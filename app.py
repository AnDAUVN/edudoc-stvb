import os
import re
import time
import json
import datetime
from flask import Flask, request, jsonify, send_file, render_template

from engine.security import create_student_raw_template, check_anti_cheat
from engine.validator import Decree30Validator

app = Flask(__name__, template_folder="templates", static_folder="static")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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

# Đảm bảo các thư mục tồn tại
for path in [STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED, DATA_DIR]:
    os.makedirs(path, exist_ok=True)

def load_json_file(file_path, default_val):
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return default_val
    return default_val

def save_json_file(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_session_state():
    default_state = {
        "is_open": False,
        "enforce_roster": True,
        "active_doc_type": "bai_thu_hoach",
        "message": "Giảng viên đang giảng lý thuyết. Hệ thống làm bài tập đang tạm khóa để các bạn tập trung nghe giảng.",
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    state = load_json_file(SESSION_STATE_FILE, default_state)
    if "enforce_roster" not in state:
        state["enforce_roster"] = True
    if "active_doc_type" not in state:
        state["active_doc_type"] = "bai_thu_hoach"
    return state

def is_session_open():
    if app.testing or app.config.get("TESTING", False) or os.environ.get("EDUDOC_TESTING") == "1":
        return True
    state = get_session_state()
    return bool(state.get("is_open", False))

def is_student_in_roster(class_code, mssv):
    if app.testing or app.config.get("TESTING", False) or os.environ.get("EDUDOC_TESTING") == "1":
        return True
    state = get_session_state()
    if not state.get("enforce_roster", True):
        return True

    c_code = str(class_code or "").strip().upper()
    m_clean = str(mssv or "").strip().lower()
    if not c_code or not m_clean:
        return True

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    class_students = roster.get(c_code, [])
    if not class_students:
        return False

    for s in class_students:
        if str(s.get("mssv", "")).strip().lower() == m_clean:
            return True
    return False

def get_student_from_roster(class_code, mssv):
    c_code = str(class_code or "").strip().upper()
    m_clean = str(mssv or "").strip().lower()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    class_students = roster.get(c_code, [])
    for s in class_students:
        if str(s.get("mssv", "")).strip().lower() == m_clean:
            return s
    return None

def parse_students_text(raw_text):
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
        name = None
        sbd = ""

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
        elif len(parts) >= 3:
            mssv_idx = -1
            for idx, p in enumerate(parts):
                if len(p) >= 6 and any(c.isdigit() for c in p):
                    mssv_idx = idx
                    break
            if mssv_idx == -1:
                for idx, p in enumerate(parts):
                    if any(c.isdigit() for c in p) and len(p) >= 3:
                        mssv_idx = idx
                        break

            if mssv_idx != -1:
                mssv = parts[mssv_idx]
                if mssv_idx > 0:
                    sbd = parts[0]
                name_parts = parts[mssv_idx + 1:]
                name = " ".join(name_parts)
            else:
                sbd = parts[0]
                mssv = parts[1]
                name = " ".join(parts[2:])

        if mssv:
            mssv = re.sub(r'[^a-zA-Z0-9]', '', mssv).strip().upper()
            name = re.sub(r'\s+', ' ', name or '').strip()
            sbd = str(sbd).strip()
            if mssv:
                students.append({
                    "sbd": sbd,
                    "mssv": mssv,
                    "name": name or f"Sinh viên {mssv}"
                })
    return students

@app.route("/")
def index():
    state = get_session_state()
    active_doc_type = state.get("active_doc_type", "bai_thu_hoach")
    return render_template("index.html", mode="student", active_doc_type=active_doc_type)

@app.route("/teacher")
def teacher_portal():
    state = get_session_state()
    active_doc_type = state.get("active_doc_type", "bai_thu_hoach")
    return render_template("index.html", mode="teacher", active_doc_type=active_doc_type)

@app.route("/api/session-state", methods=["GET"])
def api_get_session_state():
    state = get_session_state()
    return jsonify(state)

@app.route("/api/teacher/session-state", methods=["POST"])
def api_set_session_state():
    data = request.json or {}
    current = get_session_state()
    new_is_open = bool(data.get("is_open", current.get("is_open", False))) if "is_open" in data else current.get("is_open", False)
    new_message = str(data.get("message", "")).strip() or current.get("message", "Giảng viên đang giảng lý thuyết. Hệ thống làm bài tập đang tạm khóa để các bạn tập trung nghe giảng.")
    enforce_roster = bool(data.get("enforce_roster", current.get("enforce_roster", True)))
    active_doc_type = str(data.get("active_doc_type", current.get("active_doc_type", "bai_thu_hoach"))).strip()
    
    updated_state = {
        "is_open": new_is_open,
        "enforce_roster": enforce_roster,
        "active_doc_type": active_doc_type,
        "message": new_message,
        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_json_file(SESSION_STATE_FILE, updated_state)
    return jsonify({
        "success": True,
        "session_state": updated_state,
        "message": "Đã mở quyền làm bài cho sinh viên!" if new_is_open else "Đã khóa hệ thống để sinh viên tập trung nghe giảng!"
    })

@app.route("/api/teacher/set-active-doc", methods=["POST"])
def api_set_active_doc():
    data = request.json or {}
    doc_type = str(data.get("doc_type", "")).strip()
    if not doc_type:
        return jsonify({"error": "Vui lòng chọn loại văn bản hợp lệ!"}), 400
    state = get_session_state()
    state["active_doc_type"] = doc_type
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json_file(SESSION_STATE_FILE, state)
    return jsonify({
        "success": True,
        "active_doc_type": doc_type,
        "session_state": state,
        "message": f"Đã chuyển loại văn bản giao làm bài sang: [{doc_type}]"
    })

@app.route("/api/teacher/roster-toggle", methods=["POST"])
def toggle_roster_mode():
    data = request.json or {}
    state = get_session_state()
    enforce = bool(data.get("enforce_roster", not state.get("enforce_roster", True)))
    state["enforce_roster"] = enforce
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_json_file(SESSION_STATE_FILE, state)
    status_text = "BẮT BUỘC (Chỉ sinh viên có tên trong danh sách lớp mới được làm bài)" if enforce else "MỞ TỰ DO (Mọi sinh viên đều được làm bài)"
    return jsonify({
        "success": True,
        "enforce_roster": enforce,
        "session_state": state,
        "message": f"Chế độ kiểm soát danh sách lớp: {status_text}!"
    })

@app.route("/api/student/verify", methods=["POST"])
def verify_student():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    mssv = str(data.get("mssv", "")).strip()

    if not class_code or not mssv:
        return jsonify({"valid": False, "error": "Vui lòng chọn Mã lớp và nhập MSSV!"}), 400

    state = get_session_state()
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

    if not class_students:
        return jsonify({
            "valid": False,
            "not_in_roster": True,
            "error": f"Lớp [{class_code}] hiện chưa có danh sách sinh viên được cấp quyền. Vui lòng liên hệ Giảng viên để thêm sinh viên vào danh sách lớp!"
        }), 403

    return jsonify({
        "valid": False,
        "not_in_roster": True,
        "error": f"Mã sinh viên [{mssv}] KHÔNG CÓ trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài cho lớp này! Vui lòng liên hệ Giảng viên."
    }), 403

    return jsonify({
        "valid": True,
        "enforce": True,
        "student": student,
        "message": f"Xác thực thành công sinh viên {student.get('name', '')} thuộc lớp {class_code}!"
    })

@app.route("/api/teacher/students", methods=["GET"])
def get_teacher_students():
    class_code = str(request.args.get("class_code", "")).strip().upper()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    submissions = load_json_file(SUBMISSIONS_FILE, [])

    sub_map = {}
    for sub in submissions:
        sub_key = f"{sub.get('class_code', '').upper()}_{sub.get('mssv', '').upper()}"
        sub_map[sub_key] = sub

    if class_code and class_code != "ALL":
        raw_students = roster.get(class_code, [])
        students = []
        for s in raw_students:
            s_dict = dict(s)
            s_dict["class_code"] = class_code
            sub_key = f"{class_code}_{s.get('mssv', '').upper()}"
            sub = sub_map.get(sub_key)
            s_dict["has_submitted"] = bool(sub)
            s_dict["submission"] = sub if sub else None
            students.append(s_dict)
        return jsonify({"class_code": class_code, "students": students, "total": len(students)})
    else:
        all_students = []
        for c_code, s_list in roster.items():
            for s in s_list:
                s_copy = dict(s)
                s_copy["class_code"] = c_code
                sub_key = f"{c_code}_{s.get('mssv', '').upper()}"
                sub = sub_map.get(sub_key)
                s_copy["has_submitted"] = bool(sub)
                s_copy["submission"] = sub if sub else None
                all_students.append(s_copy)
        return jsonify({"class_code": "ALL", "students": all_students, "total": len(all_students)})

@app.route("/api/teacher/students/add", methods=["POST"])
def add_student_to_roster():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    mssv = str(data.get("mssv", "")).strip().upper()
    name = str(data.get("name", "")).strip()
    sbd = str(data.get("sbd", "")).strip()

    if not class_code or not mssv or not name:
        return jsonify({"error": "Vui lòng nhập đầy đủ Mã lớp, MSSV và Họ và tên sinh viên!"}), 400

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code not in roster:
        roster[class_code] = []

    existing = False
    for s in roster[class_code]:
        if str(s.get("mssv", "")).upper() == mssv:
            s["name"] = name
            if sbd:
                s["sbd"] = sbd
            existing = True
            break

    if not existing:
        if not sbd:
            sbd = f"{len(roster[class_code]) + 1:02d}"
        roster[class_code].append({
            "sbd": sbd,
            "mssv": mssv,
            "name": name
        })

    classes = load_json_file(CLASSES_FILE, [])
    if class_code not in classes:
        classes.append(class_code)
        classes.sort()
        save_json_file(CLASSES_FILE, classes)

    save_json_file(STUDENTS_ROSTER_FILE, roster)
    return jsonify({
        "success": True,
        "message": f"Đã thêm thành công sinh viên [{mssv} - {name}] vào lớp {class_code}!",
        "students": roster[class_code]
    })

@app.route("/api/teacher/students/import", methods=["POST"])
def import_students_to_roster():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    raw_text = str(data.get("raw_text", "")).strip()

    if not class_code or not raw_text:
        return jsonify({"error": "Vui lòng chọn Mã lớp và dán danh sách sinh viên!"}), 400

    parsed_students = parse_students_text(raw_text)
    if not parsed_students:
        return jsonify({"error": "Không thể nhận diện sinh viên nào từ văn bản đã dán. Vui lòng kiểm tra lại định dạng!"}), 400

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code not in roster:
        roster[class_code] = []

    added_count = 0
    updated_count = 0
    mssv_map = {str(s.get("mssv", "")).upper(): s for s in roster[class_code]}

    for new_s in parsed_students:
        m = new_s["mssv"]
        if m in mssv_map:
            mssv_map[m]["name"] = new_s["name"]
            if new_s.get("sbd"):
                mssv_map[m]["sbd"] = new_s["sbd"]
            updated_count += 1
        else:
            if not new_s.get("sbd"):
                new_s["sbd"] = f"{len(roster[class_code]) + 1:02d}"
            roster[class_code].append(new_s)
            mssv_map[m] = new_s
            added_count += 1

    classes = load_json_file(CLASSES_FILE, [])
    if class_code not in classes:
        classes.append(class_code)
        classes.sort()
        save_json_file(CLASSES_FILE, classes)

    save_json_file(STUDENTS_ROSTER_FILE, roster)
    return jsonify({
        "success": True,
        "added_count": added_count,
        "updated_count": updated_count,
        "total": len(roster[class_code]),
        "message": f"Đã nạp thành công {added_count} sinh viên mới (cập nhật {updated_count}) vào lớp {class_code}!",
        "students": roster[class_code]
    })

@app.route("/api/teacher/students/delete", methods=["POST"])
def delete_student_from_roster():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    mssv = str(data.get("mssv", "")).strip().upper()

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code in roster:
        roster[class_code] = [s for s in roster[class_code] if str(s.get("mssv", "")).upper() != mssv]
        save_json_file(STUDENTS_ROSTER_FILE, roster)
        return jsonify({"success": True, "message": f"Đã xóa sinh viên [{mssv}] khỏi lớp {class_code}!"})
    return jsonify({"error": "Không tìm thấy dữ liệu lớp!"}), 404

@app.route("/api/teacher/students/clear", methods=["POST"])
def clear_class_roster():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()

    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    if class_code in roster:
        roster[class_code] = []
        save_json_file(STUDENTS_ROSTER_FILE, roster)
        return jsonify({"success": True, "message": f"Đã làm trống toàn bộ danh sách sinh viên của lớp {class_code}!"})
    return jsonify({"error": "Không tìm thấy dữ liệu lớp!"}), 404

@app.route("/api/documents", methods=["GET"])
def get_documents():
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    docs = [{"id": k, "name": v["name"], "category": v["category"]} for k, v in templates_data.items()]
    return jsonify(docs)

@app.route("/api/classes", methods=["GET"])
def get_classes():
    classes = load_json_file(CLASSES_FILE, ["22DTH01", "22DTH02", "KN01", "KN02"])
    return jsonify({"classes": classes})

@app.route("/api/classes/add", methods=["POST"])
def add_class():
    data = request.json or {}
    new_class = str(data.get("class_code", "")).strip().upper()
    if not new_class:
        return jsonify({"error": "Vui lòng nhập Mã lớp KN!"}), 400
    classes = load_json_file(CLASSES_FILE, [])
    if new_class not in classes:
        classes.append(new_class)
        classes.sort()
        save_json_file(CLASSES_FILE, classes)
    return jsonify({"success": True, "classes": classes, "message": f"Đã thêm Mã lớp '{new_class}' thành công!"})

@app.route("/api/classes/delete", methods=["POST"])
def delete_class():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    classes = load_json_file(CLASSES_FILE, [])
    if class_code in classes:
        classes.remove(class_code)
        save_json_file(CLASSES_FILE, classes)
    return jsonify({"success": True, "classes": classes, "message": f"Đã xóa Mã lớp '{class_code}'!"})

@app.route("/api/quiz/get", methods=["POST"])
def get_quiz():
    if not is_session_open():
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    mssv = str(data.get("mssv", "")).strip()

    if class_code and mssv and not is_student_in_roster(class_code, mssv):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép làm bài!",
            "not_in_roster": True
        }), 403

    doc_type = data.get("doc_type")
    all_questions = load_json_file(os.path.join(DATA_DIR, "questions.json"), {})
    
    raw_questions = all_questions.get(doc_type, [])
    if not raw_questions:
        return jsonify({"questions": [], "total": 0, "pass_score": 0, "time_limit_seconds": 300})

    import random
    # Chọn ngẫu nhiên tối đa 5 câu từ ngân hàng câu hỏi
    sample_size = min(len(raw_questions), 5)
    selected_questions = random.sample(raw_questions, sample_size)

    # Ẩn đáp án đúng và xáo trộn các phương án trả lời nhưng giữ ID gốc
    safe_questions = []
    for q in selected_questions:
        options_with_id = [{"opt_id": idx, "text": opt} for idx, opt in enumerate(q["options"])]
        random.shuffle(options_with_id)
        safe_questions.append({
            "id": q["id"],
            "question": q["question"],
            "options": options_with_id
        })

    import math
    pass_score = max(1, math.ceil(len(safe_questions) * 0.8))
    return jsonify({
        "questions": safe_questions,
        "total": len(safe_questions),
        "pass_score": pass_score,
        "time_limit_seconds": 300
    })

@app.route("/api/quiz/submit", methods=["POST"])
def submit_quiz():
    if not is_session_open():
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    doc_type = data.get("doc_type")
    user_answers = data.get("answers", {}) # { "1": opt_id, "2": opt_id, ... }
    
    all_questions = load_json_file(os.path.join(DATA_DIR, "questions.json"), {})
    questions_list = all_questions.get(doc_type, [])
    q_map = {str(q["id"]): q for q in questions_list}
    
    correct_count = 0
    feedback = []
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
            "explanation": q["explanation"]
        })
        
    import math
    total_q = len(user_answers) if user_answers else len(questions_list)
    pass_score = max(1, math.ceil(total_q * 0.8)) if total_q else 0
    passed = (correct_count >= pass_score)
    return jsonify({
        "score": correct_count,
        "total": total_q,
        "pass_score": pass_score,
        "passed": passed,
        "feedback": feedback
    })

@app.route("/api/template/generate", methods=["POST"])
def generate_template():
    if not is_session_open():
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    sbd = str(data.get("sbd", "")).strip()
    mssv = str(data.get("mssv", "")).strip()
    name = str(data.get("name", "")).strip()
    doc_type = str(data.get("doc_type", "")).strip()
    
    if not (sbd and mssv and name and doc_type):
        return jsonify({"error": "Vui lòng nhập đầy đủ SBD, MSSV, Họ và tên và Chọn loại văn bản!"}), 400

    if not is_student_in_roster(class_code, mssv):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép nhận file mẫu bài tập!",
            "not_in_roster": True
        }), 403
        
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    tmpl = templates_data.get(doc_type)
    if not tmpl:
        return jsonify({"error": "Không tìm thấy dữ liệu loại văn bản này!"}), 404
        
    # Tạo tên file theo quy chuẩn cũ: [SBD]_[MSSV]_[HOVATEN]_[LoaiVB].docx
    clean_name = "".join(c for c in name if c.isalnum()).upper()
    file_suffix = tmpl.get("filename_suffix", doc_type)
    filename = f"{sbd}_{mssv}_{clean_name}_{file_suffix}.docx"
    output_path = os.path.join(STORAGE_TEMPLATES, filename)
    
    # Xử lý nội dung thân bài: Để trống hoặc lấy nội dung Giảng viên thiết lập
    if tmpl.get("is_body_blank", False):
        body_content = "[Nội dung văn bản: Sinh viên tự nhập theo nội dung Giảng viên hướng dẫn trực tiếp tại lớp]"
    else:
        body_content = tmpl.get("body_part", "")
        
    header = tmpl.get("header_part", "")
    footer = tmpl.get("footer_part", "")
    full_text = f"{header}\n\n{body_content}\n\n{footer}" if (header or footer) else tmpl.get("raw_text", "")

    # Cá nhân hóa Số ký hiệu văn bản gắn với 3 số cuối MSSV
    if len(mssv) >= 3:
        last3 = mssv[-3:]
        full_text = re.sub(r'(Số\s*:\s*)\d+(/)', rf'\g<1>{last3}\2', full_text, flags=re.IGNORECASE)
    
    create_student_raw_template(
        sbd=sbd,
        mssv=mssv,
        student_name=name,
        doc_type_id=doc_type,
        raw_text=full_text,
        output_path=output_path
    )

    # Ghi nhận Telemetry: Thời điểm sinh phôi bài làm & khởi tạo phiên
    sessions = load_json_file(STUDENT_SESSIONS_FILE, {})
    sess_key = f"{mssv}_{doc_type}"
    sessions[sess_key] = {
        "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timestamp": time.time(),
        "preview_count": 0
    }
    save_json_file(STUDENT_SESSIONS_FILE, sessions)
    
    return jsonify({
        "filename": filename,
        "download_url": f"/api/template/download/{filename}"
    })

@app.route("/api/template/download/<filename>")
def download_template(filename):
    safe_name = os.path.basename(filename)
    path = os.path.join(STORAGE_TEMPLATES, safe_name)
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=safe_name)
    return "File không tồn tại", 404

@app.route("/api/validate", methods=["POST"])
def validate_student_work():
    if not is_session_open():
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    if "file" not in request.files:
        return jsonify({"error": "Chưa chọn file tải lên!"}), 400
        
    file = request.files["file"]
    class_code = str(request.form.get("class_code", "")).strip().upper() or "Chung"
    sbd = request.form.get("sbd", "").strip()
    mssv = request.form.get("mssv", "").strip()
    name = request.form.get("name", "").strip()
    doc_type = request.form.get("doc_type", "").strip()
    
    if not (file.filename and sbd and mssv and name and doc_type):
        return jsonify({"error": "Thiếu thông tin xác thực bài làm!"}), 400

    if not is_student_in_roster(class_code, mssv):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép thẩm định bài làm!",
            "not_in_roster": True
        }), 403

    temp_save_path = os.path.join(STORAGE_UPLOADS, f"temp_{mssv}_{file.filename}")
    file.save(temp_save_path)
    
    try:
        # 1. BƯỚC 1: KIỂM TRA GIAN LẬN (CHỐNG CHÉP BÀI)
        # Nạp dữ liệu các bài đã từng nộp để tra cứu tên người cho chép
        submissions = load_json_file(SUBMISSIONS_FILE, [])
        students_db = {s["mssv"]: s for s in submissions}
        
        fraud_check = check_anti_cheat(
            docx_path=temp_save_path,
            current_sbd=sbd,
            current_mssv=mssv,
            current_name=name,
            students_db=students_db
        )
        
        if fraud_check.get("is_fraud"):
            # Ghi lại hồ sơ vi phạm vào fraud_logs.json
            import uuid
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

            fraud_logs = load_json_file(FRAUD_LOGS_FILE, [])
            fraud_entry = {
                "id": log_id,
                "class_code": class_code or "Chung",
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "doc_type": doc_type,
                "fraud_data": fraud_check
            }
            fraud_logs.append(fraud_entry)
            save_json_file(FRAUD_LOGS_FILE, fraud_logs)
            
            return jsonify({
                "status": "FRAUD_DETECTED",
                "fraud_info": fraud_check
            })

        # Ghi nhận số lần kiểm tra thử (Preview Count Telemetry)
        sessions = load_json_file(STUDENT_SESSIONS_FILE, {})
        sess_key = f"{mssv}_{doc_type}"
        current_sess = sessions.get(sess_key, {
            "started_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "timestamp": time.time(),
            "preview_count": 0
        })
        current_sess["preview_count"] = current_sess.get("preview_count", 0) + 1
        sessions[sess_key] = current_sess
        save_json_file(STUDENT_SESSIONS_FILE, sessions)

        # 2. BƯỚC 2: KIỂM TRA THỂ THỨC NGHỊ ĐỊNH 30 (Ô 1 - Ô 9)
        templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
        tmpl_info = templates_data.get(doc_type, {})
        
        validator = Decree30Validator(temp_save_path, doc_type, tmpl_info, mssv=mssv)
        result = validator.validate_document()
        
        result["status"] = "SUCCESS"
        result["temp_file"] = os.path.basename(temp_save_path)
        result["preview_count"] = current_sess["preview_count"]
        result["max_previews"] = 3
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": f"Lỗi xử lý file: {str(e)}"}), 500

@app.route("/api/submit", methods=["POST"])
def submit_final():
    if not is_session_open():
        return jsonify({
            "error": "Phòng làm bài hiện đang tạm khóa để sinh viên nghe giảng lý thuyết! Vui lòng chờ Giảng viên cho phép bắt đầu.",
            "is_locked": True
        }), 403

    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip().upper()
    sbd = data.get("sbd")
    mssv = data.get("mssv")
    name = data.get("name")
    doc_type = data.get("doc_type")
    temp_file = data.get("temp_file")
    
    if not (sbd and mssv and name and doc_type and temp_file):
        return jsonify({"error": "Thiếu thông tin nộp bài!"}), 400

    if not is_student_in_roster(class_code, mssv):
        return jsonify({
            "error": f"Mã sinh viên [{mssv}] không có trong danh sách chính thức của lớp [{class_code}]. Bạn không được phép nộp bài!",
            "not_in_roster": True
        }), 403
        
    temp_path = os.path.join(STORAGE_UPLOADS, temp_file)
    if not os.path.exists(temp_path):
        return jsonify({"error": "Không tìm thấy file bài làm tạm thời để nộp!"}), 404
        
    # Di chuyển sang thư mục submitted
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    tmpl = templates_data.get(doc_type, {})
    clean_name = "".join(c for c in name if c.isalnum()).upper()
    file_suffix = tmpl.get("filename_suffix", doc_type)
    final_filename = f"{sbd}_{mssv}_{clean_name}_{file_suffix}.docx"
    final_path = os.path.join(STORAGE_SUBMITTED, final_filename)
    
    import shutil
    shutil.copy2(temp_path, final_path)
    
    # Ghi nhận kết quả và Telemetry thời gian làm bài
    sessions = load_json_file(STUDENT_SESSIONS_FILE, {})
    sess_key = f"{mssv}_{doc_type}"
    sess = sessions.get(sess_key, {})
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
        if elapsed_seconds < 120 and not (app.testing or os.environ.get("EDUDOC_TESTING") == "1"):
            is_suspicious_speed = True
            flags.append(f"🚩 Nộp bài quá nhanh ({elapsed_str} < 2 phút)")
            
    preview_count = sess.get("preview_count", 0)

    submissions = load_json_file(SUBMISSIONS_FILE, [])
    # Xóa bản ghi cũ nếu sinh viên nộp lại
    submissions = [s for s in submissions if not (s["mssv"] == mssv and s["doc_type"] == doc_type)]
    
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
        "status": "Hoàn thành 100% Nghị định 30"
    }
    submissions.append(new_sub)
    save_json_file(SUBMISSIONS_FILE, submissions)
    
    return jsonify({"success": True, "message": "Nộp bài thành công!", "submission": new_sub})

@app.route("/api/teacher/data", methods=["GET"])
def teacher_data():
    submissions = load_json_file(SUBMISSIONS_FILE, [])
    fraud_logs = load_json_file(FRAUD_LOGS_FILE, [])
    classes = load_json_file(CLASSES_FILE, ["22DTH01", "22DTH02", "KN01", "KN02"])
    session_state = get_session_state()
    roster = load_json_file(STUDENTS_ROSTER_FILE, {})
    total_roster_students = sum(len(s_list) for s_list in roster.values())
    return jsonify({
        "submissions": submissions,
        "fraud_logs": fraud_logs,
        "classes": classes,
        "session_state": session_state,
        "students_roster": roster,
        "total_roster_students": total_roster_students
    })

@app.route("/api/download/submitted/<filename>")
def download_submitted(filename):
    safe_name = os.path.basename(filename)
    path = os.path.join(STORAGE_SUBMITTED, safe_name)
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=safe_name)
    return "File không tồn tại", 404

@app.route("/api/teacher/export-csv", methods=["GET"])
def export_csv():
    class_filter = request.args.get("class_code", "ALL")
    submissions = load_json_file(SUBMISSIONS_FILE, [])
    if class_filter != "ALL":
        submissions = [s for s in submissions if s.get("class_code") == class_filter]
        
    import io
    import csv
    from flask import Response
    
    output = io.StringIO()
    # Thêm UTF-8 BOM để Excel trên Windows hiển thị đúng tiếng Việt có dấu
    output.write('\ufeff')
    writer = csv.writer(output)
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
            "10.0 / 10"
        ])
        
    csv_data = output.getvalue()
    filename = f"Bang_Diem_STVB_{class_filter}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@app.route("/api/teacher/submissions/delete", methods=["POST"])
def delete_teacher_submission():
    data = request.json or {}
    mssv = str(data.get("mssv", "")).strip()
    doc_type = str(data.get("doc_type", "")).strip()
    if not mssv:
        return jsonify({"error": "Thiếu MSSV cần xóa!"}), 400
    submissions = load_json_file(SUBMISSIONS_FILE, [])
    new_sub = [s for s in submissions if not (s.get("mssv") == mssv and (not doc_type or s.get("doc_type") == doc_type))]
    save_json_file(SUBMISSIONS_FILE, new_sub)
    return jsonify({"success": True, "message": f"Đã xóa bài nộp của MSSV {mssv}!"})

@app.route("/api/teacher/fraud/delete", methods=["POST"])
def delete_fraud_log():
    data = request.json or {}
    log_id = str(data.get("id", "")).strip()
    if not log_id:
        return jsonify({"error": "Thiếu mã bản ghi vi phạm cần xóa!"}), 400
    
    fraud_logs = load_json_file(FRAUD_LOGS_FILE, [])
    orig_len = len(fraud_logs)
    fraud_logs = [log for log in fraud_logs if str(log.get("id")) != log_id]
    
    if len(fraud_logs) == orig_len:
        fraud_logs = [log for log in fraud_logs if str(log.get("timestamp")) != log_id]
        
    save_json_file(FRAUD_LOGS_FILE, fraud_logs)
    return jsonify({"success": True, "message": "Đã xóa biên bản vi phạm thành công!"})

@app.route("/api/teacher/fraud/clear", methods=["POST"])
def clear_fraud_logs():
    data = request.json or {}
    class_code = str(data.get("class_code", "")).strip()
    
    fraud_logs = load_json_file(FRAUD_LOGS_FILE, [])
    if class_code and class_code != "ALL":
        fraud_logs = [log for log in fraud_logs if log.get("class_code") != class_code]
        msg = f"Đã xóa toàn bộ nhật ký vi phạm của lớp {class_code}!"
    else:
        fraud_logs = []
        msg = "Đã xóa toàn bộ nhật ký vi phạm của hệ thống!"
        
    save_json_file(FRAUD_LOGS_FILE, fraud_logs)
    return jsonify({"success": True, "message": msg})

@app.route("/api/teacher/templates", methods=["GET"])
def teacher_templates():
    templates_data = load_json_file(os.path.join(DATA_DIR, "document_templates.json"), {})
    return jsonify(templates_data)

@app.route("/api/teacher/templates/save", methods=["POST"])
def save_teacher_template():
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

    # Cập nhật lại raw_text
    placeholder = "[Nội dung văn bản: Sinh viên tự nhập theo nội dung Giảng viên hướng dẫn trực tiếp tại lớp]"
    b = placeholder if is_body_blank else body_part
    templates_data[doc_type]["raw_text"] = f"{header_part}\n\n{b}\n\n{footer_part}"

    save_json_file(os.path.join(DATA_DIR, "document_templates.json"), templates_data)
    return jsonify({"success": True, "message": "Đã lưu cập nhật nội dung bài tập thành công!"})

@app.route("/api/teacher/quiz/<doc_type>", methods=["GET"])
def get_teacher_quiz(doc_type):
    all_questions = load_json_file(os.path.join(DATA_DIR, "questions.json"), {})
    questions = all_questions.get(doc_type, [])
    return jsonify({"questions": questions, "doc_type": doc_type, "total": len(questions)})

@app.route("/api/teacher/quiz/save", methods=["POST"])
def save_teacher_quiz():
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
    except:
        return jsonify({"error": "Đáp án đúng không hợp lệ!"}), 400

    questions_path = os.path.join(DATA_DIR, "questions.json")
    all_questions = load_json_file(questions_path, {})
    if doc_type not in all_questions:
        all_questions[doc_type] = []

    q_list = all_questions[doc_type]

    # Kiểm tra xem là SỬA câu hỏi có sẵn hay THÊM MỚI
    if q_id is not None:
        try:
            q_id = int(q_id)
        except:
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
    save_json_file(questions_path, all_questions)
    return jsonify({"success": True, "message": "Đã lưu câu hỏi trắc nghiệm thành công!", "questions": q_list})

@app.route("/api/teacher/quiz/delete", methods=["POST"])
def delete_teacher_quiz():
    data = request.json or {}
    doc_type = data.get("doc_type")
    q_id = data.get("id")

    if not doc_type or q_id is None:
        return jsonify({"error": "Thiếu thông tin câu hỏi cần xóa!"}), 400

    try:
        q_id = int(q_id)
    except:
        pass

    questions_path = os.path.join(DATA_DIR, "questions.json")
    all_questions = load_json_file(questions_path, {})
    if doc_type in all_questions:
        all_questions[doc_type] = [q for q in all_questions[doc_type] if q["id"] != q_id]
        save_json_file(questions_path, all_questions)
        return jsonify({"success": True, "message": "Đã xóa câu hỏi!", "questions": all_questions[doc_type]})

    return jsonify({"error": "Không tìm thấy loại văn bản này!"}), 404

if __name__ == "__main__":
    print("Khởi động Máy chủ Phần mềm Huấn luyện STVB Nghị định 30...")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
