# -*- coding: utf-8 -*-
"""
KỊCH BẢN KHỞI CHẠY HỆ THỐNG EDUDOC - KHẢO THÍ & HUẤN LUYỆN NGHỊ ĐỊNH 30
Tự động dọn dẹp tiến trình treo, mở cổng 5000, thiết lập Cloudflare Tunnel bảo mật,
và tự động mở Bàn làm việc Giảng viên (/gv) trên máy chủ.
"""
import os
import sys
import json
import socket
import webbrowser
import threading
import subprocess
import re
import time
import atexit

tunnel_proc = None

def get_local_ip():
    """Lấy địa chỉ IP nội bộ trong mạng LAN/Wi-Fi"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def cleanup_stale_processes(port=5000):
    """Dọn dẹp các tiến trình cũ bị treo trên cổng 5000 và cloudflared cũ (Tương thích Windows / macOS / Linux)"""
    if sys.platform != "win32":
        try:
            subprocess.run(["pkill", "-f", "cloudflared"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out = subprocess.check_output(f"lsof -ti:{port}", shell=True, text=True, errors="ignore")
            for pid_str in out.strip().split():
                if pid_str and int(pid_str) != os.getpid():
                    subprocess.run(["kill", "-9", pid_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return

    # 1. Dọn cloudflared mồ côi trên Windows
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "cloudflared.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception:
        pass

    # 2. Giải phóng cổng 5000 nếu có tiến trình khác đang chiếm giữ
    try:
        out = subprocess.check_output("netstat -ano", shell=True, text=True, errors="ignore")
        my_pid = os.getpid()
        for line in out.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
                try:
                    pid = int(parts[4])
                    if pid != my_pid:
                        subprocess.run(
                            ["taskkill", "/F", "/PID", str(pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                except Exception:
                    pass
    except Exception:
        pass

def run_cloudflared_tunnel(base_dir, local_ip):
    """Khởi động Cloudflare Tunnel với tệp nhật ký trực tiếp (tránh deadlock pipe, tương thích Windows/macOS)"""
    global tunnel_proc
    import shutil
    if sys.platform == "win32":
        cloudflared_bin = os.path.join(base_dir, "tools", "cloudflared.exe")
        if not os.path.exists(cloudflared_bin):
            return
    else:
        cloudflared_bin = shutil.which("cloudflared")
        if not cloudflared_bin:
            local_bin = os.path.join(base_dir, "tools", "cloudflared")
            if os.path.exists(local_bin):
                cloudflared_bin = local_bin
            else:
                return

    tunnel_info_path = os.path.join(base_dir, "data", "tunnel_info.json")
    tunnel_log_path = os.path.join(base_dir, "data", "cloudflared.log")

    try:
        if os.path.exists(tunnel_info_path):
            try:
                os.remove(tunnel_info_path)
            except Exception:
                pass
        if os.path.exists(tunnel_log_path):
            try:
                os.remove(tunnel_log_path)
            except Exception:
                pass

        cmd = [
            cloudflared_bin,
            "tunnel",
            "--no-autoupdate",
            "--logfile", tunnel_log_path,
            "--url", "http://127.0.0.1:5000"
        ]

        # Khởi chạy không sử dụng PIPE để tuyệt đối không bị tràn bộ đệm Windows WriteFile
        tunnel_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        public_url = None
        start_time = time.time()
        # Đọc từ file log để lấy URL Cloudflare
        while time.time() - start_time < 25 and tunnel_proc.poll() is None:
            time.sleep(0.8)
            if os.path.exists(tunnel_log_path):
                try:
                    with open(tunnel_log_path, "r", encoding="utf-8", errors="ignore") as f:
                        log_data = f.read()
                    m = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', log_data)
                    if m:
                        public_url = m.group(0)
                        break
                except Exception:
                    pass

        if public_url:
            with open(tunnel_info_path, "w", encoding="utf-8") as f:
                json.dump({
                    "public_url": public_url,
                    "student_public_url": f"{public_url}/thi",
                    "local_ip": local_ip,
                    "student_local_url": f"http://{local_ip}:5000/thi",
                    "created_at": time.time()
                }, f, ensure_ascii=False, indent=2)

            print("\n" + "=" * 78)
            print("  🚀 [KẾT NỐI TOÀN CẦU THÀNH CÔNG] ĐƯỜNG LINK ONLINE CHO SINH VIÊN:")
            print(f"     👉 Link gửi Sinh viên (4G / Wi-Fi / Mọi thiết bị): {public_url}/thi")
            print(f"     👉 Bàn làm việc Giảng viên (Mở trên máy này):      http://127.0.0.1:5000/gv")
            print(f"     👉 Link mạng nội bộ phòng máy (Dự phòng):          http://{local_ip}:5000/thi")
            print("=" * 78 + "\n")
    except Exception as e:
        print(f"[!] Lỗi khởi động Cloudflare Tunnel: {e}")

def open_browser():
    """Tự động mở trình duyệt vào Bàn làm việc Giảng viên trên localhost"""
    time.sleep(2.0)
    url = "http://127.0.0.1:5000/gv"
    print(f"\n[OK] Đang tự động mở Bàn làm việc Giảng viên: {url}")
    webbrowser.open(url)

def shutdown_tunnel():
    global tunnel_proc
    if tunnel_proc:
        try:
            tunnel_proc.terminate()
            tunnel_proc.wait(timeout=2)
        except Exception:
            pass

atexit.register(shutdown_tunnel)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # 1. Dọn dẹp tiến trình cũ giải phóng cổng 5000
    cleanup_stale_processes(5000)

    local_ip = get_local_ip()

    # 2. Khởi động Cloudflare Tunnel tạo link Internet cho sinh viên
    threading.Thread(target=run_cloudflared_tunnel, args=(base_dir, local_ip), daemon=True).start()
    threading.Thread(target=open_browser, daemon=True).start()

    from app import app
    print("=" * 78)
    print("    HỆ THỐNG EDUDOC - KHẢO THÍ & HUẤN LUYỆN STVB NGHỊ ĐỊNH 30/2020/NĐ-CP")
    print("    Bàn làm việc Giảng viên: http://127.0.0.1:5000/gv")
    print(f"    Mạng nội bộ phòng máy (LAN): http://{local_ip}:5000/thi")
    print("    Nhấn Ctrl + C để dừng máy chủ.")
    print("=" * 78)

    try:
        app.run(host="0.0.0.0", port=5000, debug=False)
    finally:
        shutdown_tunnel()
