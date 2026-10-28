# -*- coding: utf-8 -*-
"""
HỆ THỐNG HUẤN LUYỆN & KHẢO THÍ THỂ THỨC VĂN BẢN HÀNH CHÍNH (EDUDOC-STVB)
Tuân thủ Nghị định 30/2020/NĐ-CP của Chính phủ.

Kiến trúc Hệ thống:
- Backend: Flask Modular với Flask Blueprints (routes/student.py, routes/teacher.py).
- Cơ sở dữ liệu: SQLite với cơ chế khóa WAL (Write-Ahead Logging) xử lý hàng trăm truy vấn đồng thời.
- Bảo mật: Thủy vân số ẩn, phát hiện đạo văn/gian lận, kiểm soát danh sách lớp (Roster).
- Tương thích Production: Hỗ trợ triển khai Render / Linux VPS với Python 3.11/3.12 LTS.
"""
import os
import sys
from flask import Flask

from engine.common import (
    BASE_DIR, DATA_DIR, STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    SUBMISSIONS_FILE, FRAUD_LOGS_FILE, CLASSES_FILE, SESSION_STATE_FILE,
    STUDENT_SESSIONS_FILE, STUDENTS_ROSTER_FILE, QUESTIONS_FILE,
    load_json_file, save_json_file, get_session_state, is_session_open,
    is_student_in_roster, get_student_from_roster, parse_students_text,
    cleanup_old_uploads
)
from engine.db import init_db
from routes.student import student_bp
from routes.teacher import teacher_bp

def create_app():
    """Khởi tạo ứng dụng Flask với các Blueprints độc lập"""
    application = Flask(__name__, template_folder="templates", static_folder="static")
    
    # Khởi tạo cơ sở dữ liệu SQLite WAL
    init_db()
    
    # Đăng ký Blueprints cho Sinh viên và Giảng viên
    application.register_blueprint(student_bp)
    application.register_blueprint(teacher_bp)
    
    # Dọn dẹp tệp rác cũ trong storage/uploads khi khởi động
    cleanup_old_uploads(max_age_seconds=3600)
    
    return application

app = create_app()

if __name__ == "__main__":
    print("=" * 70)
    print("  EDUDOC - HỆ THỐNG HUẤN LUYỆN & CHẤM BÀI STVB NGHỊ ĐỊNH 30")
    print("  Tầng dữ liệu: SQLite (Chế độ WAL Write-Ahead Logging)")
    print("  Cổng làm bài Sinh viên: http://127.0.0.1:5000/")
    print("  Bàn làm việc Giảng viên: http://127.0.0.1:5000/teacher")
    print("=" * 70)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
