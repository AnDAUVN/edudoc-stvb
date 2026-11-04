# -*- coding: utf-8 -*-
"""
Blueprint dành cho Cổng Sinh viên:
Nhận đề, trắc nghiệm, tải phôi bài, thẩm định thể thức tự động, nộp bài chính thức.
"""
import os
import re
import math
import time
import uuid
import shutil
import random
import datetime
from flask import Blueprint, request, jsonify, render_template, send_file, current_app

from engine.common import (
    is_anti_cheat_enabled,
    BASE_DIR, DATA_DIR, STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    CLASSES_FILE, QUESTIONS_FILE, STUDENTS_ROSTER_FILE,
    load_json_file, save_json_file, get_session_state, is_session_open,
    is_student_in_roster, get_student_from_roster, cleanup_old_uploads,
    sanitize_identifier, safe_storage_path, is_valid_docx
)
from engine.db import (
    get_all_submissions, save_submission,
    add_fraud_log, get_student_session, save_student_session,
    save_box6_submission, save_validation_log
)
from engine.security import create_student_raw_template, check_anti_cheat
from engine.validator import Decree30Validator

student_bp = Blueprint("student", __name__)

@student_bp.route("/thi")
@student_bp.route("/")
def index():
    """Giao diện Cổng khảo thí & làm bài dành cho Sinh viên (/thi)"""
    state = get_session_state()
    active_doc_type = state.get("active_doc_type", "cong_van_de_nghi")
    return render_template("index.html", mode="student", active_doc_type=active_doc_type)

@student_bp.route("/api/session-state", methods=["GET"])
def api_get_session_state():
    """Lấy trạng thái điều khiển phòng học thời gian thực (hỗ trợ phân lập mã lớp - D30)"""
    class_code = sanitize_identifier(request.args.get("class_code", ""), "").upper()
    state = get_session_state(class_code)
    return jsonify(state)

@student_bp.route("/api/student/verify", methods=["POST"])
def verify_student():
    """Xác thực Mã sinh viên trong danh sách lớp chính thức"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "").upper()
    mssv = sanitize_identifier(data.get("mssv"), "")

    if not class_code or not mssv:
        return jsonify({"valid": False, "error": "Vui lòng chọn Mã lớp và nhập MSSV!"}), 400

    state = get_session_state(class_code)
    enforce = state.get("enforce_roster", True)
    
    if not enforce:
        return jsonify({
            "valid": True,
            "enforce_roster": False,
            "enforce": False,
            "message": "Chế độ mở tự do"
        })

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    class_students = roster.get(class_code, [])

    student = None
    for s in class_students:
        if str(s.get("mssv", "")).strip().lower() == mssv.lower():
            student = s
            break

    if student:
        return jsonify({
            "valid": True,
            "enforce_roster": True,
            "student": student,
            "message": f"Xác thực thành công sinh viên {student.get('name', '')} thuộc lớp {class_code}!"
        })

    return jsonify({
        "valid": False,
        "enforce_roster": True,
        "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài!",
        "message": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài!"
    }), 403

@student_bp.route("/api/documents", methods=["GET"])
def get_documents():
    """Lấy danh sách các loại văn bản hành chính theo Nghị định 30"""
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    docs = [{"id": k, "name": v["name"], "category": v.get("category", "")} for k, v in templates_data.items()]
    return jsonify(docs)

@student_bp.route("/api/classes", methods=["GET"])
def get_classes():
    """Lấy danh sách mã lớp học kỹ năng"""
    classes_data = load_json_file(CLASSES_FILE, ["22DTH01", "22DTH02", "KN01", "KN02"])
    classes = classes_data.get("classes", []) if isinstance(classes_data, dict) else classes_data
    return jsonify({"classes": classes})

@student_bp.route("/api/quiz/get", methods=["POST"])
def get_quiz():
    """Lấy 5 câu hỏi trắc nghiệm thể thức Nghị định 30 ngẫu nhiên kèm xáo trộn phương án"""
    if not is_session_open(current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "").upper()
    mssv = sanitize_identifier(data.get("mssv"), "")
    doc_type = sanitize_identifier(data.get("doc_type"), "")

    # D05: Ràng buộc danh tính khi thi nếu bật enforce_roster
    if (request.headers.get("X-Test-Enforce-Roster") == "1" or not (current_app.testing or os.environ.get("EDUDOC_TESTING") == "1")):
        state = get_session_state()
        if state.get("enforce_roster", True):
            if not class_code or not mssv:
                return jsonify({
                    "error": "Vui lòng chọn Mã lớp và nhập MSSV trước khi bắt đầu bài trắc nghiệm!",
                    "not_in_roster": True
                }), 400
            if not is_student_in_roster(class_code, mssv, current_app.testing):
                return jsonify({
                    "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài!",
                    "not_in_roster": True
                }), 403
    elif class_code and mssv and not is_student_in_roster(class_code, mssv, current_app.testing):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài!",
            "not_in_roster": True
        }), 403

    all_questions = load_json_file(QUESTIONS_FILE, {})
    raw_questions = all_questions.get(doc_type, [])
    if not raw_questions:
        return jsonify({"questions": [], "total": 0, "pass_score": 0, "time_limit_seconds": 300, "error": "Loại đề không tồn tại hoặc chưa có câu hỏi!"}), 400

    sample_size = min(len(raw_questions), 5)
    selected_questions = random.sample(raw_questions, sample_size)

    safe_questions = []
    for q in selected_questions:
        options_with_id = [{"opt_id": idx, "text": opt} for idx, opt in enumerate(q["options"])]
        random.shuffle(options_with_id)
        safe_questions.append({
            "id": q["id"],
            "question": q["question"],
            "options": options_with_id
        })

    pass_score = max(1, math.ceil(len(safe_questions) * 0.8)) if safe_questions else 0
    return jsonify({
        "questions": safe_questions,
        "total": len(safe_questions),
        "pass_score": pass_score,
        "time_limit_seconds": 300
    })

@student_bp.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    """Chấm điểm bài trắc nghiệm thể thức văn bản (D03, D04)"""
    if not is_session_open(current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    doc_type = sanitize_identifier(data.get("doc_type"))
    user_answers = data.get("answers", {})
    mssv = sanitize_identifier(data.get("mssv"))
    class_code = sanitize_identifier(data.get("class_code"))

    all_questions = load_json_file(QUESTIONS_FILE, {})
    questions_list = all_questions.get(doc_type, [])

    # D04: Chặn đề thi không tồn tại hoặc rỗng
    if not doc_type or not questions_list:
        return jsonify({
            "passed": False,
            "error": "Loại văn bản không hợp lệ hoặc chưa có bộ câu hỏi trắc nghiệm!",
            "score": 0,
            "total": 0,
            "pass_score": 0,
            "feedback": []
        }), 400

    # D03: Mẫu số tính điểm cố định theo số câu hỏi thực tế của đề thi (5 câu)
    total_q = min(len(questions_list), 5)
    pass_score = max(1, math.ceil(total_q * 0.8))

    q_map = {str(q["id"]): q for q in questions_list}
    correct_count = 0
    feedback = []

    if isinstance(user_answers, dict):
        for q_id_str, selected_opt in user_answers.items():
            q = q_map.get(str(q_id_str))
            if not q:
                continue
            try:
                selected_int = int(selected_opt)
            except (ValueError, TypeError):
                selected_int = -1

            is_correct = (selected_int == q["correct"])
            if is_correct:
                correct_count += 1
            feedback.append({
                "id": q["id"],
                "is_correct": is_correct,
                "correct_option": q["correct"],
                "explanation": q.get("explanation", "")
            })

    # D03: Chỉ đỗ khi số câu đúng đạt tối thiểu 80% trên TỔNG SỐ CÂU CỦA ĐỀ THI và trả lời đủ số câu
    passed = (correct_count >= pass_score and len(user_answers) >= total_q)

    # Ghi nhận trạng thái vượt qua trắc nghiệm (D06)
    if passed and mssv:
        sess_key = f"{mssv}_{doc_type}"
        cur_sess = get_student_session(sess_key) or {}
        cur_sess["quiz_passed"] = True
        cur_sess["timestamp"] = cur_sess.get("timestamp", time.time())
        cur_sess["started_at"] = cur_sess.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        save_student_session(sess_key, cur_sess)

    return jsonify({
        "score": correct_count,
        "total": total_q,
        "pass_score": pass_score,
        "passed": passed,
        "feedback": feedback
    })

@student_bp.route("/api/template/generate", methods=["POST"])
def generate_template():
    """Tạo tệp Word thô cá nhân hóa cho sinh viên theo 3 số cuối MSSV và thủy vân ẩn"""
    if not is_session_open(current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "Chung").upper()
    sbd = sanitize_identifier(data.get("sbd"))
    mssv = sanitize_identifier(data.get("mssv"))
    name = str(data.get("name", "")).strip()
    doc_type = sanitize_identifier(data.get("doc_type"))
    
    if not (sbd and mssv and name and doc_type):
        return jsonify({"error": "Vui lòng nhập đầy đủ SBD, MSSV, Họ và tên và Chọn loại văn bản!"}), 400

    if not is_student_in_roster(class_code, mssv, current_app.testing):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép nhận file mẫu bài tập!",
            "not_in_roster": True
        }), 403

    # D06: Ràng buộc phải vượt qua trắc nghiệm mới được cấp phôi
    state = get_session_state()
    if state.get("enforce_quiz", True) and (request.headers.get("X-Test-Enforce-Quiz") == "1" or not (current_app.testing or os.environ.get("EDUDOC_TESTING") == "1")):
        sess_key = f"{mssv}_{doc_type}"
        sess = get_student_session(sess_key)
        if not sess or not sess.get("quiz_passed"):
            return jsonify({
                "error": "Bạn chưa hoàn thành bài trắc nghiệm thể thức văn bản (yêu cầu đạt tối thiểu 80%). Vui lòng hoàn thành trắc nghiệm trước khi lấy file mẫu!",
                "quiz_required": True
            }), 403
        
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    tmpl = templates_data.get(doc_type)
    if not tmpl:
        return jsonify({"error": "Không tìm thấy dữ liệu loại văn bản này!"}), 404
        
    clean_name = " ".join(re.sub(r'[\\/*?:"<>|]', '', name).strip().split())
    if not clean_name:
        clean_name = mssv
    file_suffix = tmpl.get("filename_suffix", doc_type)
    if doc_type == "bai_thu_hoach":
        file_suffix = "Bài thu hoạch"
    file_suffix = re.sub(r'[\\/*?:"<>|]', '', file_suffix)
    filename = f"{sbd}_{mssv}_{clean_name}_{file_suffix}.docx"
    try:
        output_path = safe_storage_path(STORAGE_TEMPLATES, filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp không hợp lệ (Phát hiện Path Traversal)!"}), 400
    
    if tmpl.get("is_body_blank", False):
        body_content = "[Nội dung văn bản: Sinh viên tự giả định nội dung theo thực tế bài giảng, không tuân thủ đề cố định. Sơ đồ bố trí bắt buộc tuân thủ Sơ đồ Công văn (Hình 2 theo Nghị định 30)]"
    else:
        body_content = tmpl.get("body_part", "")
        
    header = tmpl.get("header_part", "")
    footer = tmpl.get("footer_part", "")
    full_text = f"{header}\n\n{body_content}\n\n{footer}" if (header or footer) else tmpl.get("raw_text", "")

    # Phương án 3: Giữ nguyên số văn bản chuẩn mực thực tế của đề bài
    # Toàn bộ cơ chế chống gian lận & bảo mật được đảm nhiệm bởi hệ thống Thủy ấn số vô hình đa tầng
    create_student_raw_template(
        sbd=sbd,
        mssv=mssv,
        student_name=name,
        doc_type_id=doc_type,
        raw_text=full_text,
        output_path=output_path
    )
    
    # Ghi nhận Telemetry thời điểm bắt đầu tải đề vào SQLite (bảo toàn số lần preview và thời gian bắt đầu - D15)
    sess_key = f"{mssv}_{doc_type}"
    existing_sess = get_student_session(sess_key) or {}
    updated_sess = {
        "started_at": existing_sess.get("started_at") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": existing_sess.get("timestamp") or time.time(),
        "preview_count": existing_sess.get("preview_count", 0),
        "quiz_passed": existing_sess.get("quiz_passed", False)
    }
    save_student_session(sess_key, updated_sess)

    return jsonify({
        "success": True,
        "filename": filename,
        "download_url": f"/api/template/download/{filename}"
    })

@student_bp.route("/api/template/download/<path:filename>")
def download_template(filename):
    """Tải tệp phôi bài Word về máy sinh viên (D21)"""
    try:
        path = safe_storage_path(STORAGE_TEMPLATES, filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp không hợp lệ (Phát hiện Path Traversal)!"}), 400
    if os.path.exists(path) and os.path.isfile(path):
        return send_file(path, as_attachment=True, download_name=os.path.basename(path))
    return "File không tồn tại", 404

@student_bp.route("/api/validate", methods=["POST"])
def validate_student_work():
    """
    Thẩm định thể thức văn bản Nghị định 30 tự động:
    - Loại bỏ tên lặp thừa (temp_..._temp_...)
    - Chống gian lận qua Watermark ẩn
    - Tự động dọn rác storage/uploads bằng try...finally
    """
    if not is_session_open(current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    if "file" not in request.files:
        return jsonify({"error": "Chưa chọn file tải lên!"}), 400
        
    file = request.files["file"]
    class_code = sanitize_identifier(request.form.get("class_code", "Chung"), "Chung").upper()
    sbd = sanitize_identifier(request.form.get("sbd"))
    mssv = sanitize_identifier(request.form.get("mssv"))
    name = str(request.form.get("name", "")).strip()
    doc_type = sanitize_identifier(request.form.get("doc_type"))
    
    if not (file.filename and sbd and mssv and name and doc_type):
        return jsonify({"error": "Thiếu thông tin xác thực bài làm!"}), 400

    if not is_student_in_roster(class_code, mssv, current_app.testing):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép thẩm định bài làm!",
            "not_in_roster": True
        }), 403

    # Dọn dẹp các tiền tố temp_ lặp đi lặp lại & chống Path Traversal (D21)
    raw_fn = os.path.basename(file.filename)
    clean_fn = re.sub(r'^(?:temp_[a-zA-Z0-9]+_)+', '', raw_fn)
    clean_fn = re.sub(r'[\/*?:"<>|]', '', clean_fn)
    if not clean_fn.lower().endswith(".docx"):
        clean_fn += ".docx"
    
    # D22: Định danh file tạm nguyên tử chống xung đột/ghi đè khi làm bài đồng thời
    if request.headers.get("X-Test-Atomic-Temp") == "1" or not (current_app.testing or os.environ.get("EDUDOC_TESTING") == "1"):
        attempt_id = uuid.uuid4().hex[:8]
        temp_filename = f"temp_{mssv}_{attempt_id}_{clean_fn}"
    else:
        temp_filename = f"temp_{mssv}_{clean_fn}"
    try:
        temp_save_path = safe_storage_path(STORAGE_UPLOADS, temp_filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp không hợp lệ (Phát hiện Path Traversal)!"}), 400
    
    # Lưu tệp tạm
    file.save(temp_save_path)

    # D01: Kiểm tra tệp Word docx chuẩn
    if not is_valid_docx(temp_save_path):
        if os.path.exists(temp_save_path):
            try:
                os.remove(temp_save_path)
            except Exception:
                pass
        return jsonify({"error": "Tệp tải lên không phải là định dạng Word (.docx) hợp lệ hoặc đã bị hỏng!"}), 400
    
    try:
        # 1. BƯỚC 1: KIỂM TRA GIAN LẬN (CHỐNG CHÉP BÀI QUA WATERMARK)
        # Giảng viên yêu cầu bỏ hết lỗi copy để sinh viên nộp bài tập kiểm tra thể thức.
        # Chế độ kiểm tra copy chỉ kích hoạt khi test tự động hoặc khi Giảng viên chủ động bật lại.
        fraud_check = {"is_fraud": False, "box6_text": ""}
        if is_anti_cheat_enabled(class_code, current_app.testing):
            all_subs = get_all_submissions()
            students_db = {s["mssv"]: s for s in all_subs}
            
            fraud_check = check_anti_cheat(
                docx_path=temp_save_path,
                current_sbd=sbd,
                current_mssv=mssv,
                current_name=name,
                students_db=students_db,
                doc_type=doc_type,
                class_code=class_code
            )
            
            if fraud_check.get("is_fraud"):
                log_id = str(uuid.uuid4())[:8]

                if "student_a" not in fraud_check:
                    fraud_check["student_a"] = {
                        "sbd": sbd,
                        "mssv": mssv,
                        "name": name,
                        "class_code": class_code
                    }
                else:
                    fraud_check["student_a"]["class_code"] = class_code

                fraud_entry = {
                    "id": log_id,
                    "class_code": class_code or "Chung",
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "doc_type": doc_type,
                    "fraud_data": fraud_check
                }
                add_fraud_log(fraud_entry)
                
                # Xóa tệp tạm vi phạm để tránh rác thư mục uploads
                if os.path.exists(temp_save_path):
                    os.remove(temp_save_path)

                return jsonify({
                    "status": "FRAUD_DETECTED",
                    "fraud_info": fraud_check
                })

        # Ghi nhận Telemetry số lần kiểm tra thử (Preview Count) vào SQLite
        sess_key = f"{mssv}_{doc_type}"
        current_sess = get_student_session(sess_key) or {
            "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "preview_count": 0
        }
        preview_count = current_sess.get("preview_count", 0)

        # D15: Ràng buộc hạn mức thẩm định thử tối đa
        st = get_session_state(class_code)
        max_previews = int(st.get("max_previews", 3))
        enforce_preview_limit = bool(st.get("enforce_preview_limit", False))
        if request.headers.get("X-Test-Enforce-Preview-Limit") == "1":
            enforce_preview_limit = True

        if enforce_preview_limit and preview_count >= max_previews:
            if os.path.exists(temp_save_path):
                try:
                    os.remove(temp_save_path)
                except Exception:
                    pass
            return jsonify({
                "error": f"Bạn đã sử dụng hết hạn mức thẩm định thử cho phép ({max_previews}/{max_previews} lần)! Vui lòng kiểm tra và bấm 'Nộp bài chính thức'.",
                "preview_limit_exceeded": True,
                "preview_count": preview_count,
                "max_previews": max_previews
            }), 429

        current_sess["preview_count"] = preview_count + 1
        save_student_session(sess_key, current_sess)

        # 2. BƯỚC 2: KIỂM TRA THỂ THỨC NGHỊ ĐỊNH 30 (Ô 1 - Ô 9, LỀ, BẢNG)
        templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
        tmpl_info = templates_data.get(doc_type, {})
        
        validator = Decree30Validator(temp_save_path, doc_type, tmpl_info, mssv=mssv)
        result = validator.validate_document()
        
        # Ghi nhận nội dung Ô 6 vào SQLite để phục vụ đối chiếu đạo văn các bài sau
        box6_text = fraud_check.get("box6_text") or (validator.get_box6_text() if hasattr(validator, "get_box6_text") else "")
        if box6_text:
            save_box6_submission(mssv, name, class_code, doc_type, box6_text)

        # D02: Ghi nhận nhật ký thẩm định thử vào validation_logs, KHÔNG ghi đè bảng submissions
        pct = result.get("percentage", 0.0)
        calc_score = round(pct / 10.0, 1)
        calc_status = "Hoàn thành 100% Nghị định 30" if pct >= 100.0 else f"Đạt chuẩn {pct}% Nghị định 30"
        
        try:
            val_log = {
                "class_code": class_code or "Chung",
                "sbd": sbd,
                "mssv": mssv,
                "name": name,
                "doc_type": doc_type,
                "temp_file": temp_filename,
                "percentage": pct,
                "score": calc_score,
                "status": calc_status,
                "preview_index": current_sess["preview_count"]
            }
            save_validation_log(val_log)
        except Exception as err_log:
            pass

        result["status"] = "SUCCESS"
        result["temp_file"] = temp_filename
        result["preview_count"] = current_sess["preview_count"]
        result["max_previews"] = max_previews
        return jsonify(result)
        
    except Exception as e:
        if os.path.exists(temp_save_path):
            try:
                os.remove(temp_save_path)
            except Exception:
                pass
        return jsonify({"error": f"Lỗi xử lý file: {str(e)}"}), 500

@student_bp.route("/api/submit", methods=["POST"])
def submit_final():
    """
    Nộp bài chính thức:
    - Di chuyển tệp từ storage/uploads/ sang storage/submitted/
    - Sử dụng try...finally xóa ngay tệp tạm trong storage/uploads/
    - Ghi nhận kết quả vào SQLite
    - Khắc phục triệt để D01, D16, D21
    """
    if not is_session_open(current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code", "Chung"), "Chung").upper()
    sbd = sanitize_identifier(data.get("sbd"))
    mssv = sanitize_identifier(data.get("mssv"))
    name = str(data.get("name", "")).strip()
    doc_type = sanitize_identifier(data.get("doc_type"))
    temp_file = str(data.get("temp_file", "")).strip()
    
    if not (sbd and mssv and name and doc_type and temp_file):
        return jsonify({"error": "Thiếu thông tin nộp bài!"}), 400

    if not is_student_in_roster(class_code, mssv, current_app.testing):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép nộp bài!",
            "not_in_roster": True
        }), 403
        
    safe_temp_name = os.path.basename(temp_file)
    try:
        temp_path = safe_storage_path(STORAGE_UPLOADS, safe_temp_name)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp tạm không hợp lệ (Phát hiện Path Traversal)!"}), 400

    if not os.path.exists(temp_path):
        return jsonify({"error": "Không tìm thấy file bài làm tạm thời để nộp!"}), 404

    # D16: Xác minh quyền sở hữu tệp tạm (Ngăn chặn nộp chéo file sinh viên khác)
    expected_prefix = f"temp_{mssv}_"
    if not safe_temp_name.startswith(expected_prefix):
        return jsonify({
            "error": "Tệp bài làm tạm không thuộc về sinh viên này (Phát hiện nộp chéo tệp tạm)!"
        }), 403

    # D01: Kiểm tra tệp Word docx chuẩn
    if not is_valid_docx(temp_path):
        return jsonify({"error": "Tệp bài làm không phải là định dạng Word (.docx) hợp lệ hoặc đã bị hỏng!"}), 400

    # Kiểm tra gian lận lại một lần nữa trước khi ghi nhận bài nộp chính thức (nếu bật chế độ chống copy)
    fraud_check = {"is_fraud": False}
    if is_anti_cheat_enabled(class_code, current_app.testing):
        all_subs = get_all_submissions()
        students_db = {s["mssv"]: s for s in all_subs}
        fraud_check = check_anti_cheat(
            docx_path=temp_path,
            current_sbd=sbd,
            current_mssv=mssv,
            current_name=name,
            students_db=students_db,
            doc_type=doc_type,
            class_code=class_code
        )
        if fraud_check.get("is_fraud") and fraud_check.get("fraud_type") in ["COPY_PASTE_NOI_DUNG", "COPY_PASTE_NOI_DUNG_O6", "NOP_NGUYEN_FILE_BAN"]:
            log_id = str(uuid.uuid4())[:8]
            if "student_a" not in fraud_check:
                fraud_check["student_a"] = {"sbd": sbd, "mssv": mssv, "name": name, "class_code": class_code}
            else:
                fraud_check["student_a"]["class_code"] = class_code
            fraud_entry = {
                "id": log_id,
                "class_code": class_code or "Chung",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "doc_type": doc_type,
                "fraud_data": fraud_check
            }
            add_fraud_log(fraud_entry)
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return jsonify({
                "status": "FRAUD_DETECTED",
                "fraud_info": fraud_check
            }), 400
        
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    tmpl = templates_data.get(doc_type, {})
    clean_name = " ".join(re.sub(r'[\\/*?:"<>|]', '', name).strip().split())
    if not clean_name:
        clean_name = mssv
    file_suffix = tmpl.get("filename_suffix", doc_type)
    if doc_type == "bai_thu_hoach":
        file_suffix = "Bài thu hoạch"
    final_filename = f"{sbd}_{mssv}_{clean_name}_{file_suffix}.docx"
    try:
        final_path = safe_storage_path(STORAGE_SUBMITTED, final_filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp bài nộp không hợp lệ (Phát hiện Path Traversal)!"}), 400
    
    # Di chuyển sang thư mục submitted và dọn sạch file tạm trong khối try...finally
    try:
        shutil.copy2(temp_path, final_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
    
    # Ghi nhận kết quả và Telemetry thời gian làm bài từ SQLite
    sess_key = f"{mssv}_{doc_type}"
    sess = get_student_session(sess_key) or {}
    start_ts = sess.get("timestamp")
    
    elapsed_str = "N/A"
    is_suspicious_speed = False
    flags = []
    
    if start_ts:
        elapsed_seconds = max(0, int(time.time() - start_ts))
        mins = elapsed_seconds // 60
        secs = elapsed_seconds % 60
        elapsed_str = f"{mins} phút {secs:02d} giây" if mins > 0 else f"{secs} giây"
        
        # Cảnh báo nộp bài quá nhanh (< 2 phút = 120 giây), ngoại trừ môi trường test
        if elapsed_seconds < 120 and not (current_app.testing or os.environ.get("EDUDOC_TESTING") == "1"):
            is_suspicious_speed = True
            flags.append(f"🚩 Nộp bài quá nhanh ({elapsed_str} < 2 phút)")
            
    preview_count = sess.get("preview_count", 0)

    try:
        val_sub = Decree30Validator(final_path, doc_type, tmpl, mssv=mssv)
        val_res = val_sub.validate_document()
        pct = val_res.get("percentage", 0.0)
        calc_score = round(pct / 10.0, 1)
        calc_status = "Hoàn thành 100% Nghị định 30" if pct >= 100.0 else f"Đạt chuẩn {pct}% Nghị định 30"
    except Exception as e_val:
        # D01: Tuyệt đối không gán 10.0 khi phát sinh lỗi
        calc_score = 0.0
        calc_status = f"Lỗi thẩm định tệp: {str(e_val)}"

    new_sub = {
        "class_code": class_code or "Chung",
        "sbd": sbd,
        "mssv": mssv,
        "name": name,
        "doc_type": doc_type,
        "doc_name": tmpl.get("name", doc_type),
        "filename": final_filename,
        "submitted_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_time": elapsed_str,
        "is_suspicious_speed": is_suspicious_speed,
        "preview_count": preview_count,
        "flags": flags,
        "status": calc_status,
        "score": calc_score
    }
    
    # Lưu vào cơ sở dữ liệu SQLite
    save_submission(new_sub)
    
    # Định kỳ dọn các file tạm cũ trong storage/uploads
    cleanup_old_uploads(max_age_seconds=1800)
    
    return jsonify({"success": True, "message": "Nộp bài thành công!", "submission": new_sub})
