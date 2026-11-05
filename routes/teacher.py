# -*- coding: utf-8 -*-
from __future__ import annotations
"""
Blueprint dành cho Cổng Giảng viên:
Quản lý ca thi (mở/khóa làm bài), phân công bài tập, quản lý danh sách lớp (Roster),
theo dõi bài nộp, xuất điểm CSV/Excel, quản lý nhật ký gian lận và chỉnh sửa đề thi/mẫu.
"""
import io
import os
import re
import csv
import json
import datetime
import functools
import hmac
from typing import Optional, Tuple, List, Dict, Any, Union
from flask import Blueprint, request, jsonify, render_template, send_file, Response, current_app, session

from engine.common import (
    BASE_DIR, DATA_DIR, STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    CLASSES_FILE, SESSION_STATE_FILE, STUDENTS_ROSTER_FILE, QUESTIONS_FILE, TEACHERS_FILE,
    load_json_file, save_json_file, update_json_atomic, get_session_state, save_session_state, parse_students_text,
    get_teachers_data, get_active_teacher, set_active_teacher,
    sanitize_identifier, safe_storage_path
)
from engine.db import (
    get_all_submissions, delete_submission_by_mssv,
    get_all_fraud_logs, delete_fraud_log_by_id, clear_all_fraud_logs,
    get_validation_logs, backup_database, restore_database, list_backups
)

teacher_bp = Blueprint("teacher", __name__)

def _matches_teacher_pin(pin_val: Optional[str]) -> bool:
    """Đối chiếu mã PIN với PIN cấu hình bảo mật (D20)"""
    if not pin_val:
        return False
    pin_str = str(pin_val).strip()
    expected_pin = current_app.config.get("TEACHER_PIN")
    if not expected_pin:
        return False
    return hmac.compare_digest(pin_str.encode("utf-8"), str(expected_pin).strip().encode("utf-8"))

def is_teacher_authenticated() -> bool:
    """Kiem tra xem yeu cau hien tai co quyen Giang vien hay khong (D20)"""
    # Cho phep bypass khi kiem thu tu dong, tru khi test chi dinh kiem tra phan quyen qua header
    if (current_app.testing or os.environ.get("EDUDOC_TESTING") == "1") and request.headers.get("X-Test-Auth-Required") != "1":
        return True

    # Kiem tra Flask session
    if session.get("is_teacher_auth"):
        return True

    # Kiem tra Header X-Teacher-PIN
    if _matches_teacher_pin(request.headers.get("X-Teacher-PIN")):
        return True

    # Kiem tra query param hoac JSON body
    if _matches_teacher_pin(request.args.get("teacher_pin")):
        return True
    if request.is_json and isinstance(request.json, dict) and _matches_teacher_pin(request.json.get("teacher_pin")):
        return True

    return False

def require_teacher_auth(f):
    """Decorator bat buoc xac thuc Giang vien cho cac endpoint nhay cam (D20)"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_teacher_authenticated():
            return jsonify({
                "error": "Yêu cầu quyền truy cập Giảng viên! Vui lòng nhập Mã PIN bảo mật.",
                "auth_required": True
            }), 401
        return f(*args, **kwargs)
    return decorated_function

@teacher_bp.route("/api/teacher/auth", methods=["POST"])
def teacher_auth():
    """Xác thực mã PIN Giảng viên và cấp phiên đăng nhập (D20)"""
    data = request.json or {}
    pin = str(data.get("pin", "")).strip()
    if _matches_teacher_pin(pin):
        session["is_teacher_auth"] = True
        return jsonify({
            "success": True,
            "message": "Xác thực Giảng viên thành công!"
        })
    return jsonify({
        "success": False,
        "error": "Mã PIN Giảng viên không chính xác!"
    }), 401

@teacher_bp.route("/api/teacher/logout", methods=["POST"])
def teacher_logout():
    """Đăng xuất phiên làm việc của Giảng viên (D20)"""
    session.pop("is_teacher_auth", None)
    return jsonify({
        "success": True,
        "message": "Đã đăng xuất khỏi Bàn làm việc Giảng viên."
    })

@teacher_bp.route("/api/teacher/auth-status", methods=["GET"])
def teacher_auth_status():
    """Kiểm tra trạng thái đăng nhập Giảng viên thời gian thực"""
    is_auth = is_teacher_authenticated()
    return jsonify({
        "authenticated": is_auth
    })


@teacher_bp.route("/gv")
@teacher_bp.route("/quan-tri")
@teacher_bp.route("/teacher")
@teacher_bp.route("/admin")
def teacher_portal():
    """Giao diện Bàn làm việc & Dashboard Quản trị Khảo thí dành cho Giảng viên (/quan-tri)"""
    state = get_session_state()
    active_doc_type = state.get("active_doc_type", "cong_van_de_nghi")
    # Render teacher.html chuyên biệt, an toàn và tối ưu tải trang
    return render_template("teacher.html", mode="teacher", active_doc_type=active_doc_type)

VALID_DOC_TYPES = [
    "cong_van_de_nghi", "thong_bao_nhiem_vu", "thong_bao_hoat_dong",
    "to_trinh_xin_kinh_phi", "to_trinh_nhan_su", "to_trinh_thiet_bi",
    "bao_cao", "bai_thu_hoach"
]

def _parse_strict_bool(val: Any, field_name: str) -> bool:
    """Xác thực kiểu boolean nghiêm ngặt cho cấu hình phòng học (R2 11)"""
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and val in (0, 1):
        return bool(val)
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1"):
            return True
        if v in ("false", "0"):
            return False
    raise ValueError(f"Trường [{field_name}] phải có kiểu giá trị boolean thực (True/False)")

@teacher_bp.route("/api/teacher/session-state", methods=["POST"])
@require_teacher_auth
def api_set_session_state():
    """Bật / Tắt trạng thái làm bài (Khóa khi giảng lý thuyết, mở khi cho phép làm bài - D30, R2 11)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code", ""), "").upper()
    current = get_session_state(class_code)

    try:
        new_is_open = current.get("is_open", False)
        if "is_open" in data:
            new_is_open = _parse_strict_bool(data["is_open"], "is_open")

        enforce_roster = current.get("enforce_roster", True)
        if "enforce_roster" in data:
            enforce_roster = _parse_strict_bool(data["enforce_roster"], "enforce_roster")

        enforce_quiz = current.get("enforce_quiz", True)
        if "enforce_quiz" in data:
            enforce_quiz = _parse_strict_bool(data["enforce_quiz"], "enforce_quiz")

        enforce_preview_limit = current.get("enforce_preview_limit", False)
        if "enforce_preview_limit" in data:
            enforce_preview_limit = _parse_strict_bool(data["enforce_preview_limit"], "enforce_preview_limit")

        enable_anti_cheat = current.get("enable_anti_cheat", False)
        if "enable_anti_cheat" in data:
            enable_anti_cheat = _parse_strict_bool(data["enable_anti_cheat"], "enable_anti_cheat")

        max_previews = current.get("max_previews", 3)
        if "max_previews" in data:
            raw_mp = data["max_previews"]
            if not isinstance(raw_mp, int) or isinstance(raw_mp, bool):
                try:
                    raw_mp = int(raw_mp)
                except (ValueError, TypeError):
                    raise ValueError("Trường [max_previews] phải là số nguyên hợp lệ trong khoảng 1 đến 100")
            if raw_mp < 1 or raw_mp > 100:
                raise ValueError("Trường [max_previews] giới hạn trong khoảng từ 1 đến 100 lần thẩm định")
            max_previews = raw_mp

        active_doc_type = current.get("active_doc_type", "cong_van_de_nghi")
        if "active_doc_type" in data:
            raw_dt = str(data["active_doc_type"]).strip()
            if raw_dt and raw_dt not in VALID_DOC_TYPES:
                raise ValueError(f"Loại văn bản [{raw_dt}] không nằm trong danh mục chuẩn của hệ thống")
            if raw_dt:
                active_doc_type = raw_dt

        new_message = current.get("message", "")
        if "message" in data:
            new_message = str(data["message"]).strip()
    except ValueError as ve:
        return jsonify({"error": str(ve), "invalid_field": True}), 400
    
    updated_state = {
        "is_open": new_is_open,
        "enforce_roster": enforce_roster,
        "active_doc_type": active_doc_type,
        "enforce_quiz": enforce_quiz,
        "max_previews": max_previews,
        "enforce_preview_limit": enforce_preview_limit,
        "enable_anti_cheat": enable_anti_cheat,
        "message": new_message,
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_session_state(updated_state, class_code)
    return jsonify({
        "success": True,
        "class_code": class_code or "ALL",
        "session_state": updated_state,
        "message": "Đã mở quyền làm bài cho sinh viên!" if new_is_open else "Đã khóa hệ thống để sinh viên tập trung nghe giảng!"
    })

@teacher_bp.route("/api/teacher/set-active-doc", methods=["POST"])
@require_teacher_auth
def api_set_active_doc():
    """Chuyển loại văn bản bài tập giao cho sinh viên làm trong ca học (D30)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code", ""), "").upper()
    doc_type = str(data.get("doc_type", "")).strip()
    if not doc_type:
        return jsonify({"error": "Vui lòng chọn loại văn bản hợp lệ!"}), 400
    state = get_session_state(class_code)
    state["active_doc_type"] = doc_type
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_session_state(state, class_code)
    return jsonify({
        "success": True,
        "class_code": class_code or "ALL",
        "active_doc_type": doc_type,
        "session_state": state,
        "message": f"Đã chuyển loại văn bản giao làm bài sang: [{doc_type}]"
    })

@teacher_bp.route("/api/teacher/roster-toggle", methods=["POST"])
@require_teacher_auth
def toggle_roster_mode():
    """Bật / Tắt chế độ bắt buộc sinh viên phải có tên trong danh sách lớp (D30)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code", ""), "").upper()
    state = get_session_state(class_code)
    if "enforce_roster" in data:
        state["enforce_roster"] = bool(data["enforce_roster"])
    else:
        state["enforce_roster"] = not state.get("enforce_roster", True)
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_session_state(state, class_code)
    return jsonify({
        "success": True,
        "class_code": class_code or "ALL",
        "enforce_roster": state["enforce_roster"],
        "message": "Đã BẬT kiểm tra danh sách lớp (chỉ sinh viên trong danh sách mới được làm bài)!" if state["enforce_roster"] else "Đã TẮT kiểm tra danh sách (mở tự do cho mọi sinh viên)."
    })

@teacher_bp.route("/api/teacher/anti-cheat-toggle", methods=["POST"])
@require_teacher_auth
def toggle_anti_cheat_mode():
    """Bật / Tắt chế độ kiểm tra chống sao chép và gian lận (Anti-Cheat - D07, D30)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code", ""), "").upper()
    state = get_session_state(class_code)
    if "enable_anti_cheat" in data:
        state["enable_anti_cheat"] = bool(data["enable_anti_cheat"])
    else:
        state["enable_anti_cheat"] = not state.get("enable_anti_cheat", False)
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_session_state(state, class_code)
    return jsonify({
        "success": True,
        "class_code": class_code or "ALL",
        "enable_anti_cheat": state["enable_anti_cheat"],
        "message": "Đã BẬT kiểm tra chống sao chép gian lận!" if state["enable_anti_cheat"] else "Đã TẮT toàn bộ kiểm tra copy (cho phép sinh viên nộp bài kiểm tra thể thức tự do)."
    })

@teacher_bp.route("/api/teacher/students", methods=["GET"])
@require_teacher_auth
def get_teacher_students():
    """Lấy danh sách sinh viên của một lớp hoặc tất cả các lớp"""
    class_code = str(request.args.get("class_code", "")).strip().upper()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code and class_code != "ALL":
        students = roster.get(class_code, [])
        return jsonify({
            "class_code": class_code,
            "total": len(students),
            "students": students
        })
    else:
        total_all = sum(len(lst) for lst in roster.values())
        return jsonify({
            "class_code": "ALL",
            "total": total_all,
            "roster": roster
        })

@teacher_bp.route("/api/teacher/students/add", methods=["POST"])
@require_teacher_auth
def add_student_to_roster():
    """Thêm một sinh viên vào danh sách lớp"""
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    sbd = str(data.get("sbd", "")).strip()
    mssv = str(data.get("mssv", "")).strip()
    name = str(data.get("name", "")).strip()
    student_class = str(data.get("student_class", "")).strip().upper()

    if not class_code or not mssv or not name:
        return jsonify({"error": "Vui lòng nhập đầy đủ Mã lớp, MSSV và Họ và tên sinh viên!"}), 400

    mssv = re.sub(r'[^a-zA-Z0-9]', '', mssv).strip().upper()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code not in roster:
        roster[class_code] = []

    for s in roster[class_code]:
        if s.get("mssv", "").strip().upper() == mssv:
            s["sbd"] = sbd or s.get("sbd", "")
            s["name"] = name
            if student_class:
                s["student_class"] = student_class
            save_json_file(STUDENTS_ROSTER_FILE, roster)
            return jsonify({
                "success": True,
                "message": f"Đã cập nhật thông tin sinh viên MSSV [{mssv}] trong lớp [{class_code}]!",
                "student": s,
                "total": len(roster[class_code])
            })

    new_student = {
        "sbd": sbd,
        "mssv": mssv,
        "name": name,
        "student_class": student_class
    }
    roster[class_code].append(new_student)
    save_json_file(STUDENTS_ROSTER_FILE, roster)
    return jsonify({
        "success": True,
        "message": f"Đã thêm thành công sinh viên [{name}] ({mssv}) vào lớp [{class_code}]!",
        "student": new_student,
        "total": len(roster[class_code])
    })

@teacher_bp.route("/api/teacher/students/import", methods=["POST"])
@require_teacher_auth
def import_students_batch():
    """Nhập danh sách sinh viên hàng loạt từ Excel / Text"""
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    raw_text = str(data.get("raw_text", "")).strip()
    overwrite = bool(data.get("overwrite", False))

    if not class_code or not raw_text:
        return jsonify({"error": "Vui lòng chọn Mã lớp và dán danh sách sinh viên!"}), 400

    parsed = parse_students_text(raw_text)
    if not parsed:
        return jsonify({"error": "Không thể phân tích dữ liệu danh sách. Vui lòng kiểm tra định dạng!"}), 400

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code not in roster or overwrite:
        roster[class_code] = []

    existing_mssvs = {s["mssv"].upper(): s for s in roster[class_code]}
    added_count = 0
    updated_count = 0

    for item in parsed:
        m = item["mssv"].upper()
        if m in existing_mssvs:
            existing_mssvs[m]["name"] = item["name"]
            if item["sbd"]:
                existing_mssvs[m]["sbd"] = item["sbd"]
            if item.get("student_class"):
                existing_mssvs[m]["student_class"] = item["student_class"]
            updated_count += 1
        else:
            roster[class_code].append(item)
            existing_mssvs[m] = item
            added_count += 1

    save_json_file(STUDENTS_ROSTER_FILE, roster)

    # Đảm bảo mã lớp có trong classes.json
    classes_data = load_json_file(CLASSES_FILE, {"classes": []})
    c_list = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    if class_code not in c_list:
        c_list.append(class_code)
        save_json_file(CLASSES_FILE, {"classes": c_list})

    return jsonify({
        "success": True,
        "message": f"Nhập danh sách thành công cho lớp [{class_code}]: Thêm mới {added_count} SV, Cập nhật {updated_count} SV.",
        "added": added_count,
        "added_count": added_count,
        "updated": updated_count,
        "updated_count": updated_count,
        "total": len(roster[class_code]),
        "students": roster[class_code]
    })

@teacher_bp.route("/api/teacher/students/delete", methods=["POST"])
@require_teacher_auth
def delete_student_from_roster():
    """Xóa một sinh viên khỏi danh sách lớp"""
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    mssv = str(data.get("mssv", "")).strip().upper()

    if not class_code or not mssv:
        return jsonify({"error": "Thiếu mã lớp hoặc MSSV cần xóa!"}), 400

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code in roster:
        orig = len(roster[class_code])
        roster[class_code] = [s for s in roster[class_code] if s.get("mssv", "").strip().upper() != mssv]
        if len(roster[class_code]) < orig:
            save_json_file(STUDENTS_ROSTER_FILE, roster)
            return jsonify({
                "success": True,
                "message": f"Đã xóa sinh viên [{mssv}] khỏi lớp [{class_code}]!",
                "total": len(roster[class_code])
            })

    return jsonify({"error": f"Không tìm thấy sinh viên [{mssv}] trong lớp [{class_code}]!"}), 404

@teacher_bp.route("/api/teacher/students/clear", methods=["POST"])
@require_teacher_auth
def clear_class_roster():
    """Xóa toàn bộ sinh viên của một lớp"""
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    if not class_code:
        return jsonify({"error": "Thiếu mã lớp cần làm trống!"}), 400

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code in roster:
        del roster[class_code]
        save_json_file(STUDENTS_ROSTER_FILE, roster)

    return jsonify({"success": True, "message": f"Đã xóa sạch toàn bộ danh sách lớp [{class_code}]!"})

@teacher_bp.route("/api/classes/add", methods=["POST"])
@require_teacher_auth
def add_class():
    """Thêm mã lớp học kỹ năng mới"""
    data = request.json or {}
    code = str(data.get("class_code", "")).strip().upper()
    if not code:
        return jsonify({"error": "Mã lớp không được để trống!"}), 400

    classes_data = load_json_file(CLASSES_FILE, {"classes": []})
    c_list = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    if code in c_list:
        return jsonify({"error": f"Mã lớp {code} đã tồn tại!"}), 400

    c_list.append(code)
    c_list.sort()
    save_json_file(CLASSES_FILE, {"classes": c_list})
    return jsonify({"success": True, "classes": c_list, "message": f"Đã thêm lớp {code} thành công!"})

@teacher_bp.route("/api/classes/delete", methods=["POST"])
@require_teacher_auth
def delete_class():
    """Xóa một mã lớp học kỹ năng (bao gồm cả mã lớp và danh sách sinh viên của lớp)"""
    data = request.json or {}
    code = str(data.get("class_code", "")).strip().upper()
    if not code:
        return jsonify({"error": "Vui lòng cung cấp mã lớp cần xóa!"}), 400

    classes_data = load_json_file(CLASSES_FILE, {"classes": []})
    c_list = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})

    found = False
    if code in c_list:
        c_list.remove(code)
        save_json_file(CLASSES_FILE, {"classes": c_list})
        found = True

    if code in roster:
        del roster[code]
        save_json_file(STUDENTS_ROSTER_FILE, roster)
        found = True

    if found:
        return jsonify({"success": True, "classes": c_list, "message": f"Đã xóa hoàn toàn lớp {code}!"})
    return jsonify({"error": f"Không tìm thấy lớp {code}!"}), 404

@teacher_bp.route("/api/teacher/data", methods=["GET"])
@require_teacher_auth
def teacher_data():
    """Lấy dữ liệu tổng hợp từ SQLite phục vụ Bàn làm việc Giảng viên (giao với quyền lớp - R2 03)"""
    submissions = get_all_submissions()
    fraud_logs = get_all_fraud_logs()
    classes_data = load_json_file(CLASSES_FILE, {"classes": ["KN01", "KN02", "KN03", "KN04", "KN05"]})
    classes = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    session_state = get_session_state()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})

    allowed_list = get_teacher_allowed_classes()
    if allowed_list is not None:
        submissions = [s for s in submissions if str(s.get("class_code", "")).strip().upper() in allowed_list]
        fraud_logs = [f for f in fraud_logs if str(f.get("class_code", "")).strip().upper() in allowed_list]
        classes = [c for c in classes if str(c).strip().upper() in allowed_list]
        roster = {c: stus for c, stus in roster.items() if str(c).strip().upper() in allowed_list}

    total_roster_students = sum(len(s_list) for s_list in roster.values())
    t_data = get_teachers_data()
    active_teacher = get_active_teacher()

    return jsonify({
        "submissions": submissions,
        "fraud_logs": fraud_logs,
        "classes": classes,
        "session_state": session_state,
        "students_roster": roster,
        "total_roster_students": total_roster_students,
        "teachers": t_data.get("teachers", []),
        "active_teacher": active_teacher,
        "active_teacher_id": t_data.get("active_teacher_id", active_teacher.get("id"))
    })

@teacher_bp.route("/api/download/submitted/<path:filename>")
@require_teacher_auth
def download_submitted(filename):
    """Tải tệp bài nộp chính thức của sinh viên"""
    try:
        path = safe_storage_path(STORAGE_SUBMITTED, filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp không hợp lệ!"}), 400
    if os.path.exists(path) and os.path.isfile(path):
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))
    return "File không tồn tại", 404

@teacher_bp.route("/api/teacher/export-csv", methods=["GET"])
@require_teacher_auth
def export_csv():
    """Xuất bảng điểm bài tập ra định dạng CSV có UTF-8 BOM hiển thị chuẩn trong Excel (R2 03)"""
    class_filter = sanitize_identifier(request.args.get("class_code", "ALL"), "ALL").upper()
    allowed, actor = check_teacher_class_access(class_filter)
    if not allowed:
        return jsonify({"error": f"Giảng viên {actor} không có quyền xuất bảng điểm lớp {class_filter}!"}), 403
    allowed_list = get_teacher_allowed_classes()
    if allowed_list is not None and class_filter == "ALL":
        submissions = [s for s in get_all_submissions() if str(s.get("class_code", "")).strip().upper() in allowed_list]
    else:
        submissions = get_all_submissions(class_code=class_filter)
        
    output = io.StringIO()
    output.write('\ufeff')
    csv_writer = csv.writer(output)

    def write_row(values):
        # Quoting CSV fields does not stop spreadsheet formula execution.
        csv_writer.writerow([
            "'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
            else value for value in values
        ])
    
    active_teacher = get_active_teacher()
    teacher_name = active_teacher.get("name", "Giảng viên bộ môn")
    dept = active_teacher.get("department", "Quản trị văn phòng")
    
    write_row(["BẢNG ĐIỂM BÀI TẬP SOẠN THẢO VĂN BẢN (NGHỊ ĐỊNH 30/2020/NĐ-CP)"])
    write_row([f"Giảng viên phụ trách: {teacher_name} ({dept})", f"Lớp: {class_filter}", f"Thời gian xuất: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    write_row([])
    write_row([
        "STT", "Mã lớp KN", "Số báo danh (SBD)", "Mã số sinh viên (MSSV)", "Họ và tên",
        "Loại văn bản bài tập", "Tên file nộp", "Thời gian nộp", "Thời gian làm bài", "Số lần kiểm tra thử", "Cảnh báo gian lận / đối phó", "Kết quả thẩm định", "Điểm số quy đổi"
    ])
    
    for idx, s in enumerate(submissions):
        flag_text = ", ".join(s.get("flags", [])) if s.get("flags") else ("🚩 Nộp quá nhanh (< 2p)" if s.get("is_suspicious_speed") else "Bình thường")
        write_row([
            idx + 1,
            s.get("class_code", "Chung"),
            s.get("sbd", ""),
            s.get("mssv", ""),
            s.get("name", ""),
            s.get("doc_name", s.get("doc_type", "")),
            s.get("filename", ""),
            s.get("submitted_at", ""),
            s.get("elapsed_time", "N/A"),
            s.get("preview_count", 0),
            flag_text,
            s.get("status", "Hoàn thành 100% Nghị định 30"),
            f"{float(s.get('score', 10.0)):.1f} / 10"
        ])
        
    csv_data = output.getvalue()
    filename = f"Bang_Diem_STVB_{class_filter}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@teacher_bp.route("/api/teacher/submissions/delete", methods=["POST"])
@require_teacher_auth
def delete_teacher_submission():
    """Xóa bài nộp của sinh viên khỏi SQLite (hỗ trợ phân lập mã lớp - R2 01, D08)"""
    data = request.json or {}
    mssv = str(data.get("mssv", "")).strip()
    doc_type = str(data.get("doc_type", "")).strip()
    class_code = sanitize_identifier(data.get("class_code", ""), "").upper()
    if not mssv or not doc_type or not class_code or class_code == "ALL":
        return jsonify({"error": "Thiếu thông tin xác thực bài nộp cần xóa (cần class_code cụ thể, mssv, doc_type)!"}), 400

    allowed, actor = check_teacher_class_access(class_code)
    if not allowed:
        return jsonify({"error": f"Giảng viên {actor} không có quyền quản lý bài nộp của lớp {class_code}!"}), 403

    try:
        deleted = delete_submission_by_mssv(mssv, doc_type, class_code=class_code)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    if not deleted:
        return jsonify({"success": False, "error": f"Không tìm thấy bài nộp của MSSV {mssv} thuộc lớp {class_code} cho loại văn bản {doc_type}!"}), 404

    return jsonify({"success": True, "message": f"Đã xóa bài nộp của MSSV {mssv} thuộc lớp {class_code}!"})

@teacher_bp.route("/api/teacher/fraud/delete", methods=["POST"])
@require_teacher_auth
def delete_fraud_log():
    """Xóa một bản ghi nhật ký gian lận khỏi SQLite"""
    data = request.json or {}
    log_id = str(data.get("id", "")).strip()
    if not log_id:
        return jsonify({"error": "Thiếu mã bản ghi vi phạm cần xóa!"}), 400
    
    deleted = delete_fraud_log_by_id(log_id)
    return jsonify({"success": True, "message": "Đã xóa biên bản vi phạm thành công!"})

@teacher_bp.route("/api/teacher/fraud/clear", methods=["POST"])
@require_teacher_auth
def clear_fraud_logs():
    """Xóa toàn bộ nhật ký gian lận khỏi SQLite"""
    clear_all_fraud_logs()
    return jsonify({"success": True, "message": "Đã xóa toàn bộ nhật ký vi phạm của hệ thống!"})

@teacher_bp.route("/api/teacher/templates", methods=["GET"])
@require_teacher_auth
def teacher_templates():
    """Lấy danh sách các mẫu văn bản gốc để giảng viên tùy chỉnh"""
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    return jsonify(templates_data)

@teacher_bp.route("/api/teacher/templates/save", methods=["POST"])
@require_teacher_auth
def save_teacher_template():
    """Lưu cập nhật nội dung bài tập của văn bản (R2 10, R2 21)"""
    data = request.json or {}
    doc_type = str(data.get("doc_type", "")).strip()
    tmpl_path = os.path.join(DATA_DIR, "document_templates.json")

    def _updater(templates_data):
        if doc_type not in templates_data:
            return False, "Không tìm thấy loại văn bản!"

        if "is_body_blank" in data:
            templates_data[doc_type]["is_body_blank"] = bool(data["is_body_blank"])

        # R2 10: Phân biệt trường có mặt trong payload (kể cả chuỗi rỗng) với trường bị bỏ qua
        if "header_part" in data:
            templates_data[doc_type]["header_part"] = str(data["header_part"]).strip()
        if "body_part" in data:
            templates_data[doc_type]["body_part"] = str(data["body_part"]).strip()
        if "footer_part" in data:
            templates_data[doc_type]["footer_part"] = str(data["footer_part"]).strip()

        h = templates_data[doc_type].get("header_part", "")
        b = templates_data[doc_type].get("body_part", "")
        f = templates_data[doc_type].get("footer_part", "")
        placeholder = "[Nội dung văn bản: Sinh viên tự giả định nội dung theo thực tế bài giảng, không tuân thủ đề cố định. Sơ đồ bố trí bắt buộc tuân thủ Sơ đồ Công văn (Hình 2 theo Nghị định 30)]"
        actual_b = placeholder if templates_data[doc_type].get("is_body_blank") else b
        templates_data[doc_type]["raw_text"] = f"{h}\n\n{actual_b}\n\n{f}".strip()
        return True, "Đã lưu cập nhật nội dung bài tập thành công!"

    success, msg = update_json_atomic(tmpl_path, _updater, {})
    if not success:
        return jsonify({"error": msg}), 404
    return jsonify({"success": True, "message": msg})

@teacher_bp.route("/api/teacher/quiz/<doc_type>", methods=["GET"])
@require_teacher_auth
def get_teacher_quiz(doc_type):
    """Lấy ngân hàng câu hỏi trắc nghiệm của một loại văn bản"""
    all_questions = load_json_file(QUESTIONS_FILE, {})
    questions = all_questions.get(doc_type, [])
    return jsonify({"questions": questions, "doc_type": doc_type, "total": len(questions)})

@teacher_bp.route("/api/teacher/quiz/save", methods=["POST"])
@require_teacher_auth
def save_teacher_quiz():
    """Lưu hoặc cập nhật câu hỏi trắc nghiệm"""
    data = request.json or {}
    doc_type = data.get("doc_type")
    q_id = data.get("id")
    question_text = str(data.get("question", "")).strip()
    options = data.get("options", [])
    correct = data.get("correct")
    explanation = str(data.get("explanation", "")).strip()

    if not doc_type or not question_text or correct is None:
        return jsonify({"error": "Vui lòng nhập đầy đủ loại đề thi, nội dung câu hỏi và chọn đáp án đúng!"}), 400

    # D13: Ràng buộc tính hợp lệ của câu hỏi và đáp án
    if not isinstance(options, list) or len(options) < 2:
        return jsonify({"error": "Danh sách phương án phải có tối thiểu 2 phương án!"}), 400

    clean_options = [str(opt).strip() for opt in options]
    if any(not opt for opt in clean_options):
        return jsonify({"error": "Nội dung các phương án trả lời không được để trống!"}), 400

    try:
        correct = int(correct)
    except Exception:
        return jsonify({"error": "Chỉ số đáp án đúng phải là số nguyên!"}), 400

    if correct < 0 or correct >= len(clean_options):
        return jsonify({"error": f"Chỉ số đáp án đúng ({correct}) vượt quá phạm vi số lượng phương án (0 đến {len(clean_options) - 1})!"}), 400

    all_questions = load_json_file(QUESTIONS_FILE, {})
    if doc_type not in all_questions:
        all_questions[doc_type] = []

    q_list = all_questions[doc_type]

    if q_id is not None:
        try:
            q_id = int(q_id)
        except Exception:
            pass
        found = False
        for q in q_list:
            if q["id"] == q_id:
                q["question"] = question_text
                q["options"] = [str(opt).strip() for opt in options]
                q["correct"] = correct
                q["explanation"] = explanation
                found = True
                break
        if not found:
            new_id = max([q["id"] for q in q_list], default=0) + 1
            q_list.append({
                "id": new_id,
                "question": question_text,
                "options": [str(opt).strip() for opt in options],
                "correct": correct,
                "explanation": explanation
            })
    else:
        new_id = max([q["id"] for q in q_list], default=0) + 1
        q_list.append({
            "id": new_id,
            "question": question_text,
            "options": [str(opt).strip() for opt in options],
            "correct": correct,
            "explanation": explanation
        })

    all_questions[doc_type] = q_list
    save_json_file(QUESTIONS_FILE, all_questions)
    return jsonify({"success": True, "message": "Đã lưu câu hỏi trắc nghiệm thành công!", "questions": q_list})

@teacher_bp.route("/api/teacher/quiz/delete", methods=["POST"])
@require_teacher_auth
def delete_teacher_quiz():
    """Xóa câu hỏi trắc nghiệm"""
    data = request.json or {}
    doc_type = data.get("doc_type")
    q_id = data.get("id")

    if not doc_type or q_id is None:
        return jsonify({"error": "Thiếu thông tin câu hỏi cần xóa!"}), 400

    try:
        q_id = int(q_id)
    except Exception:
        pass

    all_questions = load_json_file(QUESTIONS_FILE, {})
    if doc_type in all_questions:
        all_questions[doc_type] = [q for q in all_questions[doc_type] if q["id"] != q_id]
        save_json_file(QUESTIONS_FILE, all_questions)
        return jsonify({"success": True, "message": "Đã xóa câu hỏi!", "questions": all_questions[doc_type]})

    return jsonify({"error": "Không tìm thấy loại văn bản này!"}), 404


# =========================================================================
# API QUẢN LÝ DANH SÁCH & HỒ SƠ GIẢNG VIÊN (MULTI-TEACHER SUPPORT)
# =========================================================================
@teacher_bp.route("/api/teacher/teachers", methods=["GET"])
@require_teacher_auth
def api_get_teachers():
    """Lấy danh sách tất cả giảng viên và giảng viên đang làm việc"""
    t_data = get_teachers_data()
    active_teacher = get_active_teacher()
    return jsonify({
        "teachers": t_data.get("teachers", []),
        "active_teacher": active_teacher,
        "active_teacher_id": t_data.get("active_teacher_id", active_teacher.get("id"))
    })

@teacher_bp.route("/api/teacher/teachers/select", methods=["POST"])
@require_teacher_auth
def api_select_teacher():
    """Giảng viên chọn hồ sơ / tài khoản làm việc hiện tại"""
    data = request.json or {}
    teacher_id = str(data.get("id", "")).strip()
    if not teacher_id:
        return jsonify({"error": "Vui lòng chọn Giảng viên!"}), 400
    
    teacher = set_active_teacher(teacher_id)
    if teacher:
        return jsonify({
            "success": True,
            "message": f"Đã chuyển sang giảng viên: {teacher.get('name')}",
            "active_teacher": teacher
        })
    return jsonify({"error": f"Không tìm thấy giảng viên có mã {teacher_id}!"}), 404

@teacher_bp.route("/api/teacher/teachers/save", methods=["POST"])
@require_teacher_auth
def api_save_teacher():
    """Thêm mới hoặc cập nhật thông tin giảng viên"""
    data = request.json or {}
    t_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    title = str(data.get("title", "")).strip()
    department = str(data.get("department", "")).strip()
    email = str(data.get("email", "")).strip()
    phone = str(data.get("phone", "")).strip()

    if not name:
        return jsonify({"error": "Vui lòng nhập Họ và tên Giảng viên!"}), 400

    t_data = get_teachers_data()
    t_list = t_data.get("teachers", [])

    if t_id:
        found = False
        for t in t_list:
            if t["id"] == t_id:
                t["name"] = name
                t["title"] = title
                t["department"] = department
                t["email"] = email
                t["phone"] = phone
                found = True
                saved_teacher = t
                break
        if not found:
            saved_teacher = {
                "id": t_id,
                "name": name,
                "title": title,
                "department": department,
                "email": email,
                "phone": phone
            }
            t_list.append(saved_teacher)
    else:
        # Tự động sinh ID mới: GV01, GV02, ...
        existing_nums = []
        for t in t_list:
            match = re.search(r"\d+", t.get("id", ""))
            if match:
                existing_nums.append(int(match.group()))
        next_num = max(existing_nums, default=0) + 1
        new_id = f"GV{next_num:02d}"
        saved_teacher = {
            "id": new_id,
            "name": name,
            "title": title,
            "department": department,
            "email": email,
            "phone": phone
        }
        t_list.append(saved_teacher)

    t_data["teachers"] = t_list
    save_json_file(TEACHERS_FILE, t_data)
    
    # Nếu đang chọn giảng viên này thì cập nhật luôn session_state
    if t_data.get("active_teacher_id") == saved_teacher["id"]:
        state = get_session_state()
        state["active_teacher"] = saved_teacher["name"]
        save_session_state(state)

    return jsonify({
        "success": True,
        "message": f"Đã lưu giảng viên {name} thành công!",
        "teacher": saved_teacher,
        "teachers": t_list
    })

@teacher_bp.route("/api/teacher/teachers/delete", methods=["POST"])
@require_teacher_auth
def api_delete_teacher():
    """Xóa giảng viên khỏi danh sách"""
    data = request.json or {}
    t_id = str(data.get("id", "")).strip()
    if not t_id:
        return jsonify({"error": "Thiếu mã giảng viên cần xóa!"}), 400

    t_data = get_teachers_data()
    t_list = t_data.get("teachers", [])

    if len(t_list) <= 1:
        return jsonify({"error": "Hệ thống cần tối thiểu 1 Giảng viên, không thể xóa giảng viên cuối cùng!"}), 400

    new_list = [t for t in t_list if t.get("id") != t_id]
    if len(new_list) == len(t_list):
        return jsonify({"error": "Không tìm thấy giảng viên cần xóa!"}), 404

    t_data["teachers"] = new_list
    # Nếu xóa đúng giảng viên đang active thì chọn người đầu tiên
    if t_data.get("active_teacher_id") == t_id:
        t_data["active_teacher_id"] = new_list[0]["id"]
        state = get_session_state()
        state["active_teacher"] = new_list[0]["name"]
        state["active_teacher_id"] = new_list[0]["id"]
        save_session_state(state)

    save_json_file(TEACHERS_FILE, t_data)
    return jsonify({
        "success": True,
        "message": "Đã xóa giảng viên!",
        "teachers": new_list,
        "active_teacher_id": t_data.get("active_teacher_id")
    })

@teacher_bp.route("/api/tunnel-info", methods=["GET"])
def api_tunnel_info():
    """Lấy thông tin Link Trực tuyến (Cloudflare Tunnel) và Link LAN để gửi cho Sinh viên"""
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    tunnel_file = os.path.join(DATA_DIR, "tunnel_info.json")
    tunnel_data = load_json_file(tunnel_file, {})
    public_url = tunnel_data.get("public_url", "")

    return jsonify({
        "local_ip": local_ip,
        "local_url": f"http://{local_ip}:5000",
        "student_local_url": f"http://{local_ip}:5000/thi",
        "public_url": public_url,
        "student_public_url": f"{public_url}/thi" if public_url else ""
    })

# =========================================================================
# QUẢN TRỊ CƠ SỞ DỮ LIỆU & SAO LƯU / PHỤC HỒI (D24)
# =========================================================================
@teacher_bp.route("/api/teacher/database/backup", methods=["POST"])
@require_teacher_auth
def api_backup_database():
    """Tạo bản sao lưu nóng cơ sở dữ liệu SQLite (D24)"""
    try:
        backup_file = backup_database()
        return jsonify({
            "success": True,
            "backup_file": os.path.basename(backup_file),
            "message": f"Đã sao lưu cơ sở dữ liệu thành công: {os.path.basename(backup_file)}"
        })
    except Exception as e:
        return jsonify({"error": f"Lỗi khi sao lưu cơ sở dữ liệu: {str(e)}"}), 500

@teacher_bp.route("/api/teacher/database/download", methods=["GET"])
@require_teacher_auth
def api_download_database():
    """Tải xuống bản sao lưu snapshot nhất quán của cơ sở dữ liệu SQLite edudoc.db (R2 04, Priority 6)"""
    try:
        backup_file = backup_database()
        from flask import send_file
        return send_file(backup_file, as_attachment=True, download_name="edudoc.db")
    except Exception as e:
        return jsonify({"error": f"Không thể tạo snapshot cơ sở dữ liệu để tải xuống: {str(e)}"}), 500

@teacher_bp.route("/api/teacher/database/backups", methods=["GET"])
@require_teacher_auth
def api_list_backups():
    """Lấy danh sách các bản sao lưu cơ sở dữ liệu (D24)"""
    backups = list_backups()
    return jsonify({
        "success": True,
        "total": len(backups),
        "backups": backups
    })

@teacher_bp.route("/api/teacher/database/restore", methods=["POST"])
@require_teacher_auth
def api_restore_database():
    """Khôi phục cơ sở dữ liệu từ bản sao lưu (D24)"""
    data = request.json or {}
    raw_fn = os.path.basename(str(data.get("filename", "")).strip())
    filename = re.sub(r'[\/*?:"<>|]', '', raw_fn)
    if not filename or not filename.endswith(".db"):
        return jsonify({"error": "Tên tệp sao lưu không hợp lệ!"}), 400

    backup_dir = os.path.join(DATA_DIR, "backups")
    try:
        backup_path = safe_storage_path(backup_dir, filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp sao lưu không an toàn!"}), 400

    if not os.path.exists(backup_path):
        return jsonify({"error": f"Không tìm thấy bản sao lưu: {filename}"}), 404

    try:
        restore_database(backup_path)
        return jsonify({
            "success": True,
            "message": f"Đã khôi phục cơ sở dữ liệu thành công từ: {filename}"
        })
    except Exception as e:
        return jsonify({"error": f"Lỗi khi khôi phục cơ sở dữ liệu: {str(e)}"}), 500

# =========================================================================
# NHẬT KÝ THẨM ĐỊNH THỬ - VALIDATION LOGS (D02)
# =========================================================================
@teacher_bp.route("/api/teacher/validation-logs", methods=["GET"])
@require_teacher_auth
def api_get_validation_logs():
    """Lấy danh sách nhật ký thẩm định thử của sinh viên (D02)"""
    class_code = sanitize_identifier(request.args.get("class_code", ""), "").upper()
    mssv = sanitize_identifier(request.args.get("mssv", ""), "")
    logs = get_validation_logs(class_code=class_code or None, mssv=mssv or None)
    return jsonify({
        "success": True,
        "total": len(logs),
        "logs": logs
    })

# =========================================================================
# THỐNG KÊ LỖI THỰC TẾ TỪ CƠ SỞ DỮ LIỆU BÀI NỘP - REAL ANALYTICS (D19)
# =========================================================================
_ANALYTICS_CACHE = {}

@teacher_bp.route("/api/teacher/analytics", methods=["GET"])
@require_teacher_auth
def api_get_analytics():
    """
    D19: Thống kê lỗi thực tế từ cơ sở dữ liệu bài nộp sinh viên:
    - Tính toán tỷ lệ đạt theo từng nhóm thể thức thực tế
    - Thống kê top các lỗi vi phạm phổ biến nhất từ bài nộp
    - Hỗ trợ lọc theo mã lớp (class_code)
    - Trả về has_data=False nếu chưa đủ dữ liệu
    """
    from engine.validator import Decree30Validator
    
    class_code = sanitize_identifier(request.args.get("class_code", ""), "").upper()
    all_subs = get_all_submissions()
    
    if class_code and class_code != "ALL":
        subs = [s for s in all_subs if s.get("class_code") == class_code]
    else:
        subs = all_subs

    total = len(subs)
    if total == 0:
        return jsonify({
            "success": True,
            "has_data": False,
            "message": "Chưa có đủ dữ liệu thống kê từ bài nộp sinh viên cho bộ lọc này.",
            "total_submissions": 0,
            "avg_score": 0.0,
            "group_stats": [],
            "top_errors": []
        })

    # Tính điểm trung bình thực tế
    total_score = sum(float(s.get("score") or 0.0) for s in subs)
    avg_score = round(total_score / total, 1) if total > 0 else 0.0

    group_counts = {
        1: {"name": "Khổ giấy & Căn lề", "passed": 0, "total": 0},
        2: {"name": "Quốc hiệu, Tên CQ & Số/KH", "passed": 0, "total": 0},
        3: {"name": "Nội dung & Bảng biểu", "passed": 0, "total": 0},
        4: {"name": "Chữ ký & Nơi nhận", "passed": 0, "total": 0}
    }
    
    missing_evidence_count = 0
    error_freq = {}
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})

    for s in subs:
        fn = s.get("filename", "")
        doc_type = s.get("doc_type", "bai_thu_hoach")
        fp = os.path.join(STORAGE_SUBMITTED, fn)
        
        checklist = None
        if os.path.exists(fp):
            mtime = os.path.getmtime(fp)
            cache_key = f"{fn}_{mtime}"
            if cache_key in _ANALYTICS_CACHE:
                checklist = _ANALYTICS_CACHE[cache_key]
            else:
                try:
                    tmpl = templates_data.get(doc_type, {})
                    v = Decree30Validator(fp, doc_type, tmpl, mssv=s.get("mssv", ""))
                    val_res = v.validate_document()
                    checklist = val_res.get("checklist", [])
                    _ANALYTICS_CACHE[cache_key] = checklist
                except Exception:
                    checklist = None

        if checklist:
            # Nhóm 1: Căn lề
            g1_items = [it for it in checklist if it.get("box_id") == "margins"]
            group_counts[1]["total"] += 1
            if g1_items and all(it.get("passed", False) for it in g1_items):
                group_counts[1]["passed"] += 1

            # Nhóm 2: Quốc hiệu, CQ, Số, Địa danh
            g2_items = [it for it in checklist if it.get("box_id") in [1, 2, 3, 4]]
            group_counts[2]["total"] += 1
            if g2_items and all(it.get("passed", False) for it in g2_items):
                group_counts[2]["passed"] += 1

            # Nhóm 3: Bảng biểu, Trích yếu, Nội dung
            g3_items = [it for it in checklist if it.get("box_id") in ["tables", 5, "5a", "5b", 6]]
            group_counts[3]["total"] += 1
            if g3_items and all(it.get("passed", False) for it in g3_items):
                group_counts[3]["passed"] += 1

            # Nhóm 4: Chữ ký, Nơi nhận
            g4_items = [it for it in checklist if it.get("box_id") in [7, "9a", "9b"]]
            group_counts[4]["total"] += 1
            if g4_items and all(it.get("passed", False) for it in g4_items):
                group_counts[4]["passed"] += 1

            # Ghi nhận từng lỗi chi tiết
            for it in checklist:
                if not it.get("passed", False):
                    for err in it.get("errors", []):
                        issue = err.get("issue", "").strip()
                        fix = err.get("fix", "").strip()
                        if issue:
                            short_target = issue.split("(")[0].strip() if "(" in issue else issue
                            short_target = short_target.replace("Section 1: ", "")
                            if short_target not in error_freq:
                                error_freq[short_target] = {
                                    "target": short_target,
                                    "solution": fix or "Xem lại quy định Nghị định 30/2020/NĐ-CP.",
                                    "count": 0
                                }
                            error_freq[short_target]["count"] += 1
        else:
            # R2 14: Thiếu tệp Word/snapshot không được ngụy tạo kết quả 100%; ghi nhận vào bài thiếu bằng chứng
            missing_evidence_count += 1

    group_stats = []
    for grp_id in [1, 2, 3, 4]:
        info = group_counts[grp_id]
        grp_tot = max(1, info["total"])
        grp_pass = info["passed"]
        pass_rate = round((grp_pass / grp_tot) * 100)
        group_stats.append({
            "id": grp_id,
            "name": info["name"],
            "passed": grp_pass,
            "failed": max(0, grp_tot - grp_pass),
            "passRate": pass_rate
        })

    sorted_errors = sorted(error_freq.values(), key=lambda x: x["count"], reverse=True)
    top_errors = []
    for rank, err in enumerate(sorted_errors[:10], start=1):
        cnt = err["count"]
        pct = round((cnt / total) * 100)
        top_errors.append({
            "rank": rank,
            "target": err["target"],
            "count": cnt,
            "rate": f"{pct}%",
            "solution": err["solution"]
        })

    return jsonify({
        "success": True,
        "has_data": True,
        "total_submissions": total,
        "avg_score": avg_score,
        "group_stats": group_stats,
        "top_errors": top_errors,
        "missing_evidence_count": missing_evidence_count
    })


# =========================================================================
# CN18 & CN17: QUẢN TRỊ THIẾT BỊ VÀ CẤP QUYỀN LÀM LẠI BÀI CHO GIẢNG VIÊN
# =========================================================================

def get_teacher_allowed_classes() -> Optional[List[str]]:
    """Lấy danh sách các lớp giảng viên được phân công phụ trách (R2 03). Trả về None nếu toàn quyền."""
    allowed = session.get("assigned_classes") or request.headers.get("X-Teacher-Assigned-Classes")
    if not allowed:
        active_t = get_active_teacher()
        if active_t and "assigned_classes" in active_t:
            allowed = active_t.get("assigned_classes")
    if not allowed:
        return None
    if isinstance(allowed, str):
        allowed_list = [c.strip().upper() for c in allowed.split(",") if c.strip()]
    else:
        allowed_list = [str(c).strip().upper() for c in allowed if str(c).strip()]
    if "ALL" in allowed_list:
        return None
    return allowed_list

def check_teacher_class_access(class_code: Optional[str]) -> Tuple[bool, str]:
    """
    Kiểm tra quyền phụ trách lớp của giảng viên (R2 03, R6 09 - RBAC Per Class).
    Trả về (allowed: bool, teacher_actor_name: str).
    """
    actor = session.get("active_teacher") or request.headers.get("X-Teacher-Name") or get_active_teacher().get("name", "Giảng viên")
    allowed_list = get_teacher_allowed_classes()
    if allowed_list is not None:
        if not class_code:
            return False, actor
        c_clean = str(class_code).strip().upper()
        if c_clean == "ALL":
            return True, actor
        if c_clean not in allowed_list:
            return False, actor
    return True, actor

@teacher_bp.route("/api/teacher/device/requests", methods=["GET"])
@require_teacher_auth
def get_teacher_device_requests():
    """Lấy danh sách yêu cầu đổi thiết bị của sinh viên (CN18 - NT09, V5 02, R6 09)"""
    class_code = request.args.get("class_code")
    allowed_list = get_teacher_allowed_classes()
    if class_code and class_code.strip().upper() != "ALL":
        allowed, actor = check_teacher_class_access(class_code)
        if not allowed:
            return jsonify({"error": f"Giảng viên không phụ trách lớp [{class_code}]!"}), 403
    status = request.args.get("status", "PENDING")
    from engine.db import get_device_change_requests
    query_class = class_code if (class_code and class_code.strip().upper() != "ALL") else None
    reqs = get_device_change_requests(class_code=query_class, status=status)
    if allowed_list is not None:
        reqs = [r for r in reqs if str(r.get("class_code", "")).strip().upper() in allowed_list]
    return jsonify({"requests": reqs, "total": len(reqs)})

@teacher_bp.route("/api/teacher/device/approve", methods=["POST"])
@require_teacher_auth
def approve_teacher_device():
    """Phê duyệt yêu cầu đổi thiết bị (CN18 - NT10, V5 02, R6 09)"""
    data = request.json or {}
    req_id = data.get("request_id")
    if not req_id:
        return jsonify({"error": "Thiếu request_id"}), 400
    from engine.db import get_device_change_request_by_id, approve_device_change_request
    req = get_device_change_request_by_id(req_id)
    if not req:
        return jsonify({"error": "Không tìm thấy yêu cầu hoặc yêu cầu đã được xử lý!"}), 404
    allowed, teacher_name = check_teacher_class_access(req.get("class_code"))
    if not allowed:
        return jsonify({"error": f"Giảng viên không phụ trách lớp [{req.get('class_code')}]!"}), 403
    ok = approve_device_change_request(req_id, approved_by=teacher_name)
    if ok:
        return jsonify({"success": True, "message": "Đã phê duyệt đổi thiết bị cho sinh viên!"})
    return jsonify({"error": "Không tìm thấy yêu cầu hoặc yêu cầu đã được xử lý!"}), 404

@teacher_bp.route("/api/teacher/device/reject", methods=["POST"])
@require_teacher_auth
def reject_teacher_device():
    """Từ chối yêu cầu đổi thiết bị (CN18 - NT11, V5 02, R6 09)"""
    data = request.json or {}
    req_id = data.get("request_id")
    if not req_id:
        return jsonify({"error": "Thiếu request_id"}), 400
    from engine.db import get_device_change_request_by_id, reject_device_change_request
    req = get_device_change_request_by_id(req_id)
    if not req:
        return jsonify({"error": "Không tìm thấy yêu cầu hoặc yêu cầu đã được xử lý!"}), 404
    allowed, teacher_name = check_teacher_class_access(req.get("class_code"))
    if not allowed:
        return jsonify({"error": f"Giảng viên không phụ trách lớp [{req.get('class_code')}]!"}), 403
    ok = reject_device_change_request(req_id, rejected_by=teacher_name)
    if ok:
        return jsonify({"success": True, "message": "Đã từ chối yêu cầu đổi thiết bị!"})
    return jsonify({"error": "Không tìm thấy yêu cầu hoặc yêu cầu đã được xử lý!"}), 404

@teacher_bp.route("/api/teacher/reattempt/grant", methods=["POST"])
@require_teacher_auth
def grant_reattempt():
    """Giảng viên cấp quyền làm lại bài cho sinh viên (CN17 - NT06, V5 02, R6 09)"""
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    mssv = str(data.get("mssv", "")).strip()
    doc_type = str(data.get("doc_type", "")).strip()
    reason = str(data.get("reason", "Giảng viên cho phép làm lại")).strip()
    if not (class_code and mssv and doc_type):
        return jsonify({"error": "Thiếu thông tin (class_code, mssv, doc_type)!"}), 400
    allowed, teacher_name = check_teacher_class_access(class_code)
    if not allowed:
        return jsonify({"error": f"Giảng viên không có thẩm quyền đối với lớp [{class_code}]!"}), 403
    if not doc_type:
        from engine.common import get_session_state
        doc_type = get_session_state(class_code).get("active_doc_type", "bai_thu_hoach")
    from engine.db import grant_reattempt_permission, get_db_connection
    pid = grant_reattempt_permission(class_code, mssv, doc_type, permitted_by=teacher_name, reason=reason)
    # Tự động mở lại lượt làm trắc nghiệm cho sinh viên nếu đã hoàn thành/hết giờ trước đó
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE quiz_attempts SET status = 'RESET' WHERE UPPER(class_code) = ? AND LOWER(mssv) = ? AND doc_type = ?;",
                (class_code.upper(), mssv.lower(), doc_type)
            )
    finally:
        conn.close()
    return jsonify({"success": True, "permission_id": pid, "message": f"Đã cấp quyền làm lại bài cho sinh viên {mssv}!"})

@teacher_bp.route("/api/teacher/submissions/history", methods=["GET"])
@require_teacher_auth
def get_teacher_submissions_history():
    """Truy vấn lịch sử các bài nộp đã lưu trữ (CN17 - NT08, V5 02, R6 09)"""
    class_code = request.args.get("class_code")
    allowed_list = get_teacher_allowed_classes()
    if class_code and class_code.strip().upper() != "ALL":
        allowed, actor = check_teacher_class_access(class_code)
        if not allowed:
            return jsonify({"error": f"Giảng viên không phụ trách lớp [{class_code}]!"}), 403
    mssv = request.args.get("mssv")
    from engine.db import get_submissions_history
    query_class = class_code if (class_code and class_code.strip().upper() != "ALL") else None
    hist = get_submissions_history(class_code=query_class, mssv=mssv)
    if allowed_list is not None:
        hist = [h for h in hist if str(h.get("class_code", "")).strip().upper() in allowed_list]
    return jsonify({"history": hist, "total": len(hist)})
