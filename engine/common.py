# -*- coding: utf-8 -*-
"""
Cấu hình và Hàm tiện ích Dùng chung cho Toàn bộ Hệ thống EDUDOC-STVB.
"""
import os
import re
import json
import time
import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STORAGE_TEMPLATES = os.path.join(BASE_DIR, "storage", "templates")
STORAGE_UPLOADS = os.path.join(BASE_DIR, "storage", "uploads")
STORAGE_SUBMITTED = os.path.join(BASE_DIR, "storage", "submitted")

SUBMISSIONS_FILE = os.path.join(DATA_DIR, "submissions.json")
FRAUD_LOGS_FILE = os.path.join(DATA_DIR, "fraud_logs.json")
CLASSES_FILE = os.path.join(DATA_DIR, "classes.json")
SESSION_STATE_FILE = os.path.join(DATA_DIR, "session_state.json")
STUDENT_SESSIONS_FILE = os.path.join(DATA_DIR, "student_sessions.json")
STUDENTS_ROSTER_FILE = os.path.join(DATA_DIR, "students_roster.json")
QUESTIONS_FILE = os.path.join(DATA_DIR, "questions.json")
TEACHERS_FILE = os.path.join(DATA_DIR, "teachers.json")

# Đảm bảo các thư mục luôn tồn tại
for path in [STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED, DATA_DIR]:
    os.makedirs(path, exist_ok=True)

def load_json_file(file_path: str, default_val: Any) -> Any:
    """Nạp tệp JSON an toàn với giá trị mặc định khi có lỗi"""
    try:
        if os.path.normcase(os.path.abspath(file_path)) == os.path.normcase(os.path.abspath(SESSION_STATE_FILE)):
            from engine.db import get_session_state_db
            return get_session_state_db()
    except Exception:
        pass
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default_val
    return default_val

import threading
_JSON_FILE_LOCK = threading.RLock()

def update_json_atomic(file_path: str, updater_fn, default_val=None):
    """
    Cập nhật tệp JSON nguyên tử bảo vệ toàn bộ chu trình Đọc - Sửa - Ghi (R2 21).
    Ngăn chặn mất cập nhật khi nhiều tiến trình/luồng ghi đồng thời.
    """
    with _JSON_FILE_LOCK:
        current_data = load_json_file(file_path, default_val if default_val is not None else {})
        res = updater_fn(current_data)
        if isinstance(res, tuple):
            success, result_val = res
            if success:
                save_json_file(file_path, current_data)
            return success, result_val
        else:
            save_json_file(file_path, current_data)
            return res

def save_json_file(file_path: str, data: Any) -> None:
    """Ghi dữ liệu ra tệp JSON với định dạng utf-8 thụt đầu dòng đẹp"""
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        if os.path.normcase(os.path.abspath(file_path)) == os.path.normcase(os.path.abspath(SESSION_STATE_FILE)) and isinstance(data, dict):
            from engine.db import save_session_state_db
            save_session_state_db(data)
    except Exception:
        pass

def get_session_state(class_code: str = "") -> Dict[str, Any]:
    """Lấy trạng thái điều khiển phòng học từ SQLite WAL theo mã lớp hoặc toàn hệ thống (D30)"""
    try:
        from engine.db import get_session_state_db
        return get_session_state_db(class_code=class_code)
    except Exception:
        default_state = {
            "is_open": False,
            "enforce_roster": True,
            "active_doc_type": "cong_van_de_nghi",
            "enforce_quiz": True,
            "max_previews": 3,
            "enforce_preview_limit": False,
            "enable_anti_cheat": False,
            "message": "Giảng viên đang giảng lý thuyết. Hệ thống làm bài tập đang tạm khóa để các bạn tập trung nghe giảng.",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        state = load_json_file(SESSION_STATE_FILE, default_state)
        if "enforce_roster" not in state:
            state["enforce_roster"] = True
        if "active_doc_type" not in state:
            state["active_doc_type"] = "cong_van_de_nghi"
        return state

def save_session_state(state: Dict[str, Any], class_code: str = "") -> None:
    """Lưu trạng thái điều khiển phòng học vào SQLite WAL và đồng bộ JSON (D30)"""
    try:
        from engine.db import save_session_state_db
        save_session_state_db(state, class_code=class_code)
    except Exception:
        save_json_file(SESSION_STATE_FILE, state)

def is_session_open(class_code: Any = "", app_testing: bool = False) -> bool:
    """Kiểm tra xem phòng thi/bài tập có đang mở cho sinh viên không (D30, Priority 3, 4)"""
    if isinstance(class_code, bool):
        app_testing = class_code
        class_code = ""

    is_testing = bool(app_testing or os.environ.get("EDUDOC_TESTING") == "1")
    if is_testing:
        try:
            from flask import request, has_request_context
            if has_request_context():
                if request.headers.get("X-Test-Force-Check-Open") == "0":
                    return False
                if request.headers.get("X-Test-Force-Check-Open") == "1":
                    return True
        except Exception:
            pass
        return True

    c_code = str(class_code or "").strip().upper()
    state = get_session_state(c_code)
    return bool(state.get("is_open", False))

def is_anti_cheat_enabled(class_code: str = "", app_testing: bool = False) -> bool:
    """Kiểm tra xem có bật chế độ kiểm tra lỗi copy / gian lận không (D07, Priority 3, 4).
    Giảng viên có thể bật/tắt chống gian lận cho từng lớp học hoặc toàn bộ hệ thống từ trang /gv.
    Tuyệt đối không hardcode theo tên mã lớp.
    """
    is_testing = bool(app_testing or os.environ.get("EDUDOC_TESTING") == "1")
    try:
        from flask import request, has_request_context
        if has_request_context():
            if is_testing and request.headers.get("X-Test-Disable-Anti-Cheat") == "1":
                return False
            if is_testing and request.headers.get("X-Test-Enable-Anti-Cheat") == "1":
                return True
    except Exception:
        pass

    c_code = str(class_code or "").strip().upper()
    # 1. Nếu lớp có cấu hình riêng biệt trong DB (được lưu với key 'class_...')
    if c_code:
        try:
            from engine.db import get_db_connection
            conn = get_db_connection()
            row = conn.execute("SELECT enable_anti_cheat FROM session_state WHERE key = ?;", (f"class_{c_code}",)).fetchone()
            conn.close()
            if row is not None and row["enable_anti_cheat"] is not None:
                return bool(row["enable_anti_cheat"])
        except Exception:
            pass

    # 2. Môi trường kiểm thử tự động (nếu không có cấu hình lớp riêng), mặc định bật để test chống gian lận
    if is_testing:
        return True

    # 3. Cấu hình toàn hệ thống (môi trường vận hành thực tế)
    global_state = get_session_state()
    if global_state and global_state.get("enable_anti_cheat") is not None:
        return bool(global_state.get("enable_anti_cheat"))

    return False

def is_student_in_roster(class_code: str, mssv: str, app_testing: bool = False, force_check: bool = False) -> bool:
    """Kiểm tra sinh viên có trong danh sách chính thức của lớp không (D05, Priority 3, 4)"""
    c_code = str(class_code or "").strip().upper()
    m_clean = str(mssv or "").strip().lower()
    
    # D05: Thiếu mã lớp hoặc MSSV luôn bị từ chối
    if not c_code or not m_clean:
        return False

    is_testing = bool(app_testing or os.environ.get("EDUDOC_TESTING") == "1")
    try:
        from flask import request, has_request_context, current_app
        if current_app and current_app.testing:
            is_testing = True
        if has_request_context():
            if current_app and not current_app.testing and os.environ.get("EDUDOC_TESTING") != "1":
                is_testing = False
            elif "werkzeug" in request.headers.get("User-Agent", "").lower() and is_testing:
                is_testing = True
            if request.headers.get("X-Test-Enforce-Roster") == "1":
                force_check = True
    except Exception:
        pass

    if not force_check and is_testing:
        return True

    # Kiểm tra cấu hình lớp cụ thể hoặc toàn cục
    state = get_session_state(c_code)
    if not state.get("enforce_roster", True):
        return True

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    class_students = roster.get(c_code, [])
    if not class_students:
        return False

    for s in class_students:
        if str(s.get("mssv", "")).strip().lower() == m_clean:
            return True
    return False

def get_student_from_roster(class_code: str, mssv: str) -> Optional[Dict[str, Any]]:
    """Tra cứu thông tin chi tiết sinh viên trong danh sách lớp"""
    c_code = str(class_code or "").strip().upper()
    m_clean = str(mssv or "").strip().lower()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    class_students = roster.get(c_code, [])
    for s in class_students:
        if str(s.get("mssv", "")).strip().lower() == m_clean:
            return s
    return None

def parse_students_text(raw_text: str) -> List[Dict[str, str]]:
    """Phân tích danh sách sinh viên nhập dạng văn bản (Excel copy, Tab, Phẩy, Gạch ngang).
    Hỗ trợ linh hoạt:
    - 4 cột: SBD <tab> MSSV <tab> Họ và tên <tab> Lớp
    - 3 cột: MSSV <tab> Họ và tên <tab> Lớp  (hoặc SBD <tab> MSSV <tab> Họ tên)
    - 2 cột: MSSV <tab> Họ tên (nếu họ tên chứa mã lớp ở đuôi sẽ tự tách riêng)
    - 1 cột: MSSV
    """
    cls_pattern = re.compile(r'^[0-9]{2}[A-Za-z0-9_-]+$')
    name_cls_split = re.compile(r'^(.*?)\s+([0-9]{2}[A-Za-z0-9_-]+)$')

    students = []
    lines = raw_text.strip().splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in re.split(r'[\t,;]+', line) if p.strip()]
        if len(parts) == 1 and "-" in line:
            parts = [p.strip() for p in line.split("-", 1) if p.strip()]
        elif len(parts) == 1 and "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]

        if not parts:
            continue

        mssv = None
        name = ""
        sbd = ""
        st_cls = ""

        if len(parts) == 1:
            mssv = parts[0]
            name = f"Sinh viên {mssv}"
        elif len(parts) == 2:
            if any(c.isdigit() for c in parts[0]) and not any(c.isdigit() for c in parts[1]):
                mssv, name = parts[0], parts[1]
            elif any(c.isdigit() for c in parts[1]) and not any(c.isdigit() for c in parts[0]):
                name, mssv = parts[0], parts[1]
            else:
                mssv, name = parts[0], parts[1]
        elif len(parts) == 3:
            p0, p1, p2 = parts[0], parts[1], parts[2]
            if cls_pattern.match(p2):
                # Định dạng MSSV <tab> Họ và tên <tab> Lớp
                mssv, name, st_cls = p0, p1, p2
            elif len(p0) <= 4 and p0.isdigit() and (len(p1) >= 6 or any(c.isdigit() for c in p1)):
                # Định dạng SBD <tab> MSSV <tab> Họ và tên
                sbd, mssv, name = p0, p1, p2
            else:
                if len(p0) >= 6 and any(c.isdigit() for c in p0):
                    mssv, name, st_cls = p0, p1, p2
                else:
                    sbd, mssv, name = p0, p1, p2
        elif len(parts) >= 4:
            sbd = parts[0]
            mssv = parts[1]
            last_part = parts[-1]
            if cls_pattern.match(last_part):
                st_cls = last_part
                name = " ".join(parts[2:-1])
            else:
                name = " ".join(parts[2:])

        # Tự động tách mã lớp nếu còn dính ở cuối tên
        if not st_cls and name:
            m = name_cls_split.match(name)
            if m:
                name = m.group(1).strip()
                st_cls = m.group(2).strip().upper()

        if mssv:
            mssv = re.sub(r'[^a-zA-Z0-9]', '', mssv).strip().upper()
            name = re.sub(r'\s+', ' ', name or '').strip()
            sbd = str(sbd).strip()
            st_cls = str(st_cls).strip().upper()
            if mssv:
                students.append({
                    "sbd": sbd,
                    "mssv": mssv,
                    "name": name or f"Sinh viên {mssv}",
                    "student_class": st_cls
                })
    return students

def cleanup_old_uploads(max_age_seconds: int = 7200) -> int:
    """Tự động dọn rác các tệp tạm trong storage/uploads quá thời gian quy định (mặc định 2h - D22)"""
    deleted_count = 0
    now = time.time()
    if not os.path.exists(STORAGE_UPLOADS):
        return 0
    for fname in os.listdir(STORAGE_UPLOADS):
        if fname == ".gitkeep":
            continue
        fpath = os.path.join(STORAGE_UPLOADS, fname)
        try:
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > max_age_seconds):
                os.remove(fpath)
                deleted_count += 1
        except Exception:
            pass
    return deleted_count


DEFAULT_TEACHERS = [
    {
        "id": "GV01",
        "name": "ThS. Nguyễn Văn A",
        "title": "Giảng viên chính",
        "department": "Bộ môn Quản trị văn phòng",
        "email": "nguyenvana@truong.edu.vn",
        "phone": "0901234567"
    },
    {
        "id": "GV02",
        "name": "TS. Trần Thị B",
        "title": "Trưởng Bộ môn",
        "department": "Bộ môn Hành chính học",
        "email": "tranthib@truong.edu.vn",
        "phone": "0912345678"
    },
    {
        "id": "GV03",
        "name": "ThS. Lê Hoàng C",
        "title": "Giảng viên",
        "department": "Khoa Quản trị & Luật",
        "email": "lehoangc@truong.edu.vn",
        "phone": "0987654321"
    }
]

def get_teachers_data() -> Dict[str, Any]:
    """Lấy danh sách giảng viên và ID giảng viên đang hoạt động"""
    data = load_json_file(TEACHERS_FILE, None)
    if not data or not isinstance(data, dict) or "teachers" not in data or not data["teachers"]:
        data = {
            "teachers": list(DEFAULT_TEACHERS),
            "active_teacher_id": "GV01"
        }
        save_json_file(TEACHERS_FILE, data)
    return data

def get_active_teacher() -> Dict[str, Any]:
    """Lấy thông tin chi tiết của giảng viên đang làm việc"""
    t_data = get_teachers_data()
    active_id = t_data.get("active_teacher_id", "GV01")
    for t in t_data.get("teachers", []):
        if t.get("id") == active_id:
            return t
    if t_data.get("teachers"):
        return t_data["teachers"][0]
    return DEFAULT_TEACHERS[0]

def set_active_teacher(teacher_id: str) -> Optional[Dict[str, Any]]:
    """Chọn giảng viên làm việc hiện tại"""
    t_data = get_teachers_data()
    found = None
    for t in t_data.get("teachers", []):
        if t.get("id") == teacher_id:
            found = t
            break
    if found:
        t_data["active_teacher_id"] = teacher_id
        save_json_file(TEACHERS_FILE, t_data)
        # Đồng bộ vào session_state
        state = get_session_state()
        state["active_teacher"] = found.get("name", "")
        state["active_teacher_id"] = teacher_id
        save_session_state(state)
        return found
    return None

# Xuất các hàm bảo mật đường dẫn và kiểm tra tệp Word
from engine.security import sanitize_identifier, safe_storage_path, is_valid_docx

# Xuất các hàm nhật ký kiểm tra và sao lưu phục hồi cơ sở dữ liệu (D02, D24)
from engine.db import (
    save_validation_log, get_validation_logs,
    backup_database, restore_database, list_backups
)
