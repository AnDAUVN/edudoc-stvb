# -*- coding: utf-8 -*-
import os
import sys
import json
import socket
import webbrowser
import threading
import subprocess
import re
import time

tunnel_proc = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def run_cloudflared_tunnel(base_dir, local_ip):
    global tunnel_proc
    cloudflared_bin = os.path.join(base_dir, "tools", "cloudflared.exe")
    if not os.path.exists(cloudflared_bin):
        return

    tunnel_info_path = os.path.join(base_dir, "data", "tunnel_info.json")
    try:
        if os.path.exists(tunnel_info_path):
            os.remove(tunnel_info_path)

        cmd = [cloudflared_bin, "tunnel", "--url", "http://127.0.0.1:5000"]
        tunnel_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )

        public_url = None
        start_time = time.time()
        while time.time() - start_time < 20 and tunnel_proc.poll() is None:
            line = tunnel_proc.stderr.readline()
            if line:
                m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if m:
                    public_url = m.group(0)
                    break

        if public_url:
            with open(tunnel_info_path, "w", encoding="utf-8") as f:
                json.dump({
                    "public_url": public_url,
                    "student_public_url": f"{public_url}/thi",
                    "local_ip": local_ip,
                    "student_local_url": f"http://{local_ip}:5000/thi",
                    "created_at": time.time()
                }, f, ensure_ascii=False, indent=2)

            print("\n" + "=" * 75)
            print("  🚀 [INTERNET LINK] ĐÃ TẠO ĐƯỜNG LINK ONLINE CHO SINH VIÊN:")
            print(f"     👉 Link gửi Sinh viên (4G / Wi-Fi / Mọi nơi): {public_url}/thi")
            print(f"     👉 Link Giảng viên quản lý từ xa:            {public_url}/gv")
            print("=" * 75 + "\n")
    except Exception as e:
        print(f"[!] Lỗi khởi động Cloudflare Tunnel: {e}")

def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:5000"
    print(f"\n[OK] Đang tự động mở trình duyệt tại: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    local_ip = get_local_ip()

    # Khởi động Tunnel tạo link Internet cho sinh viên
    threading.Thread(target=run_cloudflared_tunnel, args=(base_dir, local_ip), daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()

    from app import app
    print("=" * 75)
    print("    HỆ THỐNG EDUDOC - KHẢO THÍ & HUẤN LUYỆN STVB NGHỊ ĐỊNH 30")
    print("    Máy chủ đang chạy tại: http://127.0.0.1:5000")
    print(f"    Mạng nội bộ (Wi-Fi/LAN): http://{local_ip}:5000/thi")
    print("    Nhấn Ctrl + C để dừng máy chủ.")
    print("=" * 75)

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        if tunnel_proc:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass
