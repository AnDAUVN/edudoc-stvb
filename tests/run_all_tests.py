# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import socket

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)

TEST_SUITES = [
    "test_system.py",
    "test_user_case.py",
    "test_perfect_doc.py",
    "test_cascade.py",
    "test_kinh_phi.py",
    "test_blank_and_custom.py",
    "test_fraud_management.py",
    "test_cong_ty_pho_giam_doc.py",
    "test_all_8_docs.py",
    "comprehensive_audit_suite.py"
]

def is_server_running(host="127.0.0.1", port=5000):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            return s.connect_ex((host, port)) == 0
    except:
        return False

def main():
    print("=" * 70)
    print("       CHẠY TOÀN BỘ BỘ KIỂM THỬ TỰ ĐỘNG - EDUDOC STVB")
    print(f"       Thư mục gốc: {ROOT_DIR}")
    print("=" * 70)

    server_process = None
    if not is_server_running():
        print(" [i] Máy chủ 127.0.0.1:5000 chưa chạy. Đang tự động khởi động máy chủ thử nghiệm...")
        server_process = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            time.sleep(0.5)
            if is_server_running():
                print(" [+] Máy chủ thử nghiệm đã sẵn sàng tại http://127.0.0.1:5000!")
                break
        else:
            print(" [!] Cảnh báo: Không thể kết nối tới máy chủ sau 10s.")

    total = len(TEST_SUITES)
    passed = 0
    failed = 0
    start_time = time.time()

    try:
        for idx, test_file in enumerate(TEST_SUITES, 1):
            test_path = os.path.join(ROOT_DIR, "tests", test_file)
            if not os.path.exists(test_path):
                print(f"[{idx:02d}/{total:02d}] ⚠ KHÔNG TÌM THẤY: {test_file}")
                failed += 1
                continue

            env = os.environ.copy()
            env["PYTHONPATH"] = ROOT_DIR
            res = subprocess.run([sys.executable, test_path], capture_output=True, text=True, encoding="utf-8", cwd=ROOT_DIR, env=env)
            if res.returncode == 0:
                print(f"[{idx:02d}/{total:02d}] PASS ✔ -> {test_file}")
                passed += 1
            else:
                print(f"[{idx:02d}/{total:02d}] FAIL ✖ -> {test_file}")
                print("  --- Chi tiết lỗi ---")
                lines = res.stderr.strip().splitlines()[-5:] if res.stderr else res.stdout.strip().splitlines()[-5:]
                for l in lines:
                    print("   ", l)
                failed += 1
    finally:
        if server_process:
            print(" [i] Đang tắt máy chủ thử nghiệm...")
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except:
                server_process.kill()

    duration = time.time() - start_time
    print("=" * 70)
    print(f" KẾT QUẢ: {passed}/{total} suites ĐẠT ({passed/total*100:.1f}%) | Thời gian: {duration:.2f}s")
    if failed == 0:
        print(" 🎉 TẤT CẢ TEST SUITES HOÀN TOÀN KHÔNG CÓ LỖI (ZERO REGRESSION)!")
    print("=" * 70)

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
