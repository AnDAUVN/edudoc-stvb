# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import socket
import shutil
import tempfile

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)
os.environ["EDUDOC_TESTING"] = "1"

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
    "test_schema_layouts.py",
    "test_session_control.py",
    "test_anti_cheat_stages.py",
    "test_cong_van_tu_gia_dinh.py",
    "test_roster_management.py",
    "test_sqlite_and_cleanup.py",
    "test_teacher_selector_and_quiz_edit.py",
    "test_audit_phase1.py",
    "test_audit_phase2.py",
    "test_audit_phase3.py",
    "test_audit_phase4.py",
    "test_audit_priorities.py",
    "test_audit_cn17_cn18.py",
    "comprehensive_audit_suite.py",
    "test_audit_repairs.py",
    "test_audit_r2.py"
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
    server_log = None
    if is_server_running():
        print("[!] Cổng 5000 đang được sử dụng. Dừng kiểm thử để tránh tác động máy chủ đang chạy.")
        return 1
    if not is_server_running():
        print(" [i] Máy chủ 127.0.0.1:5000 chưa chạy. Đang tự động khởi động máy chủ thử nghiệm...")
        server_env = os.environ.copy()
        server_env["EDUDOC_TESTING"] = "1"
        server_log = open(os.path.join(ROOT_DIR, "server-test.log"), "w+", encoding="utf-8")
        server_process = subprocess.Popen([sys.executable, "app.py"], cwd=ROOT_DIR, env=server_env,
                                          stdout=server_log, stderr=subprocess.STDOUT)
        for _ in range(20):
            time.sleep(0.5)
            if is_server_running():
                print(" [+] Máy chủ thử nghiệm đã sẵn sàng tại http://127.0.0.1:5000!")
                break
        else:
            print(" [!] Không thể khởi động máy chủ thử nghiệm sau 10s; dừng kiểm thử.")
            server_process.terminate()
            server_process.wait(timeout=5)
            server_log.seek(0)
            print(server_log.read())
            server_log.close()
            return 1

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
                print(res.stderr if res.stderr else res.stdout)
                failed += 1
    finally:
        try:
            import sqlite3
            db_file = os.path.join(ROOT_DIR, "data", "edudoc.db")
            if os.path.exists(db_file):
                c = sqlite3.connect(db_file)
                c.execute("UPDATE session_state SET enable_anti_cheat = 0;")
                c.commit()
                c.close()
        except Exception:
            pass
        if server_process:
            print(" [i] Đang tắt máy chủ thử nghiệm...")
            server_process.terminate()
            try:
                server_process.wait(timeout=3)
            except:
                server_process.kill()
                server_process.wait(timeout=5)
        if server_log:
            server_log.close()

    duration = time.time() - start_time
    print("=" * 70)
    print(f" KẾT QUẢ: {passed}/{total} suites ĐẠT ({passed/total*100:.1f}%) | Thời gian: {duration:.2f}s")
    if failed == 0:
        print(" 🎉 TẤT CẢ TEST SUITES HOÀN TOÀN KHÔNG CÓ LỖI (ZERO REGRESSION)!")
    print("=" * 70)

    return 0 if failed == 0 else 1

def run_isolated():
    """Legacy suites mutate data and clear tables; always run on a disposable copy."""
    with tempfile.TemporaryDirectory(prefix="edudoc-audit-", dir=os.path.dirname(ROOT_DIR)) as temp:
        isolated = os.path.join(temp, "project")
        shutil.copytree(ROOT_DIR, isolated, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "*.zip", "venv", ".venv", "env",
            ".session-key", ".teacher-pin", "*.db-wal", "*.db-shm"
        ))
        env = os.environ.copy()
        env.update({"EDUDOC_TEST_WORKER": "1", "EDUDOC_TESTING": "1", "TEACHER_PIN": "gv2026"})
        return subprocess.run([sys.executable, "-u", os.path.join(isolated, "tests", "run_all_tests.py")],
                              cwd=isolated, env=env).returncode


if __name__ == "__main__":
    sys.exit(main() if os.environ.get("EDUDOC_TEST_WORKER") == "1" else run_isolated())
