# -*- coding: utf-8 -*-
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
from flask import Blueprint, request, jsonify, render_template, send_file, Response, current_app

from engine.common import (
    BASE_DIR, DATA_DIR, STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    CLASSES_FILE, SESSION_STATE_FILE, STUDENTS_ROSTER_FILE, QUESTIONS_FILE, TEACHERS_FILE,
    load_json_file, save_json_file, get_session_state, save_session_state, parse_students_text,
    get_teachers_data, get_active_teacher, set_active_teacher
)
from engine.db import (
    get_all_submissions, delete_submission_by_mssv,
    get_all_fraud_logs, delete_fraud_log_by_id, clear_all_fraud_logs
)

teacher_bp = Blueprint("teacher", __name__)

@teacher_bp.route("/quan-tri")
@teacher_bp.route("/teacher")
@teacher_bp.route("/admin")
def teacher_portal():
    """Giao diện Bàn làm việc & Dashboard Quản trị Khảo thí dành cho Giảng viên (/quan-tri)"""
    state = get_session_state()
    active_doc_type = state.get("active_doc_type", "cong_van_de_nghi")
    # Render teacher.html chuyên biệt, an toàn và tối ưu tải trang
    return render_template("teacher.html", mode="teacher", active_doc_type=active_doc_type)

@teacher_bp.route("/api/teacher/session-state", methods=["POST"])
def api_set_session_state():
    """Bật / Tắt trạng thái làm bài (Khóa khi giảng lý thuyết, mở khi cho phép làm bài)"""
    data = request.json or {}
    current = get_session_state()
    new_is_open = bool(data.get("is_open", current.get("is_open", False))) if "is_open" in data else current.get("is_open", False)
    new_message = str(data.get("message", "")).strip() or current.get("message", "Giảng viên đang giảng lý thuyết. Hệ thống làm bài tập đang tạm khóa để các bạn tập trung nghe giảng.")
    enforce_roster = bool(data.get("enforce_roster", current.get("enforce_roster", True)))
    active_doc_type = str(data.get("active_doc_type", current.get("active_doc_type", "cong_van_de_nghi"))).strip()
    
    updated_state = {
        "is_open": new_is_open,
        "enforce_roster": enforce_roster,
        "active_doc_type": active_doc_type,
        "message": new_message,
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_session_state(updated_state)
    return jsonify({
        "success": True,
        "session_state": updated_state,
        "message": "Đã mở quyền làm bài cho sinh viên!" if new_is_open else "Đã khóa hệ thống để sinh viên tập trung nghe giảng!"
    })

@teacher_bp.route("/api/teacher/set-active-doc", methods=["POST"])
def api_set_active_doc():
    """Chuyển loại văn bản bài tập giao cho sinh viên làm trong ca học"""
    data = request.json or {}
    doc_type = str(data.get("doc_type", "")).strip()
    if not doc_type:
        return jsonify({"error": "Vui lòng chọn loại văn bản hợp lệ!"}), 400
    state = get_session_state()
    state["active_doc_type"] = doc_type
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_session_state(state)
    return jsonify({
        "success": True,
        "active_doc_type": doc_type,
        "session_state": state,
        "message": f"Đã chuyển loại văn bản giao làm bài sang: [{doc_type}]"
    })

@teacher_bp.route("/api/teacher/roster-toggle", methods=["POST"])
def toggle_roster_mode():
    """Bật / Tắt chế độ bắt buộc sinh viên phải có tên trong danh sách lớp"""
    data = request.json or {}
    state = get_session_state()
    if "enforce_roster" in data:
        state["enforce_roster"] = bool(data["enforce_roster"])
    else:
        state["enforce_roster"] = not state.get("enforce_roster", True)
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_session_state(state)
    return jsonify({
        "success": True,
        "enforce_roster": state["enforce_roster"],
        "message": "Đã BẬT kiểm tra danh sách lớp (chỉ sinh viên trong danh sách mới được làm bài)!" if state["enforce_roster"] else "Đã TẮT kiểm tra danh sách (mở tự do cho mọi sinh viên)."
    })

@teacher_bp.route("/api/teacher/students", methods=["GET"])
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
def add_student_to_roster():
    """Thêm một sinh viên vào danh sách lớp"""
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    sbd = str(data.get("sbd", "")).strip()
    mssv = str(data.get("mssv", "")).strip()
    name = str(data.get("name", "")).strip()

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
        "name": name
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
def delete_class():
    """Xóa một mã lớp học kỹ năng"""
    data = request.json or {}
    code = str(data.get("class_code", "")).strip().upper()
    classes_data = load_json_file(CLASSES_FILE, {"classes": []})
    c_list = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    if code in c_list:
        c_list.remove(code)
        save_json_file(CLASSES_FILE, {"classes": c_list})
        return jsonify({"success": True, "classes": c_list, "message": f"Đã xóa lớp {code}!"})
    return jsonify({"error": f"Không tìm thấy lớp {code}!"}), 404

@teacher_bp.route("/api/teacher/data", methods=["GET"])
def teacher_data():
    """Lấy dữ liệu tổng hợp từ SQLite phục vụ Bàn làm việc Giảng viên"""
    submissions = get_all_submissions()
    fraud_logs = get_all_fraud_logs()
    classes_data = load_json_file(CLASSES_FILE, {"classes": ["KN01", "KN02", "KN03", "KN04", "KN05"]})
    classes = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    session_state = get_session_state()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
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

@teacher_bp.route("/api/download/submitted/<filename>")
def download_submitted(filename):
    """Tải tệp bài nộp chính thức của sinh viên"""
    safe_name = os.path.basename(filename)
    path = os.path.join(STORAGE_SUBMITTED, safe_name)
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=safe_name)
    return "File không tồn tại", 404

@teacher_bp.route("/api/teacher/export-csv", methods=["GET"])
def export_csv():
    """Xuất bảng điểm bài tập ra định dạng CSV có UTF-8 BOM hiển thị chuẩn trong Excel"""
    class_filter = request.args.get("class_code", "ALL")
    submissions = get_all_submissions(class_code=class_filter)
        
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    
    active_teacher = get_active_teacher()
    teacher_name = active_teacher.get("name", "Giảng viên bộ môn")
    dept = active_teacher.get("department", "Quản trị văn phòng")
    
    writer.writerow(["BẢNG ĐIỂM BÀI TẬP SOẠN THẢO VĂN BẢN (NGHỊ ĐỊNH 30/2020/NĐ-CP)"])
    writer.writerow([f"Giảng viên phụ trách: {teacher_name} ({dept})", f"Lớp: {class_filter}", f"Thời gian xuất: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    writer.writerow([])
    writer.writerow([
        "STT", "Mã lớp KN", "Số báo danh (SBD)", "Mã số sinh viên (MSSV)", "Họ và tên",
        "Loại văn bản bài tập", "Tên file nộp", "Thời gian nộp", "Thời gian làm bài", "Số lần kiểm tra thử", "Cảnh báo gian lận / đối phó", "Kết quả thẩm định", "Điểm số quy đổi"
    ])
    
    for idx, s in enumerate(submissions):
        flag_text = ", ".join(s.get("flags", [])) if s.get("flags") else ("🚩 Nộp quá nhanh (< 2p)" if s.get("is_suspicious_speed") else "Bình thường")
        writer.writerow([
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
def delete_teacher_submission():
    """Xóa bài nộp của sinh viên khỏi SQLite"""
    data = request.json or {}
    mssv = str(data.get("mssv", "")).strip()
    doc_type = str(data.get("doc_type", "")).strip()
    if not mssv:
        return jsonify({"error": "Thiếu MSSV cần xóa!"}), 400
    
    deleted = delete_submission_by_mssv(mssv, doc_type)
    return jsonify({"success": True, "message": f"Đã xóa bài nộp của MSSV {mssv}!"})

@teacher_bp.route("/api/teacher/fraud/delete", methods=["POST"])
def delete_fraud_log():
    """Xóa một bản ghi nhật ký gian lận khỏi SQLite"""
    data = request.json or {}
    log_id = str(data.get("id", "")).strip()
    if not log_id:
        return jsonify({"error": "Thiếu mã bản ghi vi phạm cần xóa!"}), 400
    
    deleted = delete_fraud_log_by_id(log_id)
    return jsonify({"success": True, "message": "Đã xóa biên bản vi phạm thành công!"})

@teacher_bp.route("/api/teacher/fraud/clear", methods=["POST"])
def clear_fraud_logs():
    """Xóa toàn bộ nhật ký gian lận khỏi SQLite"""
    clear_all_fraud_logs()
    return jsonify({"success": True, "message": "Đã xóa toàn bộ nhật ký vi phạm của hệ thống!"})

@teacher_bp.route("/api/teacher/templates", methods=["GET"])
def teacher_templates():
    """Lấy danh sách các mẫu văn bản gốc để giảng viên tùy chỉnh"""
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    return jsonify(templates_data)

@teacher_bp.route("/api/teacher/templates/save", methods=["POST"])
def save_teacher_template():
    """Lưu cập nhật nội dung bài tập của văn bản"""
    data = request.json or {}
    doc_type = data.get("doc_type")
    is_body_blank = bool(data.get("is_body_blank", False))
    header_part = data.get("header_part", "").strip()
    body_part = data.get("body_part", "").strip()
    footer_part = data.get("footer_part", "").strip()

    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    if doc_type not in templates_data:
        return jsonify({"error": "Không tìm thấy loại văn bản!"}), 404

    templates_data[doc_type]["is_body_blank"] = is_body_blank
    if header_part:
        templates_data[doc_type]["header_part"] = header_part
    templates_data[doc_type]["body_part"] = body_part
    if footer_part:
        templates_data[doc_type]["footer_part"] = footer_part

    placeholder = "[Nội dung văn bản: Sinh viên tự giả định nội dung theo thực tế bài giảng, không tuân thủ đề cố định. Sơ đồ bố trí bắt buộc tuân thủ Sơ đồ Công văn (Hình 2 theo Nghị định 30)]"
    b = placeholder if is_body_blank else body_part
    templates_data[doc_type]["raw_text"] = f"{header_part}\n\n{b}\n\n{footer_part}"

    save_json_file(os.path.join(DATA_DIR, "document_templates.json"), templates_data)
    return jsonify({"success": True, "message": "Đã lưu cập nhật nội dung bài tập thành công!"})

@teacher_bp.route("/api/teacher/quiz/<doc_type>", methods=["GET"])
def get_teacher_quiz(doc_type):
    """Lấy ngân hàng câu hỏi trắc nghiệm của một loại văn bản"""
    all_questions = load_json_file(QUESTIONS_FILE, {})
    questions = all_questions.get(doc_type, [])
    return jsonify({"questions": questions, "doc_type": doc_type, "total": len(questions)})

@teacher_bp.route("/api/teacher/quiz/save", methods=["POST"])
def save_teacher_quiz():
    """Lưu hoặc cập nhật câu hỏi trắc nghiệm"""
    data = request.json or {}
    doc_type = data.get("doc_type")
    q_id = data.get("id")
    question_text = str(data.get("question", "")).strip()
    options = data.get("options", [])
    correct = data.get("correct")
    explanation = str(data.get("explanation", "")).strip()

    if not doc_type or not question_text or len(options) < 2 or correct is None:
        return jsonify({"error": "Vui lòng nhập đầy đủ câu hỏi, tối thiểu 2 phương án và chọn đáp án đúng!"}), 400

    try:
        correct = int(correct)
    except Exception:
        return jsonify({"error": "Đáp án đúng không hợp lệ!"}), 400

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
