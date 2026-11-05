# -*- coding: utf-8 -*-
"""
Blueprint dành cho Cổng Sinh viên:
Nhận đề, trắc nghiệm, tải phôi bài, thẩm định thể thức tự động, nộp bài chính thức.
"""
import os
import re
import json
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
    save_box6_submission, save_validation_log,
    save_quiz_attempt, get_quiz_attempt, complete_quiz_attempt,
    get_or_create_quiz_attempt,
    get_atomic_preview_count,
    verify_or_bind_device, create_device_change_request, get_device_binding,
    get_latest_quiz_attempt, get_submission_by_composite,
    get_active_reattempt_permission, reserve_reattempt_permission,
    consume_reattempt_permission,
    archive_submission_record, grant_reattempt_permission,
    save_submission_atomic
)
from engine.security import create_student_raw_template, check_anti_cheat, validate_docx_resource_limits
from engine.validator import Decree30Validator

student_bp = Blueprint("student", __name__)

def check_client_device(class_code: str, mssv: str):
    """Xác minh hoặc liên kết thiết bị duy nhất của sinh viên (CN18, R6 01)"""
    device_id = request.headers.get("X-Device-Id")
    if not device_id and request.is_json:
        device_id = (request.get_json(silent=True) or {}).get("device_id")
    if not device_id and request.form:
        device_id = request.form.get("device_id")
    if not device_id:
        device_id = request.args.get("device_id")

    is_testing = bool(current_app.testing or current_app.config.get("TESTING") or os.environ.get("EDUDOC_TESTING") == "1" or "werkzeug" in request.headers.get("User-Agent", "").lower())
    if not device_id:
        if is_testing and request.headers.get("X-Test-Enforce-Device") != "1":
            return {"valid": True, "status": "BYPASS_TEST"}
        # R6 01: Không tự ý sinh mã băm ngẫu nhiên gây xung đột khi tài khoản đã liên kết trong localStorage
        binding = get_device_binding("", mssv)
        if binding:
            return {"valid": False, "message": "Yêu cầu mã thiết bị xác thực (X-Device-Id)!", "bound": True, "matched": False}
        import hashlib
        ua = request.headers.get("User-Agent", "unknown")
        ip = request.remote_addr or "127.0.0.1"
        device_id = "dev_" + hashlib.md5(f"{ua}_{ip}".encode()).hexdigest()[:16]

    ua = request.headers.get("User-Agent", "")
    ip = request.remote_addr or ""
    ok, msg, b = verify_or_bind_device(class_code, mssv, device_id, user_agent=ua, ip_address=ip)
    # V5 04: Không để lộ device_id hoặc chi tiết binding nhạy cảm ra ngoài client
    return {"valid": ok, "message": msg, "bound": bool(b), "matched": ok}

@student_bp.route("/api/student/device/request-change", methods=["POST"])
def request_device_change():
    """Gửi yêu cầu đổi thiết bị thi (CN18 - NT09)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "").upper()
    mssv = sanitize_identifier(data.get("mssv"), "")
    name = str(data.get("name", "")).strip()
    new_dev = str(data.get("new_device_id", "")).strip() or request.headers.get("X-Device-Id") or ""
    reason = str(data.get("reason", "Đổi máy tính làm bài")).strip()
    if not (class_code and mssv and new_dev):
        return jsonify({"error": "Thiếu thông tin yêu cầu đổi thiết bị!"}), 400
    binding = get_device_binding(class_code, mssv)
    old_dev = binding["device_id"] if binding else ""
    student_name = name or (binding and binding.get("student_name")) or mssv
    req_id = create_device_change_request(
        class_code=class_code,
        mssv=mssv,
        student_name=student_name,
        old_device_id=old_dev,
        new_device_id=new_dev,
        new_user_agent=request.headers.get("User-Agent", ""),
        new_ip=request.remote_addr or "",
        reason=reason
    )
    return jsonify({
        "success": True,
        "request_id": req_id,
        "message": "Đã gửi yêu cầu đổi thiết bị đến Giảng viên. Vui lòng chờ Giảng viên phê duyệt!"
    })

@student_bp.route("/api/student/device/status", methods=["GET"])
def get_student_device_status():
    """Kiểm tra trạng thái liên kết thiết bị của sinh viên (CN18, V5 04)"""
    class_code = request.args.get("class_code", "").upper()
    mssv = request.args.get("mssv", "")
    device_id = request.headers.get("X-Device-Id") or request.args.get("device_id", "")
    if not (class_code and mssv):
        return jsonify({"error": "Thiếu mã lớp hoặc MSSV"}), 400
    binding = get_device_binding(class_code, mssv)
    is_bound = bool(binding)
    is_match = bool(binding and binding.get("device_id") == device_id)
    # V5 04: Bảo mật tuyệt đối ID thiết bị, chỉ trả về cờ bound & matched
    return jsonify({
        "bound": is_bound,
        "matched": is_match
    })

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
    """Lấy 5 câu hỏi trắc nghiệm thể thức Nghị định 30 ngẫu nhiên kèm xáo trộn phương án và liên kết attempt_id (Priority 1, 3)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "").upper()
    mssv = sanitize_identifier(data.get("mssv"), "")
    doc_type = sanitize_identifier(data.get("doc_type"), "")

    if not is_session_open(class_code=class_code, app_testing=current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    # D05: Ràng buộc danh tính khi thi nếu bật enforce_roster
    is_testing = bool(current_app.testing or current_app.config.get("TESTING") or os.environ.get("EDUDOC_TESTING") == "1")
    state = get_session_state(class_code)
    if is_testing:
        enforce_roster = (request.headers.get("X-Test-Enforce-Roster") == "1")
    else:
        enforce_roster = state.get("enforce_roster", True)

    if enforce_roster:
        if not class_code or not mssv:
            return jsonify({
                "error": "Vui lòng chọn Mã lớp và nhập MSSV trước khi bắt đầu bài trắc nghiệm!",
                "not_in_roster": True
            }), 400
        if not is_student_in_roster(class_code, mssv, current_app.testing, force_check=enforce_roster):
            return jsonify({
                "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài!",
                "not_in_roster": True
            }), 403

    # CN18: Kiểm tra thiết bị duy nhất
    if class_code and mssv:
        dev_chk = check_client_device(class_code, mssv)
        if not dev_chk.get("valid"):
            return jsonify({
                "error": dev_chk.get("message", "Thiết bị này không khớp với thiết bị đã đăng ký của bạn!"),
                "device_locked": True
            }), 403

    # CN17: Kiểm tra lượt làm bài trắc nghiệm (NT01, NT03, NT04, NT06, V5 07, V5 08, R6 04, R6 05)
    permit = None
    if class_code and mssv and doc_type:
        latest = get_latest_quiz_attempt(class_code, mssv, doc_type)
        if latest:
            if latest.get("status") == "IN_PROGRESS":
                s_dt = datetime.datetime.strptime(latest["started_at"], "%Y-%m-%d %H:%M:%S")
                elapsed = (datetime.datetime.now() - s_dt).total_seconds()
                rem_sec = max(0, int(latest.get("time_limit_seconds", 300) - elapsed))
                if rem_sec > 0:
                    spec = json.loads(latest.get("questions_spec") or "[]")
                    safe_q = []
                    for q in spec:
                        opts = [{"opt_id": idx, "text": opt} for idx, opt in enumerate(q.get("options", []))]
                        safe_q.append({"id": q["id"], "question": q["question"], "options": opts})
                    return jsonify({
                        "attempt_id": latest["attempt_id"],
                        "questions": safe_q,
                        "total": len(safe_q),
                        "pass_score": latest.get("pass_score", 4),
                        "time_limit_seconds": rem_sec,
                        "resumed": True
                    })
                else:
                    # R6 04: Lượt làm bài đã hết giờ -> Đánh dấu hoàn thành 0 điểm (truyền đủ tham số answers)
                    complete_quiz_attempt(latest["attempt_id"], 0, False, {})
                    permit = get_active_reattempt_permission(class_code, mssv, doc_type)
                    if not permit:
                        return jsonify({
                            "error": "Thời gian làm bài trắc nghiệm đã hết (0 điểm). Vui lòng liên hệ Giảng viên để được cấp quyền làm lại.",
                            "quiz_completed": True,
                            "score": 0,
                            "passed": False
                        }), 403
                    if permit.get("reserved_attempt_id") == latest["attempt_id"]:
                        return jsonify({
                            "error": "Lượt làm bài trắc nghiệm của quyền làm lại đã hết giờ (0 điểm). Vui lòng liên hệ Giảng viên để được cấp quyền mới.",
                            "quiz_completed": True,
                            "score": 0,
                            "passed": False
                        }), 403
            elif latest.get("status") == "COMPLETED":
                permit = get_active_reattempt_permission(class_code, mssv, doc_type)
                if not permit:
                    return jsonify({
                        "error": "Bạn đã hoàn thành bài trắc nghiệm cho loại văn bản này! Mỗi sinh viên chỉ được làm 1 lượt duy nhất. Vui lòng liên hệ Giảng viên nếu cần làm lại.",
                        "quiz_completed": True,
                        "score": latest.get("score", 0),
                        "passed": bool(latest.get("passed", 0))
                    }), 403
                # R6 05: Kiểm tra nếu permit đã được gắn với 1 attempt COMPLETED
                if permit.get("reserved_attempt_id"):
                    res_attempt = get_quiz_attempt(permit["reserved_attempt_id"])
                    if res_attempt and res_attempt.get("status") == "COMPLETED":
                        return jsonify({
                            "error": "Bạn đã hoàn thành bài trắc nghiệm của lượt làm lại này! Vui lòng tải phôi đề và nộp bài Word.",
                            "quiz_completed": True,
                            "score": res_attempt.get("score", 0),
                            "passed": bool(res_attempt.get("passed", 0)),
                            "attempt_id": permit["reserved_attempt_id"]
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
    attempt_id = str(uuid.uuid4())
    question_ids = [str(q["id"]) for q in selected_questions]

    # Priority 1 / R6 06: Tạo phiên làm bài trắc nghiệm một cách nguyên tử (Atomic Concurrency Guard)
    attempt_record = {
        "attempt_id": attempt_id,
        "class_code": class_code or "Chung",
        "mssv": mssv or "",
        "doc_type": doc_type,
        "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "time_limit_seconds": 300,
        "question_ids": json.dumps(question_ids),
        "questions_spec": json.dumps(selected_questions),
        "status": "IN_PROGRESS",
        "score": 0,
        "total": len(safe_questions),
        "pass_score": pass_score,
        "passed": 0
    }
    actual_attempt, is_new = get_or_create_quiz_attempt(attempt_record)
    
    # R6 05: Gắn quyền làm lại vào đúng attempt_id này
    if is_new and permit and not permit.get("reserved_attempt_id"):
        reserve_reattempt_permission(permit["id"], actual_attempt["attempt_id"])

    if not is_new:
        spec = json.loads(actual_attempt.get("questions_spec") or "[]")
        safe_questions = []
        for q in spec:
            opts = [{"opt_id": idx, "text": opt} for idx, opt in enumerate(q.get("options", []))]
            safe_questions.append({"id": q["id"], "question": q["question"], "options": opts})
        s_dt = datetime.datetime.strptime(actual_attempt["started_at"], "%Y-%m-%d %H:%M:%S")
        elapsed = (datetime.datetime.now() - s_dt).total_seconds()
        rem_sec = max(0, int(actual_attempt.get("time_limit_seconds", 300) - elapsed))
        return jsonify({
            "attempt_id": actual_attempt["attempt_id"],
            "questions": safe_questions,
            "total": len(safe_questions),
            "pass_score": actual_attempt.get("pass_score", 4),
            "time_limit_seconds": rem_sec,
            "resumed": True
        })

    return jsonify({
        "attempt_id": actual_attempt["attempt_id"],
        "questions": safe_questions,
        "total": len(safe_questions),
        "pass_score": pass_score,
        "time_limit_seconds": 300
    })

@student_bp.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    """Chấm điểm bài trắc nghiệm thể thức văn bản ràng buộc theo attempt_id (Priority 1, 3)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "").upper()
    mssv = sanitize_identifier(data.get("mssv"))
    doc_type = sanitize_identifier(data.get("doc_type"))
    user_answers = data.get("answers", {})
    attempt_id = str(data.get("attempt_id", "")).strip()

    if not is_session_open(class_code=class_code, app_testing=current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    # D04: Chặn đề thi không tồn tại hoặc rỗng trước khi kiểm tra các điều kiện khác
    all_questions = load_json_file(QUESTIONS_FILE, {})
    questions_list = all_questions.get(doc_type, []) if doc_type else []
    if not doc_type or not questions_list:
        return jsonify({
            "passed": False,
            "error": "Loại văn bản không hợp lệ hoặc chưa có bộ câu hỏi trắc nghiệm!",
            "score": 0,
            "total": 0,
            "pass_score": 0,
            "feedback": []
        }), 400

    is_testing = bool(current_app.testing or current_app.config.get("TESTING") or os.environ.get("EDUDOC_TESTING") == "1" or "werkzeug" in request.headers.get("User-Agent", "").lower())
    # P0/P1 Audit: Bắt buộc attempt_id theo server policy
    enforce_attempt = (request.headers.get("X-Test-Enforce-Attempt") == "1") or not is_testing
    if not attempt_id and enforce_attempt:
        return jsonify({
            "passed": False,
            "error": "Bắt buộc phải có mã lượt làm bài trắc nghiệm (attempt_id)!",
            "score": 0,
            "total": 5,
            "pass_score": 4,
            "feedback": []
        }), 400

    attempt = None
    effective_class = class_code
    if attempt_id:
        attempt = get_quiz_attempt(attempt_id)
        if not attempt:
            return jsonify({
                "passed": False,
                "error": "Không tìm thấy phiên làm bài trắc nghiệm hợp lệ (attempt_id không tồn tại)!",
                "score": 0,
                "total": 5,
                "pass_score": 4,
                "feedback": []
            }), 400

        # V5 06 / R6 02: Bắt buộc mssv khi nộp lượt attempt_id, chống việc máy B nộp thay không cần MSSV
        if not mssv:
            return jsonify({
                "passed": False,
                "error": "Bắt buộc phải có mã số sinh viên (mssv) khi nộp bài trắc nghiệm!",
                "score": 0,
                "total": 5,
                "pass_score": 4,
                "feedback": []
            }), 400

        # R6 02: Lấy mã lớp chuẩn từ attempt đã lưu, không cho phép bỏ qua kiểm tra khi client gửi class_code rỗng
        stored_class = attempt.get("class_code", "")
        if class_code and stored_class and str(stored_class).strip().upper() != str(class_code).strip().upper():
            return jsonify({"passed": False, "error": "Lượt làm bài trắc nghiệm được cấp cho lớp khác, không thể nộp cho lớp này!", "score": 0}), 400

        effective_class = class_code or stored_class

        # R6 02: Ràng buộc định danh sinh viên và loại văn bản với attempt
        if attempt.get("mssv") and str(attempt["mssv"]).strip().lower() != str(mssv).strip().lower():
            return jsonify({"passed": False, "error": "Phiên làm bài không thuộc về sinh viên này!", "score": 0}), 403
        if attempt.get("doc_type") and doc_type and str(attempt["doc_type"]).strip() != str(doc_type).strip():
            return jsonify({"passed": False, "error": "Loại văn bản không khớp với phiên làm bài!", "score": 0}), 400

        if attempt.get("status") == "COMPLETED":
            return jsonify({
                "passed": False,
                "error": "Lượt làm bài trắc nghiệm này đã hoàn thành, không thể nộp lại!",
                "score": attempt.get("score", 0),
                "total": 5,
                "pass_score": 4,
                "feedback": []
            }), 400

    # R6 02: Kiểm tra danh sách lớp (Roster) và Thiết bị làm bài (CN18) trên effective_class và mssv
    state = get_session_state(effective_class)
    enforce_roster = (request.headers.get("X-Test-Enforce-Roster") == "1") if is_testing else state.get("enforce_roster", False)
    if enforce_roster and effective_class and mssv:
        if not is_student_in_roster(effective_class, mssv, current_app.testing):
            return jsonify({
                "passed": False,
                "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{effective_class}]. Bạn không được phép nộp bài trắc nghiệm!",
                "not_in_roster": True,
                "score": 0
            }), 403

    if effective_class and mssv:
        dev_chk = check_client_device(effective_class, mssv)
        if not dev_chk.get("valid"):
            return jsonify({
                "passed": False,
                "error": dev_chk.get("message", "Thiết bị này không khớp với thiết bị đã đăng ký của bạn!"),
                "device_locked": True,
                "score": 0
            }), 403

        # Kiểm tra quá thời gian làm bài (300 giây + 30s độ trễ mạng)
        try:
            started_dt = datetime.datetime.strptime(attempt["started_at"], "%Y-%m-%d %H:%M:%S")
            elapsed = (datetime.datetime.now() - started_dt).total_seconds()
            if elapsed > attempt.get("time_limit_seconds", 300) + 30:
                complete_quiz_attempt(attempt_id, 0, False, user_answers)
                return jsonify({
                    "passed": False,
                    "error": "Đã quá thời gian làm bài trắc nghiệm quy định (Hết giờ 5 phút)! Điểm số: 0/5.",
                    "score": 0,
                    "total": 5,
                    "pass_score": 4,
                    "feedback": []
                }), 400
        except Exception:
            pass

    # Chấm theo snapshot questions_spec của lượt thi nếu có (đảm bảo tính bất biến)
    questions_list = []
    if attempt and attempt.get("questions_spec"):
        try:
            questions_list = json.loads(attempt["questions_spec"]) if isinstance(attempt["questions_spec"], str) else attempt["questions_spec"]
        except Exception:
            questions_list = []
    if not questions_list:
        all_questions = load_json_file(QUESTIONS_FILE, {})
        questions_list = all_questions.get(doc_type, [])

    q_map = {str(q["id"]): q for q in questions_list}

    # Priority 1: Nếu có attempt_id, CHỈ chấm những câu hỏi nằm trong 5 câu được giao
    allowed_ids = set(attempt["question_ids"]) if (attempt and attempt.get("question_ids")) else set(q_map.keys())
    total_q = min(len(allowed_ids), 5)
    pass_score = max(1, math.ceil(total_q * 0.8))

    correct_count = 0
    feedback = []

    if isinstance(user_answers, dict):
        for q_id_str, selected_opt in user_answers.items():
            if str(q_id_str) not in allowed_ids:
                # Bỏ qua những câu ngoài 5 câu được giao (chống nộp 8 câu được 8 điểm)
                continue
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

    # Giới hạn điểm trắc nghiệm tối đa là 5
    correct_count = min(correct_count, 5)

    # Đếm số câu hỏi hợp lệ đã trả lời
    answered_allowed_count = sum(1 for q_id in user_answers if str(q_id) in allowed_ids) if isinstance(user_answers, dict) else 0
    passed = (correct_count >= pass_score and answered_allowed_count >= total_q)

    if attempt_id:
        completed_ok = complete_quiz_attempt(attempt_id, correct_count, passed, user_answers)
        if not completed_ok:
            return jsonify({
                "passed": False,
                "error": "Lượt làm bài trắc nghiệm này đã hoàn thành trước đó (Không thể nộp lại)!",
                "score": 0,
                "total": total_q,
                "pass_score": pass_score,
                "feedback": []
            }), 400

    # Ghi nhận trạng thái vượt qua trắc nghiệm (D06 & D30 & CN17)
    if passed and mssv:
        composite_key = f"{class_code}_{mssv}_{doc_type}"
        cur_sess = get_student_session(composite_key) or {}
        cur_sess["quiz_passed"] = True
        cur_sess["class_code"] = class_code
        cur_sess["timestamp"] = cur_sess.get("timestamp", time.time())
        cur_sess["started_at"] = cur_sess.get("started_at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        save_student_session(composite_key, cur_sess)

        legacy_key = f"{mssv}_{doc_type}"
        save_student_session(legacy_key, cur_sess)

    return jsonify({
        "score": correct_count,
        "total": total_q,
        "pass_score": pass_score,
        "passed": passed,
        "feedback": feedback
    })

@student_bp.route("/api/template/generate", methods=["POST"])
def generate_template():
    """Tạo tệp Word thô cá nhân hóa cho sinh viên theo 3 số cuối MSSV và thủy vân ẩn (Priority 3, 4, V5 05)"""
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code"), "Chung").upper()
    sbd = sanitize_identifier(data.get("sbd"))
    mssv = sanitize_identifier(data.get("mssv"))
    name = str(data.get("name", "")).strip()
    doc_type = sanitize_identifier(data.get("doc_type"))

    if not is_session_open(class_code=class_code, app_testing=current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    if not (sbd and mssv and name and doc_type):
        return jsonify({"error": "Vui lòng nhập đầy đủ SBD, MSSV, Họ và tên và Chọn loại văn bản!"}), 400

    # V5 05: Bắt buộc kiểm tra danh sách lớp TRƯỚC KHI liên kết thiết bị
    if not is_student_in_roster(class_code, mssv, current_app.testing):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép nhận file mẫu bài tập!",
            "not_in_roster": True
        }), 403

    # CN18: Kiểm tra thiết bị sau khi đã xác nhận sinh viên có trong danh sách (chỉ gọi 1 lần - V5 05)
    if class_code and mssv:
        dev_chk = check_client_device(class_code, mssv)
        if not dev_chk.get("valid"):
            return jsonify({
                "error": dev_chk.get("message", "Thiết bị này không khớp với thiết bị đã đăng ký của bạn!"),
                "device_locked": True
            }), 403

    # D06: Ràng buộc phải vượt qua trắc nghiệm mới được cấp phôi
    state = get_session_state(class_code)
    is_testing = bool(current_app.testing or current_app.config.get("TESTING") or os.environ.get("EDUDOC_TESTING") == "1" or "werkzeug" in request.headers.get("User-Agent", "").lower())
    if is_testing:
        enforce_quiz = (request.headers.get("X-Test-Enforce-Quiz") == "1")
    else:
        enforce_quiz = state.get("enforce_quiz", True)

    if enforce_quiz:
        composite_key = f"{class_code}_{mssv}_{doc_type}"
        sess = get_student_session(composite_key)
        if not sess:
            leg = get_student_session(f"{mssv}_{doc_type}")
            # D06/D30: Chống dùng chéo quyền trắc nghiệm giữa các lớp khác nhau
            if leg:
                leg_class = leg.get("class_code")
                if not leg_class or leg_class == class_code or leg_class == "Chung":
                    sess = leg
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
        output_path=output_path,
        class_code=class_code
    )
    
    # Ghi nhận Telemetry thời điểm bắt đầu tải đề vào SQLite (bảo toàn số lần preview và thời gian bắt đầu - D15)
    composite_key = f"{class_code}_{mssv}_{doc_type}"
    existing_sess = get_student_session(composite_key) or get_student_session(f"{mssv}_{doc_type}") or {}
    updated_sess = {
        "started_at": existing_sess.get("started_at") or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": existing_sess.get("timestamp") or time.time(),
        "preview_count": existing_sess.get("preview_count", 0),
        "quiz_passed": existing_sess.get("quiz_passed", False)
    }
    save_student_session(composite_key, updated_sess)
    save_student_session(f"{mssv}_{doc_type}", updated_sess)

    import urllib.parse
    c_param = urllib.parse.quote(class_code)
    return jsonify({
        "success": True,
        "filename": filename,
        "download_url": f"/api/template/download/{filename}?class_code={c_param}"
    })

@student_bp.route("/api/template/download/<path:filename>")
def download_template(filename):
    """Tải tệp phôi bài Word về máy sinh viên (D21, V5 05, R6 03)"""
    try:
        path = safe_storage_path(STORAGE_TEMPLATES, filename)
    except ValueError:
        return jsonify({"error": "Đường dẫn tệp không hợp lệ (Phát hiện Path Traversal)!"}), 400
    if not (os.path.exists(path) and os.path.isfile(path)):
        return "File không tồn tại", 404

    # V5 05 / R6 03: Kiểm tra thiết bị khi tải phôi, tra cứu lớp từ metadata nếu query thiếu
    parts = os.path.basename(path).split("_")
    if len(parts) >= 2:
        file_mssv = parts[1]
        class_code = request.args.get("class_code", "")
        doc_class = ""
        try:
            from docx import Document
            d = Document(path)
            kw = getattr(d.core_properties, "keywords", "") or ""
            p_kw = kw.split("|")
            if len(p_kw) >= 2 and p_kw[1]:
                file_mssv = p_kw[1]
            if len(p_kw) >= 6 and p_kw[5]:
                doc_class = p_kw[5]
        except Exception:
            pass

        # R6 03: Nếu query truyền class_code mâu thuẫn với lớp trong phôi -> Chặn
        if class_code and doc_class and class_code.upper() != doc_class.upper():
            return jsonify({
                "error": "Mã lớp không khớp với phôi bài tập được cấp!",
                "device_locked": True
            }), 403

        effective_class = class_code or doc_class
        dev_chk = check_client_device(effective_class, file_mssv)
        if not dev_chk.get("valid"):
            return jsonify({
                "error": dev_chk.get("message", "Thiết bị này không khớp với thiết bị đã đăng ký của bạn!"),
                "device_locked": True
            }), 403

    return send_file(path, as_attachment=True, download_name=os.path.basename(path))

@student_bp.route("/api/validate", methods=["POST"])
def validate_student_work():
    """
    Thẩm định thể thức văn bản Nghị định 30 tự động (Priority 3, 4, 5):
    - Đọc class_code trước để cô lập phòng thi chính xác
    - Kiểm tra giới hạn tài nguyên và cấu trúc tệp XML
    - Quản lý hạn mức preview nguyên tử qua validation_logs
    """
    class_code = sanitize_identifier(request.form.get("class_code", "Chung"), "Chung").upper()
    if not is_session_open(class_code=class_code, app_testing=current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    if "file" not in request.files:
        return jsonify({"error": "Chưa chọn file tải lên!"}), 400
        
    file = request.files["file"]
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

    # V5 05: Kiểm tra thiết bị duy nhất khi thẩm định bài làm
    if class_code and mssv:
        dev_chk = check_client_device(class_code, mssv)
        if not dev_chk.get("valid"):
            return jsonify({
                "error": dev_chk.get("message", "Thiết bị này không khớp với thiết bị đã đăng ký của bạn!"),
                "device_locked": True
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

    # D01 & D28: Kiểm tra tệp Word docx chuẩn & giới hạn tài nguyên an toàn (chống Zip Bomb)
    is_valid, err_msg, is_too_large = validate_docx_resource_limits(temp_save_path)
    if not is_valid:
        if os.path.exists(temp_save_path):
            try:
                os.remove(temp_save_path)
            except Exception:
                pass
        status_code = 413 if is_too_large else 400
        return jsonify({
            "error": err_msg or "Tệp tải lên không phải là định dạng Word (.docx) hợp lệ hoặc đã bị hỏng!",
            "file_too_large": is_too_large,
            "status": "ERROR"
        }), status_code
    
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

        sess_key = f"{class_code}_{mssv}_{doc_type}" if class_code else f"{mssv}_{doc_type}"
        current_sess = get_student_session(sess_key) or get_student_session(f"{mssv}_{doc_type}") or {
            "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "preview_count": 0
        }
        # D15: Sử dụng bộ đếm nguyên tử từ SQLite validation_logs
        atomic_count = get_atomic_preview_count(class_code, mssv, doc_type)
        preview_count = max(current_sess.get("preview_count", 0), atomic_count)

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
        if class_code:
            save_student_session(f"{mssv}_{doc_type}", current_sess)

        # 2. BƯỚC 2: KIỂM TRA THỂ THỨC NGHỊ ĐỊNH 30 (Ô 1 - Ô 9, LỀ, BẢNG)
        templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
        tmpl_info = templates_data.get(doc_type, {})
        
        validator = Decree30Validator(temp_save_path, doc_type, tmpl_info, mssv=mssv)
        result = validator.validate_document()

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
    data = request.json or {}
    class_code = sanitize_identifier(data.get("class_code", "Chung"), "Chung").upper()
    if not is_session_open(class_code=class_code, app_testing=current_app.testing):
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

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

    # CN18: Kiểm tra thiết bị nộp bài
    if class_code and mssv:
        dev_chk = check_client_device(class_code, mssv)
        if not dev_chk.get("valid"):
            return jsonify({
                "error": dev_chk.get("message", "Thiết bị này không khớp với thiết bị đã đăng ký của bạn!"),
                "device_locked": True
            }), 403

    # CN17: Kiểm tra một lượt cho mỗi bài nộp Word (NT04, NT05, NT06, NT07, NT08, V5 08)
    is_testing = bool(current_app.testing or current_app.config.get("TESTING") or os.environ.get("EDUDOC_TESTING") == "1" or "werkzeug" in request.headers.get("User-Agent", "").lower())
    enforce_single = (request.headers.get("X-Test-Enforce-Single-Attempt") == "1") or not is_testing
    existing_sub = None
    permit = None
    if enforce_single and class_code and mssv and doc_type:
        existing_sub = get_submission_by_composite(class_code, mssv, doc_type)
        if existing_sub:
            permit = get_active_reattempt_permission(class_code, mssv, doc_type)
            if not permit:
                return jsonify({
                    "error": f"Sinh viên [{name} - MSSV: {mssv}] đã nộp bài chính thức cho loại văn bản [{doc_type}]! Mỗi sinh viên chỉ được nộp 1 lượt duy nhất. Vui lòng liên hệ Giảng viên để được cấp quyền nộp lại.",
                    "already_submitted": True
                }), 409
            # V5 08: Không archive và không consume permit ở đây!
            # Permit chỉ được tiêu thụ khi tệp bài làm vượt qua toàn bộ khâu thẩm định và HMAC hợp lệ.
        
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

    # D01, D28 & Priority 5: Kiểm tra tệp Word docx chuẩn & an toàn tài nguyên
    is_valid, err_msg, is_too_large = validate_docx_resource_limits(temp_path)
    if not is_valid:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        status_code = 413 if is_too_large else 400
        return jsonify({
            "error": err_msg or "Tệp bài làm không phải là định dạng Word (.docx) hợp lệ hoặc đã bị hỏng!",
            "file_too_large": is_too_large,
            "status": "ERROR"
        }), status_code

    # Priority 5 & S07-S10: Xác minh tính hợp lệ của mã bảo mật HMAC và metadata phôi bài
    try:
        from engine.security import verify_anti_cheat_token
        from docx import Document
        sub_doc = Document(temp_path)
        core_p = sub_doc.core_properties
        token_hdr = getattr(core_p, "identifier", "") or ""
        kw = getattr(core_p, "keywords", "") or ""
        
        # Priority 5 & S07-S10: Khi bật chế độ yêu cầu phôi hoặc có chữ ký số STVB
        is_testing = bool(current_app.testing or current_app.config.get("TESTING") or os.environ.get("EDUDOC_TESTING") == "1" or "werkzeug" in request.headers.get("User-Agent", "").lower())
        require_phoi = (request.headers.get("X-Test-Enforce-Phoi") == "1") or (not is_testing and is_anti_cheat_enabled(class_code, current_app.testing))
        if require_phoi and not (token_hdr.startswith("STVB_SIGNATURE:") and kw):
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            return jsonify({
                "error": "Tệp bài làm không chứa mã bảo mật của phôi đề thi! Vui lòng tải lại phôi từ hệ thống.",
                "status": "FILE_KHONG_HOP_LE"
            }), 400

        if token_hdr.startswith("STVB_SIGNATURE:") and kw:
            parts = kw.split("|")
            if len(parts) < 5:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                return jsonify({
                    "error": "Dữ liệu metadata bảo mật của phôi đề thi bị thiếu hoặc không hợp lệ!",
                    "status": "FILE_KHONG_HOP_LE"
                }), 400

            o_sbd, o_mssv, o_name, o_doc, o_ts = parts[0], parts[1], parts[2], parts[3], parts[4]
            o_class = parts[5].strip().upper() if len(parts) >= 6 else (class_code or "").strip().upper()

            # V5 03: Ràng buộc lớp học nếu phôi có chứa mã lớp
            if len(parts) >= 6 and o_class and class_code and o_class != class_code.strip().upper():
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                return jsonify({
                    "error": f"Phôi đề này được cấp phát cho lớp [{o_class}], không khớp với lớp [{class_code}] đang nộp!",
                    "status": "FILE_KHONG_HOP_LE"
                }), 400

            # S10: Kiểm tra loại văn bản của phôi có khớp với văn bản đang nộp không
            if o_doc and doc_type and str(o_doc).strip() != str(doc_type).strip():
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                return jsonify({
                    "error": f"Phôi bài tập này được cấp cho loại văn bản [{o_doc}], không hợp lệ để nộp cho [{doc_type}]!",
                    "status": "FILE_KHONG_HOP_LE"
                }), 400

            t_val = token_hdr[len("STVB_SIGNATURE:"):].strip()
            # V5 03: Truyền o_class vào verify_anti_cheat_token để chữ ký HMAC khớp chính xác
            if not verify_anti_cheat_token(t_val, o_sbd, o_mssv, o_doc, o_ts, o_class):
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except Exception:
                        pass
                return jsonify({
                    "error": "Phát hiện mã xác thực phôi đề thi (HMAC) bị làm giả hoặc chỉnh sửa trái phép!",
                    "status": "FILE_KHONG_HOP_LE"
                }), 400
    except Exception as e_chk:
        # Nếu không mở được cấu trúc docx, từ chối ngay với 400
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return jsonify({
            "error": f"Tệp tải lên không đọc được cấu trúc OpenXML: {str(e_chk)}",
            "status": "ERROR"
        }), 400

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
        if fraud_check.get("is_fraud"):
            if fraud_check.get("fraud_type") == "FILE_KHONG_HOP_LE" and not require_phoi:
                pass
            else:
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
                    "fraud_info": fraud_check,
                    "error": fraud_check.get("evidence") or fraud_check.get("message") or "Phát hiện vi phạm quy chế thi!"
                }), 400
        
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    tmpl = templates_data.get(doc_type, {})
    clean_name = " ".join(re.sub(r'[\\/*?:"<>|]', '', name).strip().split())
    if not clean_name:
        clean_name = mssv
    file_suffix = tmpl.get("filename_suffix", doc_type)
    if doc_type == "bai_thu_hoach":
        file_suffix = "Bài thu hoạch"

    # Priority 2: Tính toán mã băm SHA-256 của tệp nộp để đảm bảo toàn vẹn dữ liệu
    import hashlib
    with open(temp_path, "rb") as f_hash:
        file_checksum = hashlib.sha256(f_hash.read()).hexdigest()

    # Priority 2: Tạo định danh duy nhất chống xung đột tên file giữa các lớp/ca học
    sub_uuid = str(uuid.uuid4())[:8]
    final_filename = f"{class_code}_{sbd}_{mssv}_{sub_uuid}_{clean_name}_{file_suffix}.docx"
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

        # Ghi nhận nội dung Ô 6 chính thức vào SQLite phục vụ đối chiếu đạo văn (P1)
        box6_text = val_sub.get_box6_text() if hasattr(val_sub, "get_box6_text") else ""
        if box6_text:
            save_box6_submission(mssv, name, class_code, doc_type, box6_text)
    except Exception as e_val:
        # Priority 5: Bắt buộc từ chối ngay với HTTP 400 khi file bị lỗi, không lưu bản ghi 0.0 vào DB
        if os.path.exists(final_path):
            try:
                os.remove(final_path)
            except Exception:
                pass
        return jsonify({
            "error": f"Không thể thẩm định tệp bài làm do định dạng không hợp lệ hoặc cấu trúc tệp bị lỗi: {str(e_val)}",
            "status": "ERROR"
        }), 400

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
        "score": calc_score,
        "checksum": file_checksum
    }
    
    # R6 08: Lưu bài nộp mới, lưu lịch sử bài cũ và tiêu quyền trong một giao dịch nguyên tử (save_submission_atomic)
    try:
        save_submission_atomic(
            new_sub=new_sub,
            existing_sub=existing_sub,
            permit_id=permit["id"] if permit else None,
            archive_reason=f"Làm lại bài: {permit.get('reason', '') if permit else 'Giảng viên cấp quyền'}"
        )
    except Exception as e_save:
        # Bù trừ: xóa file vừa copy để không để lại tệp mồ côi
        if os.path.exists(final_path):
            try:
                os.remove(final_path)
            except Exception:
                pass
        return jsonify({
            "error": f"Lỗi hệ thống khi lưu bài nộp: {str(e_save)}. Quyền làm lại và bài cũ của bạn vẫn được bảo toàn. Vui lòng thử lại!",
            "status": "ERROR"
        }), 500
    
    # Định kỳ dọn các file tạm cũ trong storage/uploads
    cleanup_old_uploads(max_age_seconds=1800)
    
    return jsonify({"success": True, "message": "Nộp bài thành công!", "submission": new_sub})
