import os
import sys
from pathlib import Path
from flask import Flask, request, jsonify, render_template

# 1. Ép buộc đường dẫn làm việc luôn là thư mục chứa app.py
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

# 2. Khởi tạo ứng dụng Flask
app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'edudoc_stvb_secret_key_fixed_2026')

# 3. Giới hạn dung lượng tải lên tối đa 5MB (chống treo RAM máy chủ)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "status": "error",
        "message": "Tệp quá lớn! Vui lòng nộp tệp văn bản dưới 5MB."
    }), 413

# 4. Nạp các Route modules
try:
    from routes.student import student_bp
    app.register_blueprint(student_bp)
except Exception as e:
    print(f"[CẢNH BÁO] Lỗi nạp student_bp: {e}")

try:
    from routes.teacher import teacher_bp
    app.register_blueprint(teacher_bp)
except Exception as e:
    print(f"[CẢNH BÁO] Lỗi nạp teacher_bp: {e}")

# 5. Route điều hướng trang chủ
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/teacher')
def teacher_page():
    return render_template('teacher.html')

# 6. Khởi động máy chủ sản xuất Waitress đa luồng
if __name__ == '__main__':
    print("=" * 60)
    print(" HỆ THỐNG HUẤN LUYỆN & KIỂM ĐỊNH VĂN BẢN (EDUDOC-STVB)")
    print("=" * 60)
    
    try:
        from waitress import serve
        print("[THÀNH CÔNG] Máy chủ Waitress đang chạy tại: http://127.0.0.1:5000")
        print("[INFO] Cổng Giảng viên: http://127.0.0.1:5000/teacher")
        print("[INFO] Đang chạy với 8 luồng xử lý đồng thời.")
        serve(app, host='0.0.0.0', port=5000, threads=8)
    except ImportError:
        print("[CẢNH BÁO] Chưa cài waitress, chạy chế độ Flask mặc định...")
        app.run(host='0.0.0.0', port=5000, debug=False)