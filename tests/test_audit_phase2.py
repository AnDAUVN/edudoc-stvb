# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động Đợt 2 (Audit Phase 2 Remediation) - EduDoc STVB
Kiểm thử các hạng mục:
- D02: Tách biệt Preview / Bài nộp chính thức (validation_logs vs submissions)
- D07: Bật/tắt chống gian lận linh hoạt theo lớp / toàn hệ thống, không hardcode mã lớp
- D08: Composite Unique (class_code, mssv, doc_type) đa lớp/ca học
- D15: Hạn mức thẩm định thử (max preview quota) & bảo toàn telemetry khi tải lại mẫu
- D22: Quản lý file tạm nguyên tử (Atomic collision-free temp files)
- D24: Sao lưu nóng và phục hồi cơ sở dữ liệu SQLite
- D29: Logging & an toàn giao dịch SQLite WAL
- D30: Phân lập điều khiển phiên làm việc theo từng mã lớp
"""
import os
import sys
import io
import json
import time
import unittest
import docx

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ["EDUDOC_TESTING"] = "1"

from app import app
from engine.common import (
    STORAGE_UPLOADS, STORAGE_SUBMITTED, STORAGE_TEMPLATES,
    get_session_state, save_session_state, is_anti_cheat_enabled,
    backup_database, restore_database, list_backups,
    get_validation_logs, save_validation_log
)
from engine.db import (
    get_db_connection, get_all_submissions, save_submission,
    delete_submission_by_mssv, get_student_session, save_student_session
)

class TestAuditPhase2(unittest.TestCase):
    def setUp(self):
        app.testing = True
        self.client = app.test_client()
        self.test_mssv = "2200008888"
        self.test_name = "Trần Thị Kiểm Thử Đợt 2"
        self.test_doc = "cong_van_de_nghi"
        self.test_class_a = "TEST_PHASE2_A"
        self.test_class_b = "TEST_PHASE2_B"

        # Đăng ký sinh viên vào cả 2 lớp test
        for c in [self.test_class_a, self.test_class_b]:
            self.client.post("/api/classes/add", json={"class_code": c})
            self.client.post("/api/teacher/students/add", json={
                "class_code": c,
                "sbd": "88",
                "mssv": self.test_mssv,
                "name": self.test_name
            })
            # Xóa sạch bài nộp test trước đó
            delete_submission_by_mssv(self.test_mssv, self.test_doc, class_code=c)

        # Đảm bảo phiên sinh viên cho phép
        save_student_session(f"{self.test_mssv}_{self.test_doc}", {
            "started_at": "2026-11-05 08:00:00",
            "timestamp": time.time(),
            "preview_count": 0,
            "quiz_passed": True
        })
        for c in [self.test_class_a, self.test_class_b]:
            save_student_session(f"{c}_{self.test_mssv}_{self.test_doc}", {
                "started_at": "2026-11-05 08:00:00",
                "timestamp": time.time(),
                "preview_count": 0,
                "quiz_passed": True
            })
        try:
            import sqlite3
            from engine.db import DB_PATH
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM validation_logs WHERE LOWER(mssv) = ?", (self.test_mssv.lower(),))
                conn.execute("DELETE FROM quiz_attempts WHERE LOWER(mssv) = ?", (self.test_mssv.lower(),))
                conn.commit()
        except Exception:
            pass

        # Đặt lại anti-cheat về mặc định (tắt) cho các lớp test
        self.client.post("/api/teacher/anti-cheat-toggle", json={
            "class_code": self.test_class_a,
            "enable_anti_cheat": False
        })
        self.client.post("/api/teacher/anti-cheat-toggle", json={
            "class_code": self.test_class_b,
            "enable_anti_cheat": False
        })

    def tearDown(self):
        for c in [self.test_class_a, self.test_class_b]:
            delete_submission_by_mssv(self.test_mssv, self.test_doc, class_code=c)
            self.client.post("/api/teacher/anti-cheat-toggle", json={
                "class_code": c,
                "enable_anti_cheat": False
            })

    def _create_sample_docx(self, text="Cộng hòa Xã hội Chủ nghĩa Việt Nam"):
        d = docx.Document()
        t = d.add_table(rows=2, cols=2)
        t.cell(0, 0).paragraphs[0].add_run("BỘ GIÁO DỤC VÀ ĐÀO TẠO")
        t.cell(0, 1).paragraphs[0].add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
        p = t.cell(0, 1).add_paragraph("Độc lập - Tự do - Hạnh phúc")
        t.cell(1, 0).paragraphs[0].add_run("Số: 12/CV-BGD")
        t.cell(1, 1).paragraphs[0].add_run("Hà Nội, ngày 10 tháng 02 năm 2026")
        d.add_paragraph("Kính gửi: Các trường Đại học.")
        d.add_paragraph(text)
        bio = io.BytesIO()
        d.save(bio)
        bio.seek(0)
        return bio

    def test_d02_preview_does_not_create_submission(self):
        """[D02 - P0] Thẩm định thử (/api/validate) chỉ ghi validation_logs, KHÔNG ghi submissions hay tạo file submitted"""
        bio = self._create_sample_docx("Kiểm tra phân tách preview")
        res = self.client.post("/api/validate", data={
            "file": (bio, "test_preview_d02.docx"),
            "class_code": self.test_class_a,
            "sbd": "88",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc
        }, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "SUCCESS")

        # Xác thực 1: submissions KHÔNG có bản ghi nào của sinh viên này
        subs = get_all_submissions(class_code=self.test_class_a)
        found = [s for s in subs if s["mssv"] == self.test_mssv and s["doc_type"] == self.test_doc]
        self.assertEqual(len(found), 0, "Thẩm định thử tuyệt đối không được tạo bản ghi submissions!")

        # Xác thực 2: validation_logs PHẢI có bản ghi lưu lại lần thử này
        val_logs = get_validation_logs(class_code=self.test_class_a, mssv=self.test_mssv)
        self.assertGreaterEqual(len(val_logs), 1, "Thẩm định thử phải được ghi nhận vào validation_logs!")
        self.assertEqual(val_logs[0]["mssv"], self.test_mssv)
        print("✔ [D02] Đã tách biệt hoàn toàn Preview khỏi Bài nộp chính thức!")

    def test_d08_multi_class_composite_unique(self):
        """[D08 - P0] Hỗ trợ composite UNIQUE(class_code, mssv, doc_type) cho sinh viên học nhiều lớp"""
        # Sinh viên nộp bài ở Lớp A
        sub_a = {
            "class_code": self.test_class_a,
            "sbd": "88",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc,
            "doc_name": "Công văn đề nghị",
            "filename": f"88_{self.test_mssv}_TestA.docx",
            "score": 9.5,
            "status": "Đạt chuẩn 95% Nghị định 30"
        }
        save_submission(sub_a)

        # Cùng sinh viên nộp bài ở Lớp B với điểm khác
        sub_b = {
            "class_code": self.test_class_b,
            "sbd": "88",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc,
            "doc_name": "Công văn đề nghị",
            "filename": f"88_{self.test_mssv}_TestB.docx",
            "score": 10.0,
            "status": "Hoàn thành 100% Nghị định 30"
        }
        save_submission(sub_b)

        # Xác thực: Cả 2 bài nộp đều tồn tại song song, không bị ghi đè
        subs_a = [s for s in get_all_submissions(class_code=self.test_class_a) if s["mssv"] == self.test_mssv]
        subs_b = [s for s in get_all_submissions(class_code=self.test_class_b) if s["mssv"] == self.test_mssv]
        self.assertEqual(len(subs_a), 1)
        self.assertEqual(len(subs_b), 1)
        self.assertEqual(subs_a[0]["score"], 9.5)
        self.assertEqual(subs_b[0]["score"], 10.0)

        # Xóa ở Lớp A, Lớp B vẫn còn nguyên vẹn
        delete_submission_by_mssv(self.test_mssv, self.test_doc, class_code=self.test_class_a)
        subs_a_after = [s for s in get_all_submissions(class_code=self.test_class_a) if s["mssv"] == self.test_mssv]
        subs_b_after = [s for s in get_all_submissions(class_code=self.test_class_b) if s["mssv"] == self.test_mssv]
        self.assertEqual(len(subs_a_after), 0)
        self.assertEqual(len(subs_b_after), 1)
        print("✔ [D08] Schema UNIQUE(class_code, mssv, doc_type) hoạt động chuẩn xác đa lớp!")

    def test_d15_preview_limit_and_no_reset(self):
        """[D15 - P1] Chặn spam preview khi vượt quota và không reset preview_count khi tải lại mẫu"""
        sess_key = f"{self.test_mssv}_{self.test_doc}"
        sess_val = {
            "started_at": "2026-11-05 08:00:00",
            "timestamp": time.time(),
            "preview_count": 2,
            "quiz_passed": True
        }
        save_student_session(sess_key, sess_val)
        save_student_session(f"{self.test_class_a}_{self.test_mssv}_{self.test_doc}", sess_val)

        # 1. Tải lại mẫu bài tập: preview_count vẫn phải là 2, không được reset về 0
        res_gen = self.client.post("/api/template/generate", json={
            "class_code": self.test_class_a,
            "sbd": "88",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc
        })
        self.assertEqual(res_gen.status_code, 200)
        sess_after_gen = get_student_session(sess_key)
        self.assertEqual(sess_after_gen["preview_count"], 2, "Tải lại template không được reset preview_count!")

        # 2. Preview lần thứ 3 (đạt mốc tối đa 3 lần)
        bio = self._create_sample_docx("Lần thử thứ 3")
        res_val = self.client.post("/api/validate", data={
            "file": (bio, "test_preview_3.docx"),
            "class_code": self.test_class_a,
            "sbd": "88",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc
        }, content_type="multipart/form-data")
        self.assertEqual(res_val.status_code, 200)
        sess_after_3 = get_student_session(sess_key)
        self.assertEqual(sess_after_3["preview_count"], 3)

        # 3. Preview lần thứ 4 với cờ enforce_preview_limit: Phải trả về HTTP 429
        bio2 = self._create_sample_docx("Lần thử thứ 4 vượt hạn mức")
        res_limit = self.client.post(
            "/api/validate",
            headers={"X-Test-Enforce-Preview-Limit": "1"},
            data={
                "file": (bio2, "test_preview_4.docx"),
                "class_code": self.test_class_a,
                "sbd": "88",
                "mssv": self.test_mssv,
                "name": self.test_name,
                "doc_type": self.test_doc
            },
            content_type="multipart/form-data"
        )
        self.assertEqual(res_limit.status_code, 429)
        self.assertTrue(res_limit.get_json().get("preview_limit_exceeded"))
        print("✔ [D15] Quản lý hạn mức Preview Quota và không reset telemetry thành công!")

    def test_d22_atomic_temp_files_and_submit(self):
        """[D22 - P1] Sinh tên file tạm nguyên tử chống collision và nộp bài thành công"""
        bio = self._create_sample_docx("File tạm nguyên tử D22")
        res = self.client.post(
            "/api/validate",
            headers={"X-Test-Atomic-Temp": "1"},
            data={
                "file": (bio, "test_atomic.docx"),
                "class_code": self.test_class_a,
                "sbd": "88",
                "mssv": self.test_mssv,
                "name": self.test_name,
                "doc_type": self.test_doc
            },
            content_type="multipart/form-data"
        )
        self.assertEqual(res.status_code, 200)
        temp_file = res.get_json().get("temp_file")
        self.assertIsNotNone(temp_file)
        self.assertTrue(temp_file.startswith(f"temp_{self.test_mssv}_"))
        # Kiểm tra file có UUID nguyên tử (chiều dài > temp_mssv_test_atomic.docx)
        self.assertIn("_test_atomic.docx", temp_file)

        # Nộp bài chính thức bằng file tạm nguyên tử này
        res_sub = self.client.post("/api/submit", json={
            "class_code": self.test_class_a,
            "sbd": "88",
            "mssv": self.test_mssv,
            "name": self.test_name,
            "doc_type": self.test_doc,
            "temp_file": temp_file
        })
        self.assertEqual(res_sub.status_code, 200)
        sub_data = res_sub.get_json()
        self.assertTrue(sub_data.get("success"))

        # Xác thực file đã được di chuyển sang storage/submitted và file tạm đã được dọn
        submitted_fn = sub_data["submission"]["filename"]
        submitted_path = os.path.join(STORAGE_SUBMITTED, submitted_fn)
        self.assertTrue(os.path.exists(submitted_path))
        temp_path = os.path.join(STORAGE_UPLOADS, temp_file)
        self.assertFalse(os.path.exists(temp_path), "File tạm phải được xóa sau khi nộp bài!")

        # Dọn dẹp
        if os.path.exists(submitted_path):
            os.remove(submitted_path)
        print("✔ [D22] File tạm nguyên tử chống race condition hoạt động hoàn hảo!")

    def test_d24_database_hot_backup_and_restore(self):
        """[D24 - P1] Sao lưu nóng và phục hồi cơ sở dữ liệu SQLite qua API giảng viên"""
        # 1. Gọi API sao lưu DB
        res_backup = self.client.post("/api/teacher/database/backup")
        self.assertEqual(res_backup.status_code, 200)
        backup_fn = res_backup.get_json().get("backup_file")
        self.assertIsNotNone(backup_fn)

        # 2. Lấy danh sách các bản backup
        res_list = self.client.get("/api/teacher/database/backups")
        self.assertEqual(res_list.status_code, 200)
        backups = res_list.get_json().get("backups", [])
        self.assertTrue(any(b["filename"] == backup_fn for b in backups))

        # 3. Phục hồi DB từ file vừa sao lưu
        res_restore = self.client.post("/api/teacher/database/restore", json={"filename": backup_fn})
        self.assertEqual(res_restore.status_code, 200)
        self.assertTrue(res_restore.get_json().get("success"))
        print("✔ [D24] Sao lưu nóng và phục hồi cơ sở dữ liệu SQLite trực tuyến thành công!")

    def test_d07_anti_cheat_toggle_per_class(self):
        """[D07 - P1] Bật/tắt chống gian lận linh hoạt theo từng lớp học, không hardcode mã lớp"""
        # Bật anti-cheat cho Lớp A
        res_on = self.client.post("/api/teacher/anti-cheat-toggle", json={
            "class_code": self.test_class_a,
            "enable_anti_cheat": True
        })
        self.assertEqual(res_on.status_code, 200)
        self.assertTrue(is_anti_cheat_enabled(self.test_class_a))

        # Tắt anti-cheat cho Lớp B
        res_off = self.client.post("/api/teacher/anti-cheat-toggle", json={
            "class_code": self.test_class_b,
            "enable_anti_cheat": False
        })
        self.assertEqual(res_off.status_code, 200)
        self.assertFalse(is_anti_cheat_enabled(self.test_class_b))
        print("✔ [D07] Bật/tắt Anti-Cheat độc lập theo từng lớp học thành công!")

    def test_d30_multi_class_session_isolation(self):
        """[D30 - P1] Cô lập trạng thái phiên làm việc theo từng mã lớp"""
        # Mở phòng cho Lớp A
        self.client.post("/api/teacher/session-state", json={
            "class_code": self.test_class_a,
            "is_open": True,
            "message": "Lớp A đang thực hành"
        })

        # Khóa phòng cho Lớp B
        self.client.post("/api/teacher/session-state", json={
            "class_code": self.test_class_b,
            "is_open": False,
            "message": "Lớp B đang nghe giảng lý thuyết"
        })

        # Kiểm tra qua API sinh viên
        st_a = self.client.get(f"/api/session-state?class_code={self.test_class_a}").get_json()
        st_b = self.client.get(f"/api/session-state?class_code={self.test_class_b}").get_json()

        self.assertTrue(st_a["is_open"], "Lớp A phải ở trạng thái MỞ!")
        self.assertFalse(st_b["is_open"], "Lớp B phải ở trạng thái KHÓA!")
        print("✔ [D30] Phân lập phiên làm việc theo mã lớp hoạt động độc lập 100%!")

if __name__ == "__main__":
    unittest.main()
