# -*- coding: utf-8 -*-
"""
Module Database Quản lý Dữ liệu SQLite với cơ chế WAL (Write-Ahead Logging).
Hỗ trợ chuyển đổi từ JSON sang SQLite, chịu tải hàng trăm truy vấn đồng thời.
Sẵn sàng cho kết nối PostgreSQL đám mây (Supabase / Neon) và Cloud Storage (S3 / R2).
"""
import os
import sys
import json
import sqlite3
import datetime
import time
import uuid
import logging
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger("edudoc.db")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] [DB] %(message)s'))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "edudoc.db")

SUBMISSIONS_JSON = os.path.join(DATA_DIR, "submissions.json")
FRAUD_LOGS_JSON = os.path.join(DATA_DIR, "fraud_logs.json")
STUDENT_SESSIONS_JSON = os.path.join(DATA_DIR, "student_sessions.json")
SESSION_STATE_JSON = os.path.join(DATA_DIR, "session_state.json")
TEACHERS_JSON = os.path.join(DATA_DIR, "teachers.json")

def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Tạo kết nối SQLite an toàn với cơ chế khóa WAL (Write-Ahead Logging)
    giúp xử lý nhiều truy vấn đọc/ghi đồng thời mà không bị khóa bảng (locked database).
    """
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Bật chế độ WAL và tối ưu hóa hiệu năng chịu tải
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def _migrate_submissions_schema(conn: sqlite3.Connection) -> None:
    """Di chuyển cấu trúc bảng submissions sang UNIQUE(class_code, mssv, doc_type) an toàn (D08)"""
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='submissions';").fetchone()
        if row and "UNIQUE(mssv, doc_type)" in row[0]:
            conn.execute("PRAGMA foreign_keys=off;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS submissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    class_code TEXT,
                    sbd TEXT,
                    mssv TEXT NOT NULL,
                    name TEXT NOT NULL,
                    doc_type TEXT NOT NULL,
                    doc_name TEXT,
                    filename TEXT,
                    submitted_at TEXT,
                    elapsed_time TEXT,
                    is_suspicious_speed INTEGER DEFAULT 0,
                    preview_count INTEGER DEFAULT 0,
                    flags TEXT DEFAULT '[]',
                    status TEXT,
                    score REAL DEFAULT 10.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(class_code, mssv, doc_type)
                );
            """)
            conn.execute("""
                INSERT OR REPLACE INTO submissions_new (
                    id, class_code, sbd, mssv, name, doc_type, doc_name, filename,
                    submitted_at, elapsed_time, is_suspicious_speed, preview_count,
                    flags, status, score, created_at
                )
                SELECT id, COALESCE(class_code, 'Chung'), sbd, mssv, name, doc_type, doc_name, filename,
                       submitted_at, elapsed_time, is_suspicious_speed, preview_count,
                       flags, status, score, created_at
                FROM submissions;
            """)
            conn.execute("DROP TABLE submissions;")
            conn.execute("ALTER TABLE submissions_new RENAME TO submissions;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_mssv ON submissions(mssv);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_class ON submissions(class_code);")
            conn.execute("PRAGMA foreign_keys=on;")
            logger.info("Đã nâng cấp schema bảng submissions sang UNIQUE(class_code, mssv, doc_type)")
    except Exception as e:
        logger.warning(f"Lưu ý khi migrate submissions schema: {e}")

def _migrate_box6_schema(conn: sqlite3.Connection) -> None:
    """Di chuyển cấu trúc bảng box6_submissions sang UNIQUE(class_code, mssv, doc_type) an toàn (D08)"""
    try:
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='box6_submissions';").fetchone()
        if row and "UNIQUE(mssv, doc_type)" in row[0]:
            conn.execute("PRAGMA foreign_keys=off;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS box6_submissions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mssv TEXT NOT NULL,
                    name TEXT NOT NULL,
                    class_code TEXT,
                    doc_type TEXT NOT NULL,
                    box6_text TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(class_code, mssv, doc_type)
                );
            """)
            conn.execute("""
                INSERT OR REPLACE INTO box6_submissions_new (
                    id, mssv, name, class_code, doc_type, box6_text, updated_at
                )
                SELECT id, mssv, name, COALESCE(class_code, 'Chung'), doc_type, box6_text, updated_at
                FROM box6_submissions;
            """)
            conn.execute("DROP TABLE box6_submissions;")
            conn.execute("ALTER TABLE box6_submissions_new RENAME TO box6_submissions;")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_box6_mssv ON box6_submissions(mssv);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_box6_doc_type ON box6_submissions(doc_type);")
            conn.execute("PRAGMA foreign_keys=on;")
            logger.info("Đã nâng cấp schema bảng box6_submissions sang UNIQUE(class_code, mssv, doc_type)")
    except Exception as e:
        logger.warning(f"Lưu ý khi migrate box6 schema: {e}")

def init_db(db_path: Optional[str] = None) -> None:
    """Khởi tạo cấu trúc các bảng SQLite nếu chưa tồn tại (D02, D08)"""
    path = db_path or DB_PATH
    import_legacy_json = not os.path.exists(path) or os.path.getsize(path) == 0
    conn = get_db_connection(db_path)
    with conn:
        # 1. BẢNG BÀI NỘP CHÍNH THỨC (SUBMISSIONS)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT,
            sbd TEXT,
            mssv TEXT NOT NULL,
            name TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            doc_name TEXT,
            filename TEXT,
            submitted_at TEXT,
            elapsed_time TEXT,
            is_suspicious_speed INTEGER DEFAULT 0,
            preview_count INTEGER DEFAULT 0,
            flags TEXT DEFAULT '[]',
            status TEXT,
            score REAL DEFAULT 10.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(class_code, mssv, doc_type)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_mssv ON submissions(mssv);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_class ON submissions(class_code);")

        # Nâng cấp bảng cũ sang UNIQUE composite đa lớp nếu cần
        _migrate_submissions_schema(conn)

        # 1B. BẢNG NHẬT KÝ KIỂM TRA THỬ / THẨM ĐỊNH (VALIDATION_LOGS - D02)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS validation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT,
            sbd TEXT,
            mssv TEXT NOT NULL,
            name TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            temp_file TEXT,
            percentage REAL DEFAULT 0.0,
            score REAL DEFAULT 0.0,
            status TEXT,
            preview_index INTEGER DEFAULT 1,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_val_logs_mssv ON validation_logs(mssv);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_val_logs_class ON validation_logs(class_code);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_mssv ON submissions(mssv);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_class ON submissions(class_code);")

        # 2. BẢNG NHẬT KÝ GIAN LẬN (FRAUD_LOGS)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS fraud_logs (
            id TEXT PRIMARY KEY,
            class_code TEXT,
            timestamp TEXT,
            doc_type TEXT,
            fraud_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_fraud_class ON fraud_logs(class_code);")

        # 3. BẢNG PHIÊN LÀM BÀI SINH VIÊN (STUDENT_SESSIONS)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS student_sessions (
            session_key TEXT PRIMARY KEY,
            mssv TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            started_at TEXT,
            timestamp REAL,
            preview_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_mssv ON student_sessions(mssv);")
        # 4. BẢNG ĐIỀU KHIỂN PHÒNG HỌC / CA THI (SESSION_STATE)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS session_state (
            key TEXT PRIMARY KEY,
            is_open INTEGER DEFAULT 1,
            enforce_roster INTEGER DEFAULT 1,
            active_doc_type TEXT DEFAULT 'cong_van_de_nghi',
            message TEXT,
            updated_at TEXT
        );
        """)
            # 5. BẢNG DANH SÁCH GIẢNG VIÊN (TEACHERS)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            title TEXT,
            department TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teachers_name ON teachers(name);");
        
        # Đảm bảo cột active_teacher và active_teacher_id tồn tại trong session_state
        try:
            conn.execute("ALTER TABLE session_state ADD COLUMN active_teacher TEXT DEFAULT 'ThS. Cao Thành Trung';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE session_state ADD COLUMN active_teacher_id TEXT DEFAULT 'GV01';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE session_state ADD COLUMN enable_anti_cheat INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE student_sessions ADD COLUMN quiz_passed INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE session_state ADD COLUMN enforce_quiz INTEGER DEFAULT 1;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE session_state ADD COLUMN max_previews INTEGER DEFAULT 3;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE session_state ADD COLUMN enforce_preview_limit INTEGER DEFAULT 0;")
        except Exception:
            pass

        # 6. BẢNG NỘI DUNG THÂN BÀI Ô 6 (BOX 6 SUBMISSIONS - ĐỐI CHIẾU ĐẠO VĂN)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS box6_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mssv TEXT NOT NULL,
            name TEXT NOT NULL,
            class_code TEXT,
            doc_type TEXT NOT NULL,
            box6_text TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(mssv, doc_type)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_box6_mssv ON box6_submissions(mssv);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_box6_doc_type ON box6_submissions(doc_type);")
        _migrate_box6_schema(conn)

        # 7. BẢNG PHIÊN THI TRẮC NGHIỆM (QUIZ ATTEMPTS - PRIORITY 1)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            attempt_id TEXT PRIMARY KEY,
            class_code TEXT NOT NULL,
            mssv TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            started_at TEXT NOT NULL,
            time_limit_seconds INTEGER DEFAULT 300,
            question_ids TEXT NOT NULL,
            questions_spec TEXT,
            status TEXT DEFAULT 'IN_PROGRESS',
            score INTEGER DEFAULT 0,
            total INTEGER DEFAULT 5,
            pass_score INTEGER DEFAULT 4,
            passed INTEGER DEFAULT 0,
            answers TEXT,
            completed_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_quiz_attempts_student ON quiz_attempts(class_code, mssv, doc_type);")

        # 8. BẢNG LIÊN KẾT THIẾT BỊ SINH VIÊN (CN18 - SINGLE DEVICE PER STUDENT)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS device_bindings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT NOT NULL,
            mssv TEXT NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT,
            user_agent TEXT,
            ip_address TEXT,
            status TEXT DEFAULT 'ACTIVE',
            bound_at TEXT NOT NULL,
            last_active_at TEXT NOT NULL,
            UNIQUE(class_code, mssv)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_device_bindings_student ON device_bindings(class_code, mssv);")

        # 9. BẢNG YÊU CẦU ĐỔI THIẾT BỊ (CN18 - DEVICE CHANGE REQUESTS)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS device_change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT UNIQUE NOT NULL,
            class_code TEXT NOT NULL,
            mssv TEXT NOT NULL,
            student_name TEXT,
            old_device_id TEXT,
            new_device_id TEXT NOT NULL,
            new_user_agent TEXT,
            new_ip_address TEXT,
            reason TEXT DEFAULT 'Đổi máy tính làm bài',
            status TEXT DEFAULT 'PENDING',
            requested_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by TEXT
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_device_requests_status ON device_change_requests(status);")

        # 10. BẢNG QUYỀN LÀM LẠI BÀI (CN17 - RE-ATTEMPT PERMISSIONS)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS reattempt_permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT NOT NULL,
            mssv TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            permitted_by TEXT NOT NULL,
            permitted_at TEXT NOT NULL,
            reason TEXT,
            used INTEGER DEFAULT 0,
            used_at TEXT,
            reserved_attempt_id TEXT,
            status TEXT DEFAULT 'ACTIVE'
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reattempt_student ON reattempt_permissions(class_code, mssv, doc_type);")
        try:
            conn.execute("ALTER TABLE reattempt_permissions ADD COLUMN reserved_attempt_id TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE reattempt_permissions ADD COLUMN status TEXT DEFAULT 'ACTIVE';")
        except Exception:
            pass
        try:
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_device_bindings_active_mssv ON device_bindings(LOWER(mssv)) WHERE status = 'ACTIVE';")
        except Exception:
            pass
        try:
            conn.execute("""
                UPDATE quiz_attempts SET status = 'EXPIRED'
                WHERE status = 'IN_PROGRESS' AND mssv != '' AND attempt_id NOT IN (
                    SELECT attempt_id FROM (
                        SELECT attempt_id, ROW_NUMBER() OVER(PARTITION BY UPPER(class_code), LOWER(mssv), doc_type ORDER BY started_at DESC) as rn
                        FROM quiz_attempts WHERE status = 'IN_PROGRESS' AND mssv != ''
                    ) WHERE rn = 1
                );
            """)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_quiz_attempts_in_progress ON quiz_attempts(UPPER(class_code), LOWER(mssv), doc_type) WHERE status = 'IN_PROGRESS' AND mssv != '';")
        except Exception:
            pass

        # 11. BẢNG LỊCH SỬ BÀI NỘP TRƯỚC ĐÓ (CN17 - SUBMISSIONS HISTORY)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS submissions_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_code TEXT,
            sbd TEXT,
            mssv TEXT NOT NULL,
            name TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            doc_name TEXT,
            filename TEXT,
            submitted_at TEXT,
            elapsed_time TEXT,
            score REAL,
            checksum TEXT,
            archived_at TEXT NOT NULL,
            archive_reason TEXT
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_submissions_hist_student ON submissions_history(class_code, mssv, doc_type);")

        # Đảm bảo cột checksum tồn tại trong submissions (PRIORITY 2)
        try:
            conn.execute("ALTER TABLE submissions ADD COLUMN checksum TEXT DEFAULT '';")
        except Exception:
            pass
    conn.close()

    # JSON is an import source for a new database, not a live source of truth.
    # Reimporting whenever a table is empty resurrects deliberately deleted data.
    if import_legacy_json:
        migrate_json_to_sqlite(db_path)

_last_sync_time = 0.0
_sync_lock = threading.Lock()

def _sync_to_json_cache(force: bool = False):
    """Đồng bộ trạng thái SQLite ra tệp JSON dự phòng không chặn luồng chính (D29)"""
    global _last_sync_time
    now = time.time()
    if not force and (now - _last_sync_time < 3.0):
        return
    _last_sync_time = now

    def _worker():
        with _sync_lock:
            try:
                state = get_session_state_db()
                with open(SESSION_STATE_JSON, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    threading.Thread(target=_worker, daemon=True).start()

def migrate_json_to_sqlite(db_path: Optional[str] = None) -> None:
    """Tự động chuyển đổi dữ liệu từ các file JSON cũ sang SQLite nếu bảng còn rỗng"""
    conn = get_db_connection(db_path)
    try:
        # 1. Migrate Submissions
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM submissions;")
        sub_count = cursor.fetchone()[0]
        if sub_count == 0 and os.path.exists(SUBMISSIONS_JSON):
            try:
                with open(SUBMISSIONS_JSON, "r", encoding="utf-8") as f:
                    old_subs = json.load(f)
                if isinstance(old_subs, list):
                    for s in old_subs:
                        flags_str = json.dumps(s.get("flags", []), ensure_ascii=False) if isinstance(s.get("flags"), list) else "[]"
                        conn.execute("""
                            INSERT OR REPLACE INTO submissions 
                            (class_code, sbd, mssv, name, doc_type, doc_name, filename, submitted_at, elapsed_time, is_suspicious_speed, preview_count, flags, status, score)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            s.get("class_code", "Chung"),
                            s.get("sbd", ""),
                            s.get("mssv", ""),
                            s.get("name", ""),
                            s.get("doc_type", ""),
                            s.get("doc_name", ""),
                            s.get("filename", ""),
                            s.get("submitted_at", ""),
                            s.get("elapsed_time", ""),
                            1 if s.get("is_suspicious_speed") else 0,
                            s.get("preview_count", 0),
                            flags_str,
                            s.get("status", "Hoàn thành 100% Nghị định 30"),
                            float(s.get("score", 10.0))
                        ))
                    conn.commit()
            except Exception:
                pass

        # 2. Migrate Fraud Logs
        cursor.execute("SELECT COUNT(*) FROM fraud_logs;")
        fraud_count = cursor.fetchone()[0]
        if fraud_count == 0 and os.path.exists(FRAUD_LOGS_JSON):
            try:
                with open(FRAUD_LOGS_JSON, "r", encoding="utf-8") as f:
                    old_frauds = json.load(f)
                if isinstance(old_frauds, list):
                    for f_entry in old_frauds:
                        f_id = f_entry.get("id", str(time.time()))
                        f_class = f_entry.get("class_code", "Chung")
                        f_ts = f_entry.get("timestamp", "")
                        f_doc = f_entry.get("doc_type", "")
                        f_data_str = json.dumps(f_entry.get("fraud_data", {}), ensure_ascii=False)
                        conn.execute("""
                            INSERT OR REPLACE INTO fraud_logs (id, class_code, timestamp, doc_type, fraud_data)
                            VALUES (?, ?, ?, ?, ?)
                        """, (f_id, f_class, f_ts, f_doc, f_data_str))
                    conn.commit()
            except Exception:
                pass

        # 3. Migrate Student Sessions
        cursor.execute("SELECT COUNT(*) FROM student_sessions;")
        sess_count = cursor.fetchone()[0]
        if sess_count == 0 and os.path.exists(STUDENT_SESSIONS_JSON):
            try:
                with open(STUDENT_SESSIONS_JSON, "r", encoding="utf-8") as f:
                    old_sess = json.load(f)
                if isinstance(old_sess, dict):
                    for key, val in old_sess.items():
                        parts = key.split("_", 1)
                        mssv = parts[0] if len(parts) > 0 else ""
                        doc_type = parts[1] if len(parts) > 1 else ""
                        conn.execute("""
                            INSERT OR REPLACE INTO student_sessions (session_key, mssv, doc_type, started_at, timestamp, preview_count)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (
                            key,
                            mssv,
                            doc_type,
                            val.get("started_at", ""),
                            float(val.get("timestamp", time.time())),
                            val.get("preview_count", 0)
                        ))
                    conn.commit()
            except Exception:
                pass
        # 4. Migrate Session State
        cursor.execute("SELECT COUNT(*) FROM session_state;")
        st_count = cursor.fetchone()[0]
        if st_count == 0 and os.path.exists(SESSION_STATE_JSON):
            try:
                with open(SESSION_STATE_JSON, "r", encoding="utf-8") as f:
                    old_st = json.load(f)
                if isinstance(old_st, dict):
                    conn.execute("""
                        INSERT OR REPLACE INTO session_state (key, is_open, enforce_roster, active_doc_type, message, updated_at)
                        VALUES ('current_session', ?, ?, ?, ?, ?)
                    """, (
                        1 if old_st.get("is_open", True) else 0,
                        1 if old_st.get("enforce_roster", True) else 0,
                        old_st.get("active_doc_type", "cong_van_de_nghi"),
                        old_st.get("message", "Phòng làm bài đang mở."),
                        old_st.get("updated_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    ))
                    conn.commit()
            except Exception:
                pass
        # 5. Migrate Teachers
        cursor.execute("SELECT COUNT(*) FROM teachers;")
        teacher_count = cursor.fetchone()[0]
        if teacher_count == 0 and os.path.exists(TEACHERS_JSON):
            try:
                with open(TEACHERS_JSON, "r", encoding="utf-8") as f:
                    t_data = json.load(f)
                t_list = t_data.get("teachers", []) if isinstance(t_data, dict) else t_data
                for t in t_list:
                    conn.execute("""
                        INSERT OR REPLACE INTO teachers (id, name, title, department, email, phone)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        t.get("id"),
                        t.get("name"),
                        t.get("title", ""),
                        t.get("department", ""),
                        t.get("email", ""),
                        t.get("phone", "")
                    ))
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()

# =========================================================================
# API SUBMISSIONS
# =========================================================================
def get_all_submissions(class_code: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả bài nộp (có lọc theo mã lớp)"""
    conn = get_db_connection(db_path)
    try:
        if class_code and class_code != "ALL":
            rows = conn.execute("SELECT * FROM submissions WHERE class_code = ? ORDER BY id ASC;", (class_code,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM submissions ORDER BY id ASC;").fetchall()
        
        result = []
        for r in rows:
            flags = []
            try:
                flags = json.loads(r["flags"]) if r["flags"] else []
            except Exception:
                pass
            result.append({
                "id": r["id"],
                "class_code": r["class_code"],
                "sbd": r["sbd"],
                "mssv": r["mssv"],
                "name": r["name"],
                "doc_type": r["doc_type"],
                "doc_name": r["doc_name"],
                "filename": r["filename"],
                "submitted_at": r["submitted_at"],
                "elapsed_time": r["elapsed_time"],
                "is_suspicious_speed": bool(r["is_suspicious_speed"]),
                "preview_count": r["preview_count"],
                "flags": flags,
                "status": r["status"],
                "score": r["score"],
                "checksum": r["checksum"] if "checksum" in r.keys() else ""
            })
        return result
    finally:
        conn.close()

def save_submission(sub: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Lưu hoặc cập nhật bài nộp của sinh viên vào SQLite"""
    conn = get_db_connection(db_path)
    try:
        flags_str = json.dumps(sub.get("flags", []), ensure_ascii=False) if isinstance(sub.get("flags"), list) else "[]"
        checksum_val = str(sub.get("checksum", "")).strip()
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO submissions
                (class_code, sbd, mssv, name, doc_type, doc_name, filename, submitted_at, elapsed_time, is_suspicious_speed, preview_count, flags, status, score, checksum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                sub.get("class_code", "Chung"),
                sub.get("sbd", ""),
                sub.get("mssv", ""),
                sub.get("name", ""),
                sub.get("doc_type", ""),
                sub.get("doc_name", ""),
                sub.get("filename", ""),
                sub.get("submitted_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                sub.get("elapsed_time", "N/A"),
                1 if sub.get("is_suspicious_speed") else 0,
                sub.get("preview_count", 0),
                flags_str,
                sub.get("status", "Hoàn thành 100% Nghị định 30"),
                float(sub.get("score", 10.0)),
                checksum_val
            ))
    finally:
        conn.close()
    _sync_to_json_cache()

def delete_submission_by_mssv(mssv: str, doc_type: str, class_code: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """Xóa bài nộp theo MSSV, loại văn bản và mã lớp (R2 01, D08)"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            c_clean = str(class_code or "").strip().upper()
            if c_clean and c_clean != "ALL":
                cur = conn.execute(
                    "DELETE FROM submissions WHERE UPPER(class_code) = ? AND mssv = ? AND doc_type = ?;",
                    (c_clean, mssv, doc_type)
                )
            else:
                cur = conn.execute(
                    "DELETE FROM submissions WHERE mssv = ? AND doc_type = ?;",
                    (mssv, doc_type)
                )
            deleted = cur.rowcount > 0
        return deleted
    finally:
        conn.close()
        _sync_to_json_cache()

def delete_submission_by_index(index: int, db_path: Optional[str] = None) -> bool:
    """Xóa bài nộp theo chỉ mục danh sách (để tương thích API cũ)"""
    subs = get_all_submissions(db_path=db_path)
    if 0 <= index < len(subs):
        target = subs[index]
        return delete_submission_by_mssv(target["mssv"], target["doc_type"], class_code=target.get("class_code", "Chung"), db_path=db_path)
    return False

# =========================================================================
# API FRAUD LOGS
# =========================================================================
def get_all_fraud_logs(class_code: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả nhật ký gian lận"""
    conn = get_db_connection(db_path)
    try:
        if class_code and class_code != "ALL":
            rows = conn.execute("SELECT * FROM fraud_logs WHERE class_code = ? ORDER BY created_at DESC;", (class_code,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM fraud_logs ORDER BY created_at DESC;").fetchall()
        
        result = []
        for r in rows:
            fraud_data = {}
            try:
                fraud_data = json.loads(r["fraud_data"]) if r["fraud_data"] else {}
            except Exception:
                pass
            result.append({
                "id": r["id"],
                "class_code": r["class_code"],
                "timestamp": r["timestamp"],
                "doc_type": r["doc_type"],
                "fraud_data": fraud_data
            })
        return result
    finally:
        conn.close()

def add_fraud_log(fraud_entry: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Thêm một nhật ký vi phạm gian lận vào SQLite"""
    conn = get_db_connection(db_path)
    try:
        f_id = fraud_entry.get("id", str(time.time()))
        f_class = fraud_entry.get("class_code", "Chung")
        f_ts = fraud_entry.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        f_doc = fraud_entry.get("doc_type", "")
        f_data_str = json.dumps(fraud_entry.get("fraud_data", {}), ensure_ascii=False)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO fraud_logs (id, class_code, timestamp, doc_type, fraud_data)
                VALUES (?, ?, ?, ?, ?)
            """, (f_id, f_class, f_ts, f_doc, f_data_str))
    finally:
        conn.close()
    _sync_to_json_cache()

def delete_fraud_log_by_id(log_id: str, db_path: Optional[str] = None) -> bool:
    """Xóa nhật ký gian lận theo ID"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("DELETE FROM fraud_logs WHERE id = ?;", (log_id,))
            deleted = cur.rowcount > 0
        return deleted
    finally:
        conn.close()
        _sync_to_json_cache()

def clear_all_fraud_logs(db_path: Optional[str] = None) -> None:
    """Xóa toàn bộ nhật ký gian lận"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM fraud_logs;")
    finally:
        conn.close()
    _sync_to_json_cache()

# =========================================================================
# API STUDENT SESSIONS
# =========================================================================
def get_all_student_sessions(db_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """Lấy tất cả telemetry phiên làm bài dạng Dict {session_key: {...}}"""
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM student_sessions;").fetchall()
        result = {}
        for r in rows:
            keys = r.keys()
            result[r["session_key"]] = {
                "started_at": r["started_at"],
                "timestamp": r["timestamp"],
                "preview_count": r["preview_count"],
                "quiz_passed": bool(r["quiz_passed"]) if "quiz_passed" in keys else False
            }
        return result
    finally:
        conn.close()

def get_student_session(session_key: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Lấy thông tin phiên làm bài của sinh viên theo session_key"""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM student_sessions WHERE session_key = ?;", (session_key,)).fetchone()
        if row:
            keys = row.keys()
            return {
                "started_at": row["started_at"],
                "timestamp": row["timestamp"],
                "preview_count": row["preview_count"],
                "quiz_passed": bool(row["quiz_passed"]) if "quiz_passed" in keys else False
            }
        return None
    finally:
        conn.close()

def parse_student_session_key(session_key: str) -> Tuple[str, str, str]:
    """Phân tách session_key thành (class_code, mssv, doc_type) chuẩn xác."""
    VALID_DOC_TYPES = [
        "cong_van_de_nghi", "thong_bao_nhiem_vu", "thong_bao_hoat_dong",
        "to_trinh_xin_kinh_phi", "to_trinh_nhan_su", "to_trinh_thiet_bi",
        "bao_cao", "bai_thu_hoach"
    ]
    doc_type = ""
    prefix = session_key
    for dt in sorted(VALID_DOC_TYPES, key=len, reverse=True):
        if session_key.endswith("_" + dt):
            doc_type = dt
            prefix = session_key[:-len(dt)-1]
            break
    if not doc_type:
        parts = session_key.rsplit("_", 1)
        if len(parts) == 2:
            prefix, doc_type = parts[0], parts[1]
    if "_" in prefix:
        class_code, mssv = prefix.rsplit("_", 1)
    else:
        class_code, mssv = "", prefix
    return class_code, mssv, doc_type

def save_student_session(session_key: str, data: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Lưu hoặc cập nhật phiên làm bài của sinh viên (R2 02, D30)"""
    class_code, mssv, doc_type = parse_student_session_key(session_key)
    
    conn = get_db_connection(db_path)
    try:
        # Bảo toàn trạng thái quiz_passed nếu có từ trước
        existing_row = conn.execute("SELECT * FROM student_sessions WHERE session_key = ?;", (session_key,)).fetchone()
        existing_quiz = False
        if existing_row and "quiz_passed" in existing_row.keys():
            existing_quiz = bool(existing_row["quiz_passed"])
        
        quiz_passed = 1 if data.get("quiz_passed", existing_quiz) else 0

        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO student_sessions (session_key, mssv, doc_type, started_at, timestamp, preview_count, quiz_passed, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                session_key,
                mssv,
                doc_type,
                data.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                float(data.get("timestamp", time.time())),
                int(data.get("preview_count", 0)),
                quiz_passed
            ))
            # R2 02: Nếu ghi bằng legacy key (không có mã lớp) và chỉ định rõ quiz_passed, đồng bộ cho các composite sessions của sinh viên đó
            if not class_code and mssv and doc_type and "quiz_passed" in data:
                conn.execute(
                    "UPDATE student_sessions SET quiz_passed = ? WHERE LOWER(mssv) = ? AND doc_type = ?;",
                    (quiz_passed, mssv.lower(), doc_type)
                )
                if not quiz_passed:
                    conn.execute(
                        "UPDATE quiz_attempts SET status = 'RESET' WHERE LOWER(mssv) = ? AND doc_type = ?;",
                        (mssv.lower(), doc_type)
                    )
    finally:
        conn.close()
    _sync_to_json_cache()

# =========================================================================
# API SESSION STATE (ĐIỀU KHIỂN PHÒNG HỌC SQLITE WAL)
# =========================================================================
def get_session_state_db(class_code: str = "", db_path: Optional[str] = None) -> Dict[str, Any]:
    """Lấy trạng thái điều khiển phòng học từ SQLite (hỗ trợ phân tách ca học theo lớp - D30)"""
    conn = get_db_connection(db_path)
    try:
        row = None
        c_clean = str(class_code or "").strip().upper()
        if c_clean and c_clean != "ALL":
            row = conn.execute("SELECT * FROM session_state WHERE key = ?;", (f"class_{c_clean}",)).fetchone()
        if not row:
            row = conn.execute("SELECT * FROM session_state WHERE key = 'current_session';").fetchone()

        if row:
            keys = row.keys()
            act_teacher = row["active_teacher"] if "active_teacher" in keys and row["active_teacher"] else "ThS. Cao Thành Trung"
            act_teacher_id = row["active_teacher_id"] if "active_teacher_id" in keys and row["active_teacher_id"] else "GV01"
            return {
                "key": row["key"],
                "is_open": bool(row["is_open"]),
                "enforce_roster": bool(row["enforce_roster"]),
                "enforce_quiz": bool(row["enforce_quiz"]) if "enforce_quiz" in keys else True,
                "enable_anti_cheat": bool(row["enable_anti_cheat"]) if "enable_anti_cheat" in keys else False,
                "max_previews": int(row["max_previews"]) if "max_previews" in keys and row["max_previews"] is not None else 3,
                "enforce_preview_limit": bool(row["enforce_preview_limit"]) if "enforce_preview_limit" in keys else False,
                "active_doc_type": row["active_doc_type"] or "cong_van_de_nghi",
                "message": row["message"] or "",
                "active_teacher": act_teacher,
                "active_teacher_id": act_teacher_id,
                "updated_at": row["updated_at"] or ""
            }
        return {
            "key": "current_session",
            "is_open": True,
            "enforce_roster": True,
            "enforce_quiz": True,
            "enable_anti_cheat": False,
            "max_previews": 3,
            "enforce_preview_limit": False,
            "active_doc_type": "cong_van_de_nghi",
            "message": "Phòng làm bài đang mở.",
            "active_teacher": "ThS. Cao Thành Trung",
            "active_teacher_id": "GV01",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    finally:
        conn.close()

def save_session_state_db(state: Dict[str, Any], class_code: str = "", db_path: Optional[str] = None) -> None:
    """Lưu hoặc cập nhật trạng thái phòng học vào SQLite đầy đủ mọi cột (D07, D30)"""
    conn = get_db_connection(db_path)
    try:
        c_clean = str(class_code or "").strip().upper()
        target_key = f"class_{c_clean}" if (c_clean and c_clean != "ALL") else "current_session"

        row = conn.execute("SELECT * FROM session_state WHERE key = ?;", (target_key,)).fetchone()
        if not row and target_key != "current_session":
            row = conn.execute("SELECT * FROM session_state WHERE key = 'current_session';").fetchone()

        keys = row.keys() if row else []
        cur_is_open = bool(row["is_open"]) if row else True
        cur_enforce = bool(row["enforce_roster"]) if row else True
        cur_quiz = bool(row["enforce_quiz"]) if row and "enforce_quiz" in keys else True
        cur_anti_cheat = bool(row["enable_anti_cheat"]) if row and "enable_anti_cheat" in keys else False
        cur_max_previews = int(row["max_previews"]) if row and "max_previews" in keys and row["max_previews"] is not None else 3
        cur_enforce_prev = bool(row["enforce_preview_limit"]) if row and "enforce_preview_limit" in keys else False
        cur_active = (row["active_doc_type"] or "cong_van_de_nghi") if row else "cong_van_de_nghi"
        cur_msg = (row["message"] or "") if row else "Phòng làm bài đang mở."
        cur_teacher = (row["active_teacher"] if "active_teacher" in keys and row["active_teacher"] else "ThS. Cao Thành Trung") if row else "ThS. Cao Thành Trung"
        cur_teacher_id = (row["active_teacher_id"] if "active_teacher_id" in keys and row["active_teacher_id"] else "GV01") if row else "GV01"

        is_open = state["is_open"] if "is_open" in state else cur_is_open
        enforce_roster = state["enforce_roster"] if "enforce_roster" in state else cur_enforce
        enforce_quiz = state["enforce_quiz"] if "enforce_quiz" in state else cur_quiz
        enable_anti_cheat = state["enable_anti_cheat"] if "enable_anti_cheat" in state else cur_anti_cheat
        max_previews = state["max_previews"] if "max_previews" in state else cur_max_previews
        enforce_preview_limit = state["enforce_preview_limit"] if "enforce_preview_limit" in state else cur_enforce_prev
        active_doc_type = state["active_doc_type"] if "active_doc_type" in state else cur_active
        message = state["message"] if "message" in state else cur_msg
        active_teacher = state["active_teacher"] if "active_teacher" in state else cur_teacher
        active_teacher_id = state["active_teacher_id"] if "active_teacher_id" in state else cur_teacher_id
        updated_at = state.get("updated_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO session_state
                (key, is_open, enforce_roster, enforce_quiz, enable_anti_cheat, max_previews, enforce_preview_limit, active_doc_type, message, active_teacher, active_teacher_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                target_key,
                1 if is_open else 0,
                1 if enforce_roster else 0,
                1 if enforce_quiz else 0,
                1 if enable_anti_cheat else 0,
                max_previews,
                1 if enforce_preview_limit else 0,
                active_doc_type,
                message,
                active_teacher,
                active_teacher_id,
                updated_at
            ))
        logger.info(f"Đã lưu session_state cho [{target_key}]: anti_cheat={enable_anti_cheat}, open={is_open}")
    except Exception as e:
        logger.error(f"Lỗi khi lưu session_state: {e}")
        raise
    finally:
        conn.close()
    _sync_to_json_cache()
    try:
        merged_dict = {
            "is_open": bool(is_open),
            "enforce_roster": bool(enforce_roster),
            "active_doc_type": active_doc_type,
            "message": message,
            "active_teacher": active_teacher,
            "active_teacher_id": active_teacher_id,
            "updated_at": updated_at
        }
        with open(SESSION_STATE_JSON, "w", encoding="utf-8") as f:
            json.dump(merged_dict, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# =========================================================================
# API QUẢN LÝ GIẢNG VIÊN (TEACHERS SQLITE WAL)
# =========================================================================
def get_all_teachers_db(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả giảng viên từ SQLite"""
    conn = get_db_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM teachers ORDER BY id ASC;").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def save_teacher_db(t: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Thêm hoặc cập nhật giảng viên vào SQLite"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO teachers (id, name, title, department, email, phone)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                t.get("id"),
                t.get("name"),
                t.get("title", ""),
                t.get("department", ""),
                t.get("email", ""),
                t.get("phone", "")
            ))
    finally:
        conn.close()

def delete_teacher_db(teacher_id: str, db_path: Optional[str] = None) -> bool:
    """Xóa giảng viên theo ID"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM teachers WHERE id = ?;", (teacher_id,))
        return True
    finally:
        conn.close()

# Khởi tạo database tự động khi import
init_db()

# =========================================================================
# API BOX 6 SUBMISSIONS (ĐỐI CHIẾU ĐẠO VĂN NỘI DUNG THÂN BÀI)
# =========================================================================
def save_box6_submission(mssv: str, name: str, class_code: str, doc_type: str, box6_text: str, db_path: Optional[str] = None) -> None:
    """Lưu trữ / Cập nhật nội dung Thân bài (Ô 6) của sinh viên để đối chiếu đạo văn"""
    if not mssv or not box6_text or len(box6_text.strip()) < 25:
        return
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO box6_submissions (mssv, name, class_code, doc_type, box6_text, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (str(mssv).strip(), name or "", class_code or "Chung", doc_type or "", box6_text.strip()))
    finally:
        conn.close()

def get_all_box6_submissions(doc_type: Optional[str] = None, exclude_mssv: Optional[str] = None, class_code: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách nội dung Ô 6 của các sinh viên khác để so khớp đạo văn (D08, D23)"""
    conn = get_db_connection(db_path)
    try:
        cursor = conn.cursor()
        query = "SELECT mssv, name, class_code, doc_type, box6_text, updated_at FROM box6_submissions WHERE 1=1"
        params = []
        if doc_type:
            query += " AND doc_type = ?"
            params.append(doc_type)
        if exclude_mssv:
            query += " AND mssv != ?"
            params.append(str(exclude_mssv).strip())
        if class_code and class_code.upper() != "ALL":
            query += " AND class_code = ?"
            params.append(class_code.upper())
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def delete_box6_submission_by_mssv(mssv: str, doc_type: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    """Xóa bản ghi Ô 6 của sinh viên"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            if doc_type:
                res = conn.execute("DELETE FROM box6_submissions WHERE mssv = ? AND doc_type = ?;", (str(mssv).strip(), doc_type))
            else:
                res = conn.execute("DELETE FROM box6_submissions WHERE mssv = ?;", (str(mssv).strip(),))
            return res.rowcount > 0
    finally:
        conn.close()


# =========================================================================
# API VALIDATION LOGS (NHẬT KÝ THẨM ĐỊNH THỬ - D02)
# =========================================================================
def save_validation_log(val_log: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Lưu nhật ký một lần kiểm tra thử (Preview) vào SQLite (D02)"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO validation_logs
                (class_code, sbd, mssv, name, doc_type, temp_file, percentage, score, status, preview_index)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                val_log.get("class_code", "Chung"),
                val_log.get("sbd", ""),
                val_log.get("mssv", ""),
                val_log.get("name", ""),
                val_log.get("doc_type", ""),
                val_log.get("temp_file", ""),
                float(val_log.get("percentage", 0.0)),
                float(val_log.get("score", 0.0)),
                val_log.get("status", ""),
                int(val_log.get("preview_index", 1))
            ))
    except Exception as e:
        logger.error(f"Lỗi khi lưu validation_log: {e}")
    finally:
        conn.close()

def get_validation_logs(class_code: Optional[str] = None, mssv: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách nhật ký kiểm tra thử theo lớp hoặc MSSV (D02)"""
    conn = get_db_connection(db_path)
    try:
        query = "SELECT * FROM validation_logs"
        params = []
        conditions = []
        if class_code and class_code != "ALL":
            conditions.append("class_code = ?")
            params.append(class_code)
        if mssv:
            conditions.append("mssv = ?")
            params.append(mssv)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY validated_at DESC;"
        rows = conn.execute(query, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

# =========================================================================
# API DATABASE BACKUP & RESTORE (SAO LƯU & KHÔI PHỤC - D24)
# =========================================================================
def backup_database(backup_dir: Optional[str] = None, db_path: Optional[str] = None) -> str:
    """Online backup with a unique filename; existing snapshots are never overwritten."""
    if not backup_dir:
        backup_dir = os.path.join(DATA_DIR, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_file = os.path.join(backup_dir, f"edudoc_backup_{timestamp}_{uuid.uuid4().hex}.db")
    source_conn = get_db_connection(db_path)
    dest_conn = None
    try:
        dest_conn = sqlite3.connect(backup_file)
        source_conn.backup(dest_conn)
        logger.info(f"Đã tạo bản sao lưu cơ sở dữ liệu: {backup_file}")
        return backup_file
    except Exception:
        if dest_conn is not None:
            dest_conn.close()
            dest_conn = None
        if os.path.exists(backup_file):
            os.unlink(backup_file)
        raise
    finally:
        if dest_conn is not None:
            dest_conn.close()
        source_conn.close()


def restore_database(backup_file: str, db_path: Optional[str] = None) -> bool:
    """Validate the source and preserve a rollback snapshot before replacing data.

    Restore must be run during a maintenance window with student writes stopped.
    """
    source_path = Path(backup_file).resolve()
    target_path = Path(db_path or DB_PATH).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy file backup: {backup_file}")
    if source_path == target_path:
        raise ValueError("Không thể khôi phục từ chính cơ sở dữ liệu đang sử dụng.")
    backup_conn = sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True)
    dest_conn = None
    try:
        if backup_conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Bản sao lưu SQLite bị hỏng.")
        tables = {row[0] for row in backup_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"submissions", "student_sessions", "session_state"}.issubset(tables):
            raise ValueError("Tệp không phải bản sao lưu cơ sở dữ liệu EDUDOC hợp lệ.")
        if target_path.exists():
            backup_database(str(target_path.parent / "backups"), db_path=str(target_path))
        dest_conn = sqlite3.connect(target_path)
        backup_conn.backup(dest_conn)
        logger.info(f"Đã khôi phục cơ sở dữ liệu từ: {backup_file}")
        return True
    finally:
        if dest_conn is not None:
            dest_conn.close()
        backup_conn.close()


def list_backups(backup_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Liệt kê danh sách các bản sao lưu cơ sở dữ liệu đã có (D24)"""
    if not backup_dir:
        backup_dir = os.path.join(DATA_DIR, "backups")
    if not os.path.exists(backup_dir):
        return []

    files = []
    for f in os.listdir(backup_dir):
        if f.endswith(".db"):
            fp = os.path.join(backup_dir, f)
            st = os.stat(fp)
            files.append({
                "filename": f,
                "path": fp,
                "size_bytes": st.st_size,
                "created_at": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    files.sort(key=lambda x: x["created_at"], reverse=True)
    return files

# =========================================================================
# API QUIZ ATTEMPTS & PREVIEW QUOTA (PRIORITY 1 & ATOMIC PREVIEW)
# =========================================================================
def save_quiz_attempt(attempt_data: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Lưu phiên làm bài trắc nghiệm mới vào SQLite (Priority 1)"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO quiz_attempts (
                    attempt_id, class_code, mssv, doc_type, started_at,
                    time_limit_seconds, question_ids, questions_spec, status,
                    score, total, pass_score, passed, answers, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt_data["attempt_id"],
                attempt_data.get("class_code", "Chung"),
                attempt_data.get("mssv", ""),
                attempt_data.get("doc_type", ""),
                attempt_data.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                attempt_data.get("time_limit_seconds", 300),
                attempt_data.get("question_ids", "[]"),
                attempt_data.get("questions_spec", "[]"),
                attempt_data.get("status", "IN_PROGRESS"),
                attempt_data.get("score", 0),
                attempt_data.get("total", 5),
                attempt_data.get("pass_score", 4),
                1 if attempt_data.get("passed") else 0,
                attempt_data.get("answers", "{}"),
                attempt_data.get("completed_at", None)
            ))
    finally:
        conn.close()

def get_or_create_quiz_attempt(attempt_data: Dict[str, Any], db_path: Optional[str] = None) -> Tuple[Dict[str, Any], bool]:
    """
    Tạo hoặc trả về phiên làm bài trắc nghiệm một cách nguyên tử (R6 06 - Atomic Concurrency Guard).
    Đảm bảo 2 yêu cầu đồng thời từ cùng sinh viên không bao giờ tạo 2 attempt_id khác nhau.
    Trả về: (attempt_dict, is_newly_created)
    """
    conn = get_db_connection(db_path)
    try:
        c_code = str(attempt_data.get("class_code", "Chung")).strip().upper()
        m_clean = str(attempt_data.get("mssv", "")).strip().lower()
        d_type = str(attempt_data.get("doc_type", "")).strip()
        with conn:
            # Tra cứu xem đã có lượt IN_PROGRESS chưa hết giờ chưa (chỉ khi có định danh MSSV)
            if m_clean:
                row = conn.execute("""
                    SELECT * FROM quiz_attempts
                    WHERE UPPER(class_code) = ? AND LOWER(mssv) = ? AND doc_type = ? AND status = 'IN_PROGRESS'
                    ORDER BY created_at DESC, started_at DESC LIMIT 1;
                """, (c_code, m_clean, d_type)).fetchone()
                if row:
                    att = dict(row)
                    s_dt = datetime.datetime.strptime(att["started_at"], "%Y-%m-%d %H:%M:%S")
                    elapsed = (datetime.datetime.now() - s_dt).total_seconds()
                    rem_sec = max(0, int(att.get("time_limit_seconds", 300) - elapsed))
                    if rem_sec > 0:
                        return att, False

            # Tạo lượt mới (chống xung đột đồng thời)
            try:
                conn.execute("""
                    INSERT INTO quiz_attempts (
                        attempt_id, class_code, mssv, doc_type, started_at,
                        time_limit_seconds, question_ids, questions_spec, status,
                        score, total, pass_score, passed, answers, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt_data["attempt_id"],
                    c_code,
                    m_clean,
                    d_type,
                    attempt_data.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    attempt_data.get("time_limit_seconds", 300),
                    attempt_data.get("question_ids", "[]"),
                    attempt_data.get("questions_spec", "[]"),
                    attempt_data.get("status", "IN_PROGRESS"),
                    attempt_data.get("score", 0),
                    attempt_data.get("total", 5),
                    attempt_data.get("pass_score", 4),
                    1 if attempt_data.get("passed") else 0,
                    attempt_data.get("answers", "{}"),
                    attempt_data.get("completed_at", None)
                ))
                return attempt_data, True
            except sqlite3.IntegrityError:
                # Tranh chấp đồng thời: một yêu cầu khác vừa tạo attempt, lấy lại attempt đó
                row = conn.execute("""
                    SELECT * FROM quiz_attempts
                    WHERE UPPER(class_code) = ? AND LOWER(mssv) = ? AND doc_type = ? AND status = 'IN_PROGRESS'
                    ORDER BY created_at DESC, started_at DESC LIMIT 1;
                """, (c_code, m_clean, d_type)).fetchone()
                if row:
                    return dict(row), False
                return attempt_data, True
    finally:
        conn.close()

def get_quiz_attempt(attempt_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Truy vấn thông tin phiên làm bài trắc nghiệm theo attempt_id (Priority 1)"""
    if not attempt_id:
        return None
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM quiz_attempts WHERE attempt_id = ?;", (attempt_id,)).fetchone()
        if not row:
            return None
        res = dict(row)
        try:
            res["question_ids"] = json.loads(res["question_ids"]) if res["question_ids"] else []
        except Exception:
            res["question_ids"] = []
        try:
            res["answers"] = json.loads(res["answers"]) if res["answers"] else {}
        except Exception:
            res["answers"] = {}
        res["passed"] = bool(res["passed"])
        return res
    finally:
        conn.close()

def complete_quiz_attempt(attempt_id: str, score: int, passed: bool, answers: Optional[Any] = None, db_path: Optional[str] = None) -> bool:
    """Cập nhật kết quả chấm bài của phiên trắc nghiệm nguyên tử (Idempotency - WHERE status != 'COMPLETED', R6 04)"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("""
                UPDATE quiz_attempts
                SET status = 'COMPLETED',
                    score = ?,
                    passed = ?,
                    answers = ?,
                    completed_at = ?
                WHERE attempt_id = ? AND status != 'COMPLETED';
            """, (
                min(int(score), 5),
                1 if passed else 0,
                json.dumps(answers or {}, ensure_ascii=False) if isinstance(answers, (dict, list)) else "{}",
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                attempt_id
            ))
            return cur.rowcount > 0
    finally:
        conn.close()

def is_quiz_passed_for_student(class_code: str, mssv: str, doc_type: str, db_path: Optional[str] = None) -> bool:
    """Kiểm tra sinh viên đã hoàn thành và đạt bài trắc nghiệm của đúng lớp và loại bài hay chưa (R2 02)."""
    conn = get_db_connection(db_path)
    try:
        c_clean = str(class_code or "Chung").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        d_clean = str(doc_type or "").strip()
        # 1. Kiểm tra từ bảng quiz_attempts
        row = conn.execute("""
            SELECT COUNT(*) FROM quiz_attempts
            WHERE UPPER(class_code) = ? AND LOWER(mssv) = ? AND doc_type = ?
              AND status = 'COMPLETED' AND (passed = 1 OR score >= 4);
        """, (c_clean, m_clean, d_clean)).fetchone()
        if row and row[0] > 0:
            return True

        # 2. Kiểm tra từ student_sessions với composite key cụ thể
        comp_key = f"{c_clean}_{m_clean}_{d_clean}"
        s_row = conn.execute("SELECT quiz_passed FROM student_sessions WHERE session_key = ?;", (comp_key,)).fetchone()
        if s_row and bool(s_row[0]):
            return True
        return False
    finally:
        conn.close()

def reserve_preview_slot(class_code: str, mssv: str, doc_type: str, max_previews: int, enforce_limit: bool = True, db_path: Optional[str] = None) -> Tuple[bool, int, Optional[int]]:
    """
    Giữ chỗ lượt xem trước (preview) nguyên tử trong SQLite (R2 07).
    Trả về (allowed: bool, current_count: int, log_id: Optional[int]).
    """
    conn = get_db_connection(db_path)
    try:
        c_code = str(class_code or "Chung").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        d_type = str(doc_type or "").strip()

        with conn:
            if c_code and c_code != "CHUNG":
                row = conn.execute("""
                    SELECT COUNT(*) FROM validation_logs
                    WHERE LOWER(mssv) = ? AND doc_type = ? AND UPPER(class_code) = ?;
                """, (m_clean, d_type, c_code)).fetchone()
            else:
                row = conn.execute("""
                    SELECT COUNT(*) FROM validation_logs
                    WHERE LOWER(mssv) = ? AND doc_type = ?;
                """, (m_clean, d_type)).fetchone()
            # Đồng thời kiểm tra preview_count đã có trong student_sessions (D15)
            sess_row = conn.execute("""
                SELECT preview_count FROM student_sessions
                WHERE session_key = ? OR session_key = ?;
            """, (f"{c_code}_{m_clean}_{d_type}", f"{m_clean}_{d_type}")).fetchone()
            sess_cnt = int(sess_row[0]) if (sess_row and sess_row[0] is not None) else 0

            current_count = max(row[0] if row else 0, sess_cnt)

            if enforce_limit and current_count >= max_previews:
                return False, current_count, None

            cur = conn.execute("""
                INSERT INTO validation_logs (
                    class_code, sbd, mssv, name, doc_type, temp_file, percentage, score, status, preview_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                c_code, "", m_clean, "", d_type, "", 0.0, 0.0, "RESERVED", current_count + 1
            ))
            return True, current_count + 1, cur.lastrowid
    finally:
        conn.close()

def complete_preview_slot(log_id: int, sbd: str, name: str, temp_file: str, score: float, percentage: float, status: str, db_path: Optional[str] = None) -> bool:
    """Cập nhật kết quả thẩm định vào slot đã giữ chỗ (R2 07)."""
    if not log_id:
        return False
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("""
                UPDATE validation_logs
                SET sbd = ?, name = ?, temp_file = ?, score = ?, percentage = ?, status = ?
                WHERE id = ?;
            """, (sbd, name, temp_file, score, percentage, status, log_id))
            return cur.rowcount > 0
    finally:
        conn.close()

def release_preview_slot(log_id: int, db_path: Optional[str] = None) -> bool:
    """Giải phóng slot nếu tệp lỗi hoặc không thể thẩm định (R2 07)."""
    if not log_id:
        return False
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("DELETE FROM validation_logs WHERE id = ? AND status = 'RESERVED';", (log_id,))
            return cur.rowcount > 0
    finally:
        conn.close()

def get_atomic_preview_count(class_code: str, mssv: str, doc_type: str, db_path: Optional[str] = None) -> int:
    """Đếm số lần sinh viên đã kiểm tra thử trực tiếp từ SQLite validation_logs (Atomic - D15)"""
    conn = get_db_connection(db_path)
    try:
        c_code = str(class_code or "").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        d_type = str(doc_type or "").strip()
        if c_code and c_code != "CHUNG":
            row = conn.execute("""
                SELECT COUNT(*) FROM validation_logs
                WHERE LOWER(mssv) = ? AND doc_type = ? AND UPPER(class_code) = ?;
            """, (m_clean, d_type, c_code)).fetchone()
        else:
            row = conn.execute("""
                SELECT COUNT(*) FROM validation_logs
                WHERE LOWER(mssv) = ? AND doc_type = ?;
            """, (m_clean, d_type)).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


# =========================================================================
# CN18: API LIÊN KẾT VÀ XÁC MINH THIẾT BỊ LÀM BÀI (SINGLE DEVICE BINDING)
# =========================================================================
def get_device_binding(class_code: str, mssv: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Lấy thông tin thiết bị đang liên kết của sinh viên (Ràng buộc theo MSSV toàn hệ thống - V5 05)"""
    conn = get_db_connection(db_path)
    try:
        m_clean = str(mssv or "").strip().lower()
        if not m_clean:
            return None
        c_clean = str(class_code or "").strip().upper()
        # V5 05: Ràng buộc duy nhất theo MSSV trên toàn hệ thống
        row = conn.execute("""
            SELECT * FROM device_bindings
            WHERE LOWER(mssv) = ? AND status = 'ACTIVE'
            ORDER BY id DESC LIMIT 1;
        """, (m_clean,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def bind_device(class_code: str, mssv: str, device_id: str, device_name: str = "", user_agent: str = "", ip_address: str = "", db_path: Optional[str] = None) -> bool:
    """Đăng ký / liên kết thiết bị đầu tiên cho sinh viên (NT08) - Nguyên tử & Chống ghi đè đồng thời (V5 04, R6 07)"""
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c_clean = str(class_code or "").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        if not m_clean or not device_id:
            return False
        with conn:
            # R6 07: Kiểm tra nguyên tử trước khi đăng ký, không cho phép ghi đè thiết bị đang hoạt động
            existing = conn.execute("""
                SELECT id, device_id FROM device_bindings
                WHERE LOWER(mssv) = ? AND status = 'ACTIVE' LIMIT 1;
            """, (m_clean,)).fetchone()
            if existing:
                return existing["device_id"] == device_id

            try:
                cur = conn.execute("""
                    INSERT INTO device_bindings (class_code, mssv, device_id, device_name, user_agent, ip_address, status, bound_at, last_active_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
                """, (c_clean, m_clean, device_id, device_name or "Thiết bị chính", user_agent, ip_address, now_str, now_str))
                return cur.rowcount > 0
            except sqlite3.IntegrityError:
                return False
    finally:
        conn.close()

def verify_or_bind_device(class_code: str, mssv: str, device_id: str, user_agent: str = "", ip_address: str = "", db_path: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Xác minh thiết bị làm bài:
    - Nếu chưa có thiết bị: Tự động liên kết thiết bị đầu tiên (NT08)
    - Nếu đã có thiết bị và khớp device_id: Cho phép làm bài
    - Nếu khác device_id: Từ chối và yêu cầu đổi thiết bị (NT08, NT09, R6 03, R6 07)
    """
    if not mssv:
        return False, "Thiếu MSSV", None

    binding = get_device_binding("", mssv, db_path)
    if not binding:
        if not device_id:
            return True, "Không có mã thiết bị", None
        # Lần đầu đăng nhập / làm bài: Tự động đăng ký thiết bị ban đầu (NT08)
        bind_device(class_code, mssv, device_id, user_agent=user_agent, ip_address=ip_address, db_path=db_path)
        new_b = get_device_binding("", mssv, db_path)
        if new_b and new_b.get("device_id") == device_id:
            return True, "Đã liên kết thiết bị thành công", new_b
        return False, "Tài khoản MSSV này đã liên kết với thiết bị khác", new_b

    # Đã có binding từ trước
    if not device_id:
        return False, "Yêu cầu mã thiết bị xác thực", binding

    if binding["device_id"] == device_id:
        # D29: Giảm ghi last_active, chỉ cập nhật khi cách hơn 60 giây
        last_act = binding.get("last_active_at") or ""
        should_update = True
        if last_act:
            try:
                la_dt = datetime.datetime.strptime(last_act, "%Y-%m-%d %H:%M:%S")
                if (datetime.datetime.now() - la_dt).total_seconds() < 60:
                    should_update = False
            except Exception:
                pass
        if should_update:
            conn = get_db_connection(db_path)
            try:
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with conn:
                    conn.execute("""
                        UPDATE device_bindings SET last_active_at = ?, user_agent = ?, ip_address = ?
                        WHERE id = ?;
                    """, (now_str, user_agent, ip_address, binding["id"]))
            finally:
                conn.close()
        return True, "Thiết bị hợp lệ", binding

    # Thiết bị khác với thiết bị đã đăng ký -> Từ chối (NT08, R6 03)
    return False, "Tài khoản MSSV này đã liên kết với thiết bị khác", binding

def create_device_change_request(class_code: str, mssv: str, student_name: str, old_device_id: str, new_device_id: str, new_user_agent: str = "", new_ip: str = "", reason: str = "", db_path: Optional[str] = None) -> str:
    """Tạo yêu cầu đổi thiết bị gửi Giảng viên phê duyệt (NT09)"""
    conn = get_db_connection(db_path)
    try:
        req_id = f"DCR_{uuid.uuid4().hex[:8]}"
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute("""
                INSERT INTO device_change_requests (request_id, class_code, mssv, student_name, old_device_id, new_device_id, new_user_agent, new_ip_address, reason, status, requested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?);
            """, (req_id, class_code.upper(), mssv, student_name, old_device_id, new_device_id, new_user_agent, new_ip, reason or "Đổi thiết bị làm bài", now_str))
        return req_id
    finally:
        conn.close()

def get_device_change_requests(class_code: Optional[str] = None, status: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Lấy danh sách các yêu cầu đổi thiết bị (NT10)"""
    conn = get_db_connection(db_path)
    try:
        query = "SELECT * FROM device_change_requests WHERE 1=1"
        params = []
        if class_code and class_code != "ALL":
            query += " AND UPPER(class_code) = ?"
            params.append(class_code.upper())
        if status:
            query += " AND status = ?"
            params.append(status.upper())
        query += " ORDER BY requested_at DESC;"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def approve_device_change_request(request_id: str, approved_by: str = "Giảng viên", db_path: Optional[str] = None) -> bool:
    """Giảng viên phê duyệt yêu cầu đổi thiết bị: thu hồi thiết bị cũ và kích hoạt thiết bị mới (NT09, NT10)"""
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            row = conn.execute("SELECT * FROM device_change_requests WHERE request_id = ? AND status = 'PENDING';", (request_id,)).fetchone()
            if not row:
                return False
            # Cập nhật trạng thái yêu cầu (và tự động giải quyết các yêu cầu trùng lặp của cùng sinh viên)
            conn.execute("""
                UPDATE device_change_requests
                SET status = 'APPROVED', resolved_at = ?, resolved_by = ?
                WHERE request_id = ? OR (LOWER(mssv) = ? AND status = 'PENDING');
            """, (now_str, approved_by, request_id, row["mssv"].strip().lower()))
            # Cập nhật bảng device_bindings sang thiết bị mới cho sinh viên trên toàn hệ thống
            conn.execute("""
                UPDATE device_bindings
                SET device_id = ?, user_agent = ?, ip_address = ?, bound_at = ?, last_active_at = ?
                WHERE LOWER(mssv) = ? AND status = 'ACTIVE';
            """, (row["new_device_id"], row["new_user_agent"], row["new_ip_address"], now_str, now_str, row["mssv"].strip().lower()))
            conn.execute("""
                INSERT OR IGNORE INTO device_bindings (class_code, mssv, device_id, user_agent, ip_address, status, bound_at, last_active_at)
                VALUES (?, ?, ?, ?, ?, 'ACTIVE', ?, ?);
            """, (row["class_code"], row["mssv"], row["new_device_id"], row["new_user_agent"], row["new_ip_address"], now_str, now_str))
            return True
    finally:
        conn.close()

def reject_device_change_request(request_id: str, rejected_by: str = "Giảng viên", db_path: Optional[str] = None) -> bool:
    """Giảng viên từ chối yêu cầu đổi thiết bị"""
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            cur = conn.execute("""
                UPDATE device_change_requests
                SET status = 'REJECTED', resolved_at = ?, resolved_by = ?
                WHERE request_id = ? AND status = 'PENDING';
            """, (now_str, rejected_by, request_id))
            return cur.rowcount > 0
    finally:
        conn.close()

def get_device_change_request_by_id(request_id: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Lấy chi tiết yêu cầu đổi thiết bị theo request_id (R6 09)"""
    conn = get_db_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM device_change_requests WHERE request_id = ? LIMIT 1;", (request_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# =========================================================================
# CN17: MỘT LƯỢT CHO MỖI BÀI VÀ QUẢN LÝ QUYỀN LÀM LẠI (SINGLE ATTEMPT / RE-ATTEMPT)
# =========================================================================
def get_latest_quiz_attempt(class_code: str, mssv: str, doc_type: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Truy vấn phiên trắc nghiệm gần nhất của sinh viên cho bài học cụ thể"""
    conn = get_db_connection(db_path)
    try:
        c_clean = str(class_code or "").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        d_type = str(doc_type or "").strip()
        row = conn.execute("""
            SELECT * FROM quiz_attempts
            WHERE UPPER(class_code) = ? AND LOWER(mssv) = ? AND doc_type = ?
            ORDER BY created_at DESC, started_at DESC LIMIT 1;
        """, (c_clean, m_clean, d_type)).fetchone()
        if not row:
            return None
        res = dict(row)
        if res.get("question_ids") and isinstance(res["question_ids"], str):
            try:
                res["question_ids"] = json.loads(res["question_ids"])
            except Exception:
                pass
        return res
    finally:
        conn.close()

def get_submission_by_composite(class_code: str, mssv: str, doc_type: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Lấy bài nộp chính thức theo tổ hợp duy nhất (class_code, mssv, doc_type)"""
    conn = get_db_connection(db_path)
    try:
        c_clean = str(class_code or "").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        d_type = str(doc_type or "").strip()
        row = conn.execute("""
            SELECT * FROM submissions
            WHERE UPPER(class_code) = ? AND LOWER(mssv) = ? AND doc_type = ?;
        """, (c_clean, m_clean, d_type)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def grant_reattempt_permission(class_code: str, mssv: str, doc_type: str, permitted_by: str = "Giảng viên", reason: str = "", db_path: Optional[str] = None) -> int:
    """Giảng viên cấp quyền làm lại bài cho sinh viên (NT06, NT07)"""
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            cur = conn.execute("""
                INSERT INTO reattempt_permissions (class_code, mssv, doc_type, permitted_by, permitted_at, reason, used)
                VALUES (?, ?, ?, ?, ?, ?, 0);
            """, (class_code.upper(), mssv, doc_type, permitted_by, now_str, reason or "Giảng viên cho phép làm lại"))
            return cur.lastrowid
    finally:
        conn.close()

def get_active_reattempt_permission(class_code: str, mssv: str, doc_type: str, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Kiểm tra sinh viên có quyền làm lại chưa sử dụng không (NT06, R6 05)"""
    conn = get_db_connection(db_path)
    try:
        c_clean = str(class_code or "").strip().upper()
        m_clean = str(mssv or "").strip().lower()
        d_type = str(doc_type or "").strip()
        row = conn.execute("""
            SELECT * FROM reattempt_permissions
            WHERE (UPPER(class_code) = ? OR class_code = 'Chung' OR ? = '') AND LOWER(mssv) = ? AND doc_type = ? AND used = 0
            ORDER BY permitted_at DESC LIMIT 1;
        """, (c_clean, c_clean, m_clean, d_type)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def reserve_reattempt_permission(permit_id: int, attempt_id: str, db_path: Optional[str] = None) -> bool:
    """Gắn quyền làm lại vào lượt thi cụ thể (R6 05 - RESERVED)"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("""
                UPDATE reattempt_permissions
                SET reserved_attempt_id = ?, status = 'RESERVED'
                WHERE id = ? AND used = 0;
            """, (attempt_id, permit_id))
            return cur.rowcount > 0
    finally:
        conn.close()

def consume_reattempt_permission(permit_id: int, db_path: Optional[str] = None) -> bool:
    """Đánh dấu quyền làm lại đã được sử dụng (NT07, R6 05, R6 08)"""
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            cur = conn.execute("""
                UPDATE reattempt_permissions
                SET used = 1, used_at = ?, status = 'CONSUMED'
                WHERE id = ? AND used = 0;
            """, (now_str, permit_id))
            return cur.rowcount > 0
    finally:
        conn.close()

def archive_submission_record(sub_record: Dict[str, Any], archive_reason: str = "", db_path: Optional[str] = None) -> None:
    """Lưu bài nộp cũ vào lịch sử kiểm toán trước khi cho phép nộp bài mới (NT08)"""
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with conn:
            conn.execute("""
                INSERT INTO submissions_history (
                    class_code, sbd, mssv, name, doc_type, doc_name, filename,
                    submitted_at, elapsed_time, score, checksum, archived_at, archive_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sub_record.get("class_code"),
                sub_record.get("sbd"),
                sub_record.get("mssv"),
                sub_record.get("name"),
                sub_record.get("doc_type"),
                sub_record.get("doc_name"),
                sub_record.get("filename"),
                sub_record.get("submitted_at"),
                sub_record.get("elapsed_time"),
                sub_record.get("score"),
                sub_record.get("checksum", ""),
                now_str,
                archive_reason or "Lưu trữ trước khi nộp lại"
            ))
    finally:
        conn.close()

def save_submission_atomic(new_sub: Dict[str, Any], existing_sub: Optional[Dict[str, Any]] = None, permit_id: Optional[int] = None, archive_reason: str = "", db_path: Optional[str] = None) -> bool:
    """
    Lưu bài nộp chính thức, lưu lịch sử bài cũ và tiêu quyền làm lại trong MỘT GIAO DỊCH NGUYÊN TỬ DUY NHẤT (R2 05, R2 06, R6 08).
    Kiểm tra trạng thái bài cũ và permit TRỰC TIẾP TRONG GIAO DỊCH (Immediate Lock), ngăn chặn ghi đè race-condition.
    """
    conn = get_db_connection(db_path)
    try:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c_code = str(new_sub.get("class_code") or "Chung").strip().upper()
        m_clean = str(new_sub.get("mssv") or "").strip()
        d_type = str(new_sub.get("doc_type") or "").strip()

        with conn:
            # 1. Đọc lại bài hiện có ngay trong giao dịch
            cur = conn.execute(
                "SELECT * FROM submissions WHERE class_code = ? AND mssv = ? AND doc_type = ?;",
                (c_code, m_clean, d_type)
            )
            existing_row = cur.fetchone()

            if existing_row:
                # Đã có bài nộp trước đó -> BẮT BUỘC phải có permit_id hợp lệ
                if not permit_id:
                    raise ValueError(f"Sinh viên [{m_clean}] đã có bài nộp trước đó trong lớp [{c_code}]. Bắt buộc phải có quyền nộp lại (permit)!")

                # Xác minh permit ngay trong giao dịch
                p_cur = conn.execute(
                    "SELECT id, used FROM reattempt_permissions WHERE id = ? AND class_code = ? AND mssv = ? AND doc_type = ?;",
                    (permit_id, c_code, m_clean, d_type)
                )
                p_row = p_cur.fetchone()
                if not p_row:
                    raise ValueError(f"Không tìm thấy quyền làm lại hợp lệ (permit_id={permit_id}) cho sinh viên [{m_clean}]!")
                if p_row["used"] != 0:
                    raise ValueError(f"Quyền làm lại (permit_id={permit_id}) đã được sử dụng trước đó!")

                # Tiêu thụ permit có điều kiện used = 0
                upd_p = conn.execute(
                    "UPDATE reattempt_permissions SET used = 1, used_at = ?, status = 'CONSUMED' WHERE id = ? AND used = 0;",
                    (now_str, permit_id)
                )
                if upd_p.rowcount != 1:
                    raise ValueError(f"Xung đột đồng thời: Quyền làm lại (permit_id={permit_id}) đã bị tiêu thụ bởi tiến trình khác!")

                # Lưu bài cũ vào submissions_history
                conn.execute("""
                    INSERT INTO submissions_history (
                        class_code, sbd, mssv, name, doc_type, doc_name, filename,
                        submitted_at, elapsed_time, score, checksum, archived_at, archive_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    existing_row["class_code"], existing_row["sbd"], existing_row["mssv"],
                    existing_row["name"], existing_row["doc_type"], existing_row["doc_name"],
                    existing_row["filename"], existing_row["submitted_at"], existing_row["elapsed_time"],
                    existing_row["score"], existing_row["checksum"], now_str, archive_reason or "Làm lại bài"
                ))

                # Cập nhật bản ghi trong submissions
                flags_json = json.dumps(new_sub.get("flags", {}), ensure_ascii=False)
                conn.execute("""
                    UPDATE submissions SET
                        sbd = ?, name = ?, doc_name = ?, filename = ?, submitted_at = ?,
                        elapsed_time = ?, is_suspicious_speed = ?, preview_count = ?,
                        flags = ?, status = ?, score = ?, checksum = ?
                    WHERE class_code = ? AND mssv = ? AND doc_type = ?;
                """, (
                    new_sub.get("sbd", ""), new_sub.get("name", ""), new_sub.get("doc_name", d_type),
                    new_sub.get("filename", ""), new_sub.get("submitted_at", now_str),
                    new_sub.get("elapsed_time", "0 phút 0 giây"),
                    1 if new_sub.get("is_suspicious_speed") else 0,
                    new_sub.get("preview_count", 0), flags_json,
                    new_sub.get("status", "SUCCESS"), new_sub.get("score", 0),
                    new_sub.get("checksum", ""), c_code, m_clean, d_type
                ))

            else:
                # Chưa có bài nộp trước đó -> NỘP LẦN ĐẦU
                if permit_id:
                    conn.execute(
                        "UPDATE reattempt_permissions SET used = 1, used_at = ?, status = 'CONSUMED' WHERE id = ? AND used = 0;",
                        (now_str, permit_id)
                    )

                # Dùng INSERT thường: nếu 2 request đồng thời cùng chèn thì SQLite UNIQUE constraint sẽ bắn IntegrityError
                flags_json = json.dumps(new_sub.get("flags", {}), ensure_ascii=False)
                conn.execute("""
                    INSERT INTO submissions (
                        sbd, mssv, name, doc_type, doc_name, filename, submitted_at,
                        elapsed_time, is_suspicious_speed, preview_count, flags, status,
                        score, checksum, class_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    new_sub.get("sbd", ""), new_sub.get("mssv", ""), new_sub.get("name", ""),
                    new_sub.get("doc_type", ""), new_sub.get("doc_name", ""), new_sub.get("filename", ""),
                    new_sub.get("submitted_at", now_str), new_sub.get("elapsed_time", "0 phút 0 giây"),
                    1 if new_sub.get("is_suspicious_speed") else 0, new_sub.get("preview_count", 0),
                    flags_json, new_sub.get("status", "SUCCESS"), new_sub.get("score", 0),
                    new_sub.get("checksum", ""), c_code
                ))

        _sync_to_json_cache()
        return True
    finally:
        conn.close()

def get_submissions_history(class_code: Optional[str] = None, mssv: Optional[str] = None, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Truy vấn lịch sử các lần nộp bài đã được lưu trữ (Audit Trail)"""
    conn = get_db_connection(db_path)
    try:
        query = "SELECT * FROM submissions_history WHERE 1=1"
        params = []
        if class_code and class_code != "ALL":
            query += " AND UPPER(class_code) = ?"
            params.append(class_code.upper())
        if mssv:
            query += " AND LOWER(mssv) = ?"
            params.append(mssv.lower())
        query += " ORDER BY archived_at DESC;"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

