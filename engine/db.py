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
from typing import List, Dict, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "edudoc.db")

SUBMISSIONS_JSON = os.path.join(DATA_DIR, "submissions.json")
FRAUD_LOGS_JSON = os.path.join(DATA_DIR, "fraud_logs.json")
STUDENT_SESSIONS_JSON = os.path.join(DATA_DIR, "student_sessions.json")

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

def init_db(db_path: Optional[str] = None) -> None:
    """Khởi tạo cấu trúc các bảng SQLite nếu chưa tồn tại"""
    conn = get_db_connection(db_path)
    with conn:
        # 1. BẢNG BÀI NỘP (SUBMISSIONS)
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
            UNIQUE(mssv, doc_type)
        );
        """)
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
    conn.close()

    # Tự động đồng bộ / migrate dữ liệu cũ từ JSON vào SQLite
    migrate_json_to_sqlite(db_path)

def _sync_to_json_cache():
    """Đồng bộ trạng thái SQLite ra tệp JSON để đảm bảo tương thích ngược 100% với các test cũ"""
    try:
        # Sync submissions
        subs = get_all_submissions()
        with open(SUBMISSIONS_JSON, "w", encoding="utf-8") as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
            
        # Sync fraud_logs
        frauds = get_all_fraud_logs()
        with open(FRAUD_LOGS_JSON, "w", encoding="utf-8") as f:
            json.dump(frauds, f, ensure_ascii=False, indent=2)
            
        # Sync student_sessions
        sess = get_all_student_sessions()
        with open(STUDENT_SESSIONS_JSON, "w", encoding="utf-8") as f:
            json.dump(sess, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

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
                "score": r["score"]
            })
        return result
    finally:
        conn.close()

def save_submission(sub: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Lưu hoặc cập nhật bài nộp của sinh viên vào SQLite"""
    conn = get_db_connection(db_path)
    try:
        flags_str = json.dumps(sub.get("flags", []), ensure_ascii=False) if isinstance(sub.get("flags"), list) else "[]"
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO submissions
                (class_code, sbd, mssv, name, doc_type, doc_name, filename, submitted_at, elapsed_time, is_suspicious_speed, preview_count, flags, status, score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                float(sub.get("score", 10.0))
            ))
    finally:
        conn.close()
    _sync_to_json_cache()

def delete_submission_by_mssv(mssv: str, doc_type: str, db_path: Optional[str] = None) -> bool:
    """Xóa bài nộp theo MSSV và loại văn bản"""
    conn = get_db_connection(db_path)
    try:
        with conn:
            cur = conn.execute("DELETE FROM submissions WHERE mssv = ? AND doc_type = ?;", (mssv, doc_type))
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
        return delete_submission_by_mssv(target["mssv"], target["doc_type"], db_path=db_path)
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
            result[r["session_key"]] = {
                "started_at": r["started_at"],
                "timestamp": r["timestamp"],
                "preview_count": r["preview_count"]
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
            return {
                "started_at": row["started_at"],
                "timestamp": row["timestamp"],
                "preview_count": row["preview_count"]
            }
        return None
    finally:
        conn.close()

def save_student_session(session_key: str, data: Dict[str, Any], db_path: Optional[str] = None) -> None:
    """Lưu hoặc cập nhật phiên làm bài của sinh viên"""
    parts = session_key.split("_", 1)
    mssv = parts[0] if len(parts) > 0 else ""
    doc_type = parts[1] if len(parts) > 1 else ""
    
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO student_sessions (session_key, mssv, doc_type, started_at, timestamp, preview_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                session_key,
                mssv,
                doc_type,
                data.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                float(data.get("timestamp", time.time())),
                int(data.get("preview_count", 0))
            ))
    finally:
        conn.close()
    _sync_to_json_cache()

# Khởi tạo database tự động khi import
init_db()
