# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động xác thực:
1. Cơ sở dữ liệu SQLite với cơ chế khóa WAL (Write-Ahead Logging).
2. Tự động chuyển đổi dữ liệu và đồng bộ bộ nhớ cache JSON.
3. Cơ chế khử lặp tiền tố tên tệp (temp_..._temp_...).
4. Cơ chế dọn rác tệp tạm (try...finally) tại storage/uploads/ sau khi nộp bài.
5. Cấu hình triển khai chuẩn hóa (.gitignore, runtime.txt).
"""
import os
import sys
import io
import json
import sqlite3
import unittest
import shutil

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT_DIR)
sys.path.insert(0, ROOT_DIR)
os.environ["EDUDOC_TESTING"] = "1"

from app import app
from engine.db import (
    get_db_connection, init_db, DB_PATH,
    get_all_submissions, save_submission, delete_submission_by_mssv,
    get_all_fraud_logs, add_fraud_log, clear_all_fraud_logs,
    get_student_session, save_student_session
)
from engine.security import generate_anti_cheat_token
from engine.common import (
    STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    STUDENTS_ROSTER_FILE, load_json_file, save_json_file
)
import docx

class TestSqliteAndCleanup(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.test_mssv = "2100009999"
        self.test_class = "KN01"
        self.test_name = "NGUYỄN VĂN TEST"
        self.test_doc = "cong_van_de_nghi"

        # Đảm bảo sinh viên có trong roster
        roster = load_json_file(STUDENTS_ROSTER_FILE, {})
        if self.test_class not in roster:
            roster[self.test_class] = []
        
        # Thêm nếu chưa có
        if not any(s.get("mssv") == self.test_mssv for s in roster[self.test_class]):
            roster[self.test_class].append({
                "sbd": "99",
                "mssv": self.test_mssv,
                "name": self.test_name
            })
            save_json_file(STUDENTS_ROSTER_FILE, roster)

    def tearDown(self):
        # Dọn dẹp dữ liệu test khỏi SQLite
        delete_submission_by_mssv(self.test_mssv, self.test_doc)
        
        # Dọn dẹp sinh viên test khỏi roster
        roster = load_json_file(STUDENTS_ROSTER_FILE, {})
        if self.test_class in roster:
            roster[self.test_class] = [s for s in roster[self.test_class] if s.get("mssv") != self.test_mssv]
            save_json_file(STUDENTS_ROSTER_FILE, roster)

    def test_01_sqlite_wal_mode(self):
        """Kiểm tra SQLite đã kích hoạt chế độ WAL và cấu hình an toàn đa luồng"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode;")
            journal_mode = cursor.fetchone()[0]
            # Trong môi trường bình thường là wal, nếu in-memory có thể là memory
            self.assertIn(journal_mode.lower(), ["wal", "memory"], f"Journal mode phải là WAL (hiện tại: {journal_mode})")

            # Kiểm tra các bảng cốt lõi
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn("submissions", tables)
            self.assertIn("fraud_logs", tables)
            self.assertIn("student_sessions", tables)

            # Kiểm tra chỉ mục (index)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index';")
            indexes = [row[0] for row in cursor.fetchall()]
            self.assertIn("idx_submissions_mssv", indexes)
            self.assertIn("idx_fraud_class", indexes)
            self.assertIn("idx_sessions_mssv", indexes)
        finally:
            conn.close()

    def test_02_sqlite_crud_and_sync(self):
        """Kiểm tra hoạt động ghi/đọc/xóa dữ liệu trên SQLite"""
        # 1. Thêm submission
        test_sub = {
            "class_code": self.test_class,
            "sbd": "99",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc,
            "doc_name": "Công văn đề nghị",
            "filename": f"99_{self.test_mssv}_TEST.docx",
            "score": 10.0,
            "flags": ["Kiểm tra tự động"]
        }
        save_submission(test_sub)

        # Đọc lại từ DB
        subs = get_all_submissions(class_code=self.test_class)
        found = [s for s in subs if s["mssv"] == self.test_mssv and s["doc_type"] == self.test_doc]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], self.test_name)
        self.assertEqual(found[0]["flags"], ["Kiểm tra tự động"])

        # 2. Student Session
        save_student_session(f"{self.test_mssv}_{self.test_doc}", {
            "started_at": "2026-10-28 10:00:00",
            "timestamp": 123456789.0,
            "preview_count": 2
        })
        sess = get_student_session(f"{self.test_mssv}_{self.test_doc}")
        self.assertIsNotNone(sess)
        self.assertEqual(sess["preview_count"], 2)

        # 3. Fraud Log
        fraud_id = f"test_fraud_{self.test_mssv}"
        add_fraud_log({
            "id": fraud_id,
            "class_code": self.test_class,
            "doc_type": self.test_doc,
            "fraud_data": {"reason": "Test Fraud Entry"}
        })
        frauds = get_all_fraud_logs(class_code=self.test_class)
        f_found = [f for f in frauds if f["id"] == fraud_id]
        self.assertEqual(len(f_found), 1)
        self.assertEqual(f_found[0]["fraud_data"]["reason"], "Test Fraud Entry")

    def test_03_filename_sanitization_no_temp_accumulation(self):
        """Kiểm tra chống lặp tên tệp dạng temp_2100001234_temp_2100001234_..."""
        # Tạo một tài liệu docx hợp lệ có metadata bảo mật hệ thống
        doc = docx.Document()
        doc.add_paragraph("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        now_str = "20261028100000"
        token = generate_anti_cheat_token("99", self.test_mssv, self.test_doc, now_str)
        doc.core_properties.identifier = f"STVB_SIGNATURE:{token}"
        doc.core_properties.keywords = f"99|{self.test_mssv}|{self.test_name}|{self.test_doc}|{now_str}"

        doc_io = io.BytesIO()
        doc.save(doc_io)
        doc_io.seek(0)

        # Giả lập tên tệp đã bị lặp tiền tố nhiều lần
        chained_filename = f"temp_{self.test_mssv}_temp_{self.test_mssv}_01_sample.docx"
        
        response = self.client.post("/api/validate", data={
            "file": (doc_io, chained_filename),
            "class_code": self.test_class,
            "sbd": "99",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc
        }, content_type="multipart/form-data")

        self.assertEqual(response.status_code, 200)
        res_data = response.get_json()
        saved_temp_name = res_data.get("temp_file", "")

        # Tên tệp lưu phải được làm sạch, chỉ chứa một tiền tố temp_{mssv}_
        expected_name = f"temp_{self.test_mssv}_01_sample.docx"
        self.assertEqual(saved_temp_name, expected_name, f"Tên tệp lưu ({saved_temp_name}) phải được khử lặp tiền tố thành ({expected_name})")

        # Dọn dẹp tệp tạm sau khi test
        temp_file_on_disk = os.path.join(STORAGE_UPLOADS, saved_temp_name)
        if os.path.exists(temp_file_on_disk):
            os.remove(temp_file_on_disk)

    def test_04_submit_try_finally_cleanup(self):
        """Kiểm tra cơ chế try...finally tự động xóa file tạm tại storage/uploads sau khi nộp bài"""
        # Tạo sẵn 1 file tạm trong storage/uploads
        test_temp_name = f"temp_{self.test_mssv}_to_be_submitted.docx"
        test_temp_path = os.path.join(STORAGE_UPLOADS, test_temp_name)
        
        doc = docx.Document()
        doc.add_paragraph("Văn bản thử nghiệm nộp bài chính thức")
        doc.save(test_temp_path)
        self.assertTrue(os.path.exists(test_temp_path), "File tạm phải được tạo trước khi nộp")

        # Gửi yêu cầu nộp bài chính thức
        response = self.client.post("/api/submit", json={
            "class_code": self.test_class,
            "sbd": "99",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc,
            "temp_file": test_temp_name
        })

        self.assertEqual(response.status_code, 200)
        res_data = response.get_json()
        self.assertTrue(res_data.get("success"))

        # Xác thực 1: File tạm trong storage/uploads/ ĐÃ ĐƯỢC XÓA BẰNG TRY...FINALLY
        self.assertFalse(os.path.exists(test_temp_path), "File tạm trong storage/uploads/ phải bị xóa ngay lập tức sau khi nộp bài!")

        # Xác thực 2: File chính thức đã được lưu trong storage/submitted/
        submitted_filename = res_data["submission"]["filename"]
        final_path = os.path.join(STORAGE_SUBMITTED, submitted_filename)
        self.assertTrue(os.path.exists(final_path), f"File chính thức {submitted_filename} phải tồn tại trong storage/submitted/")

        # Dọn dẹp file chính thức tạo ra
        if os.path.exists(final_path):
            os.remove(final_path)

    def test_05_deployment_configuration(self):
        """Kiểm tra cấu hình .gitignore và runtime.txt cho môi trường Production (Render/Linux)"""
        # 1. Kiểm tra runtime.txt
        runtime_path = os.path.join(ROOT_DIR, "runtime.txt")
        self.assertTrue(os.path.exists(runtime_path), "Tệp runtime.txt phải tồn tại")
        with open(runtime_path, "r", encoding="utf-8") as f:
            runtime_content = f.read().strip()
        self.assertEqual(runtime_content, "python-3.11.9", "runtime.txt phải chỉ định đúng python-3.11.9")

        # 2. Kiểm tra .gitignore
        gitignore_path = os.path.join(ROOT_DIR, ".gitignore")
        self.assertTrue(os.path.exists(gitignore_path), "Tệp .gitignore phải tồn tại")
        with open(gitignore_path, "r", encoding="utf-8") as f:
            gitignore_content = f.read()

        required_patterns = [
            "__pycache__/",
            "*.pyc",
            "storage/uploads/*",
            "storage/test_temp/*",
            "storage/test_out/*",
            "data/edudoc.db*"
        ]
        for pattern in required_patterns:
            self.assertIn(pattern, gitignore_content, f".gitignore phải chứa mẫu: {pattern}")

if __name__ == "__main__":
    unittest.main()
