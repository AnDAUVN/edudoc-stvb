import os
import sys
import webbrowser
import threading
import time

def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:5000"
    print(f"\n[OK] Đang tự động mở trình duyệt tại: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    threading.Thread(target=open_browser, daemon=True).start()
    
    from app import app
    print("=" * 70)
    print("    HỆ THỐNG EDUDOC - KHẢO THÍ & HUẤN LUYỆN STVB NGHỊ ĐỊNH 30")
    print("    Máy chủ đang chạy tại: http://127.0.0.1:5000")
    print("    Nhấn Ctrl + C để dừng máy chủ.")
    print("=" * 70)
    app.run(host="127.0.0.1", port=5000, debug=False)
