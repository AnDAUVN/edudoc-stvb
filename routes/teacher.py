import os
import json
import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, render_template, current_app
from engine.db import get_db_connection

teacher_bp = Blueprint('teacher_bp', __name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
QUESTIONS_FILE = DATA_DIR / "questions.json"
SESSION_STATE_FILE = DATA_DIR / "session_state.json"

# 1. Route hiển thị Dashboard Giảng viên chuẩn xác
@teacher_bp.route('/teacher')
def teacher_dashboard():
    return render_template('teacher.html')

# 2. Xử lý Trạng thái ca thi: Đọc và đồng bộ cả JSON lẫn SQLite
def get_session_state(class_code="ALL"):
    state = {"is_open": False, "enforce_roster": True, "updated_at": ""}
    if SESSION_STATE_FILE.exists():
        try:
            data = json.loads(SESSION_STATE_FILE.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                state.update(data)
        except Exception:
            pass
    return state

def save_session_state(state, class_code="ALL"):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SESSION_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')

@teacher_bp.route("/api/teacher/session-toggle", methods=["POST"])
@teacher_bp.route("/api/toggle-exam-status", methods=["POST"])
def toggle_session():
    data = request.get_json(silent=True) or {}
    state = get_session_state()
    
    # Đảo trạng thái hoặc gán theo yêu cầu
    if "is_open" in data:
        new_status = bool(data["is_open"])
    elif "status" in data:
        new_status = (data["status"] == "open")
    else:
        new_status = not state.get("is_open", False)

    state["is_open"] = new_status
    state["updated_at"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Lưu xuống file JSON
    save_session_state(state)

    # Đồng bộ xuống SQLite để phục vụ sinh viên
    try:
        conn = get_db_connection()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS exam_settings (
                    id INTEGER PRIMARY KEY,
                    is_open INTEGER DEFAULT 0,
                    updated_at TEXT
                )
            """)
            conn.execute("INSERT OR IGNORE INTO exam_settings (id, is_open) VALUES (1, 0)")
            conn.execute("UPDATE exam_settings SET is_open = ?, updated_at = ? WHERE id = 1", 
                         (1 if new_status else 0, state["updated_at"]))
        conn.close()
    except Exception as e:
        print(f"[LỖI ĐỒNG BỘ CA THI]: {e}")

    return jsonify({"status": "success", "is_open": new_status})

# 3. Nạp ngân hàng câu hỏi trắc nghiệm (Đảm bảo đọc đúng file 43KB)
@teacher_bp.route("/api/teacher/questions", methods=["GET"])
@teacher_bp.route("/api/quiz-questions", methods=["GET"])
def get_quiz_questions():
    try:
        topic = request.args.get('topic', '').strip()
        if not QUESTIONS_FILE.exists():
            return jsonify({"status": "success", "data": []})
        
        raw_data = json.loads(QUESTIONS_FILE.read_text(encoding='utf-8'))
        
        # Xử lý tương thích định dạng dữ liệu trong file JSON
        if isinstance(raw_data, dict):
            if topic and topic in raw_data:
                res_data = raw_data[topic]
            else:
                # Gộp tất cả nếu không lọc chủ đề
                res_data = []
                for q_list in raw_data.values():
                    if isinstance(q_list, list):
                        res_data.extend(q_list)
        elif isinstance(raw_data, list):
            res_data = raw_data
        else:
            res_data = []

        return jsonify({"status": "success", "data": res_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 4. API Lấy danh sách đổi thiết bị CN18 (Đã nới lỏng để không bị sót)
@teacher_bp.route('/api/device-change-requests', methods=['GET'])
def get_device_change_requests():
    conn = get_db_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS device_change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                student_name TEXT,
                new_device_id TEXT,
                reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        requests = conn.execute("""
            SELECT id, student_id, student_name, new_device_id, reason, created_at
            FROM device_change_requests
            WHERE status = 'pending'
            ORDER BY id DESC
        """).fetchall()
        return jsonify({"status": "success", "data": [dict(r) for r in requests]})
    finally:
        conn.close()