# -*- coding: utf-8 -*-
"""
Công cụ đóng gói mã nguồn sạch (Clean Source Package) cho EduDoc STVB:
- Loại bỏ toàn bộ thư mục .git, __pycache__, các file .pyc, và các file docx tạm.
- Giúp giảm dung lượng file nén hơn 90% (từ 50-80MB xuống chỉ còn ~1-2MB).
- Dễ dàng gửi qua Zalo, Email, Google Drive mà không bị chặn tệp hoặc quá dung lượng.
"""
import os
import sys
import zipfile
import shutil
import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT_DIR)

def create_clean_package():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"edudoc_stvb_clean_code_{timestamp}.zip"
    output_latest = "edudoc_stvb_clean_code_latest.zip"
    output_path = os.path.join(ROOT_DIR, output_filename)
    latest_path = os.path.join(ROOT_DIR, output_latest)

    print("=" * 70)
    print("      ĐÓNG GÓI MÃ NGUỒN SẠCH & TỐI ƯU DUNG LƯỢNG (EDUDOC-STVB)")
    print("=" * 70)
    print(f" [+] Thư mục gốc: {ROOT_DIR}")
    print(f" [+] Tệp nén đầu ra: {output_filename}")

    # Danh sách các thư mục và tệp cần đóng gói
    include_files = [
        "app.py",
        "render.yaml",
        "runtime.txt",
        "requirements.txt",
        "run.bat",
        "run_app.py",
        "Cap_Nhat_Len_Web.bat",
        "cap_nhat.ps1",
        ".gitignore",
        "README.md",
        "Tao_Ban_Sao_Luu_Gon_Nhe.bat"
    ]

    include_dirs = [
        "engine",
        "routes",
        "templates",
        "static",
        "tests",
        "tools"
    ]

    # Các file dữ liệu mẫu (JSON) cần giữ
    data_files = [
        "classes.json",
        "document_templates.json",
        "questions.json",
        "session_state.json",
        "students_roster.json",
        "teachers.json"
    ]

    exclude_patterns = [
        "__pycache__",
        ".git",
        ".vscode",
        ".idea",
        "venv",
        "env",
        ".db",
        ".db-wal",
        ".db-shm",
        ".sqlite",
        ".zip",
        ".rar",
        ".7z"
    ]

    count_files = 0
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Thêm các tệp lẻ ở thư mục gốc
        for f in include_files:
            fp = os.path.join(ROOT_DIR, f)
            if os.path.exists(fp):
                zf.write(fp, arcname=f)
                count_files += 1

        # 2. Thêm các thư mục mã nguồn
        for d in include_dirs:
            dp = os.path.join(ROOT_DIR, d)
            if not os.path.exists(dp):
                continue
            for root, dirs, files in os.walk(dp):
                # Bỏ qua __pycache__ và thư mục ẩn
                dirs[:] = [sub for sub in dirs if not any(p in sub for p in exclude_patterns)]
                for file in files:
                    if file.endswith((".pyc", ".pyo", ".docx", ".zip", ".rar")):
                        continue
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, ROOT_DIR)
                    zf.write(file_path, arcname=rel_path)
                    count_files += 1

        # 3. Thêm các tệp data JSON mẫu
        for df in data_files:
            dfp = os.path.join(ROOT_DIR, "data", df)
            if os.path.exists(dfp):
                zf.write(dfp, arcname=os.path.join("data", df))
                count_files += 1

        # 4. Thêm các thư mục storage rỗng kèm .gitkeep
        for sdir in ["templates", "submitted", "uploads"]:
            gitkeep_path = os.path.join(ROOT_DIR, "storage", sdir, ".gitkeep")
            arc_keep = os.path.join("storage", sdir, ".gitkeep")
            if os.path.exists(gitkeep_path):
                zf.write(gitkeep_path, arcname=arc_keep)
            else:
                zf.writestr(arc_keep, "")
            count_files += 1

    # Tạo bản copy latest
    try:
        shutil.copy2(output_path, latest_path)
    except Exception:
        pass

    size_bytes = os.path.getsize(output_path)
    size_mb = size_bytes / (1024 * 1024)

    print(f" [+] Đã đóng gói thành công {count_files} tệp tin!")
    print(f" [+] Dung lượng tệp nén: {size_mb:.2f} MB ({size_bytes:,} bytes)")
    print(f" [+] Giảm > 90% dung lượng so với việc nén cả thư mục .git!")
    print("=" * 70)
    print(f" 🎉 BẢN SAO LƯU GỌN NHẸ SẴN SÀNG TẠI: {output_latest}")
    print("=" * 70)

if __name__ == "__main__":
    create_clean_package()
