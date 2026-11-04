# -*- coding: utf-8 -*-
"""
BỘ KIỂM THỬ 6 NHÓM ƯU TIÊN THEO BÁO CÁO ĐỐI CHIẾU KHẮC PHỤC EDUDOC STVB
(Priority 1 - Priority 6)
"""
import os
import sys
import json
import uuid
import shutil
import zipfile
import unittest
import hashlib
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from engine.db import (
    get_db_connection,
    get_all_submissions, get_quiz_attempt, init_db
)
from engine.common import (
    DATA_DIR, STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    is_session_open, is_anti_cheat_enabled,
    save_session_state, get_session_state
)
from engine.security import (
    generate_anti_cheat_token, create_student_raw_template,
    validate_docx_resource_limits
)
import docx

class TestAuditPriorities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.app = create_app()
        cls.app.config["TESTING"] = True
        cls.client = cls.app.test_client()

        cls.class_a = "PRIO_CLA"
        cls.class_b = "PRIO_CLB"
        cls.mssv = "2280609999"
        cls.sbd = "99"
        cls.name = "Nguyễn Văn Ưu Tiên"

        # Đăng ký sinh viên vào danh sách cả 2 lớp để kiểm thử
        roster_path = os.path.join(DATA_DIR, "students_roster.json")
        try:
            with open(roster_path, "r", encoding="utf-8") as f:
                roster = json.load(f)
        except Exception:
            roster = {}
        roster[cls.class_a] = [{"sbd": cls.sbd, "mssv": cls.mssv, "name": cls.name}]
        roster[cls.class_b] = [{"sbd": cls.sbd, "mssv": cls.mssv, "name": cls.name}]
        with open(roster_path, "w", encoding="utf-8") as f:
            json.dump(roster, f, ensure_ascii=False, indent=2)

    def tearDown(self):
        # Dọn dẹp dữ liệu kiểm thử
        conn = get_db_connection()
        conn.execute("DELETE FROM submissions WHERE mssv = ?;", (self.mssv,))
        conn.execute("DELETE FROM validation_logs WHERE mssv = ?;", (self.mssv,))
        conn.execute("DELETE FROM quiz_attempts WHERE mssv = ?;", (self.mssv,))
        conn.execute("DELETE FROM session_state WHERE key IN (?, ?);", (f"class_{self.class_a}", f"class_{self.class_b}"))
        conn.commit()
        conn.close()

    # =========================================================================
    # PRIORITY 1: RÀNG BUỘC ATTEMPT_ID CHO BÀI TRẮC NGHIỆM & CHẤM ĐIỂM NGHIÊM NGẶT
    # =========================================================================
    def test_priority_1_quiz_attempt_binding_and_scoring(self):
        """[Priority 1] Ràng buộc attempt_id, điểm tối đa <= 5, chỉ chấm 5 câu được giao, chặn nộp 8 câu"""
        # Mở phòng thi
        save_session_state({"is_open": True, "enforce_roster": True, "enforce_quiz": True}, self.class_a)

        # 1. Gọi /api/quiz/get để lấy đề thi và attempt_id
        res_get = self.client.post("/api/quiz/get", json={
            "class_code": self.class_a,
            "mssv": self.mssv,
            "doc_type": "cong_van_de_nghi"
        })
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        self.assertIn("attempt_id", data_get)
        attempt_id = data_get["attempt_id"]
        assigned_q_ids = [q["id"] for q in data_get["questions"]]
        self.assertEqual(len(assigned_q_ids), 5)

        # Kiểm tra phiên đã được lưu trong DB quiz_attempts
        attempt_row = get_quiz_attempt(attempt_id)
        self.assertIsNotNone(attempt_row)
        self.assertEqual(attempt_row["status"], "IN_PROGRESS")

        # 2. Sinh viên gian lận: nộp đáp án cho tất cả 8 câu trong ngân hàng câu hỏi
        all_8_answers = {
            "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0, "7": 0, "8": 0
        }
        res_sub = self.client.post("/api/quiz/submit", json={
            "attempt_id": attempt_id,
            "class_code": self.class_a,
            "mssv": self.mssv,
            "doc_type": "cong_van_de_nghi",
            "answers": all_8_answers
        })
        self.assertEqual(res_sub.status_code, 200)
        data_sub = res_sub.get_json()
        # Điểm số tuyệt đối không được vượt quá 5
        self.assertLessEqual(data_sub["score"], 5)
        self.assertEqual(data_sub["total"], 5)

        # 3. Nộp sai MSSV hoặc sai attempt_id bị từ chối
        res_fake = self.client.post("/api/quiz/submit", json={
            "attempt_id": str(uuid.uuid4()),
            "class_code": self.class_a,
            "mssv": self.mssv,
            "doc_type": "cong_van_de_nghi",
            "answers": {"1": 0}
        })
        self.assertEqual(res_fake.status_code, 400)
        print("✔ [Priority 1] Ràng buộc attempt_id và giới hạn điểm trắc nghiệm thành công!")

    # =========================================================================
    # PRIORITY 2: CHỐNG XUNG ĐỘT TÊN FILE NỘP ĐA LỚP & SHA-256 CHECKSUM
    # =========================================================================
    def test_priority_2_multi_class_file_isolation_and_checksum(self):
        """[Priority 2] Hai lớp khác nhau nộp cùng MSSV không bị ghi đè tệp và có mã SHA-256"""
        save_session_state({"is_open": True, "enforce_roster": False}, self.class_a)
        save_session_state({"is_open": True, "enforce_roster": False}, self.class_b)

        # Tạo file tạm hợp lệ cho lớp A
        tmp_name_a = f"temp_{self.mssv}_{uuid.uuid4().hex[:8]}_test_p2_a.docx"
        tmp_path_a = os.path.join(STORAGE_UPLOADS, tmp_name_a)
        create_student_raw_template(self.sbd, self.mssv, self.name, "cong_van_de_nghi", "Mẫu kiểm tra lớp A", tmp_path_a)

        # Nộp bài lớp A
        res_a = self.client.post("/api/submit", json={
            "class_code": self.class_a,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": "cong_van_de_nghi",
            "temp_file": tmp_name_a
        })
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.get_json()
        fn_a = data_a["submission"]["filename"]
        chk_a = data_a["submission"]["checksum"]
        self.assertTrue(fn_a.startswith(f"{self.class_a}_{self.sbd}_{self.mssv}_"))
        self.assertEqual(len(chk_a), 64)  # SHA-256 64 ký tự hex

        # Tạo file tạm hợp lệ cho lớp B (cùng MSSV)
        tmp_name_b = f"temp_{self.mssv}_{uuid.uuid4().hex[:8]}_test_p2_b.docx"
        tmp_path_b = os.path.join(STORAGE_UPLOADS, tmp_name_b)
        create_student_raw_template(self.sbd, self.mssv, self.name, "cong_van_de_nghi", "Mẫu kiểm tra lớp B", tmp_path_b)

        # Nộp bài lớp B
        res_b = self.client.post("/api/submit", json={
            "class_code": self.class_b,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": "cong_van_de_nghi",
            "temp_file": tmp_name_b
        })
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.get_json()
        fn_b = data_b["submission"]["filename"]
        self.assertTrue(fn_b.startswith(f"{self.class_b}_{self.sbd}_{self.mssv}_"))

        # Kiểm tra hai tệp nộp tồn tại độc lập trên ổ đĩa, không ghi đè nhau
        path_a = os.path.join(STORAGE_SUBMITTED, fn_a)
        path_b = os.path.join(STORAGE_SUBMITTED, fn_b)
        self.assertTrue(os.path.exists(path_a))
        self.assertTrue(os.path.exists(path_b))
        self.assertNotEqual(fn_a, fn_b)

        # Dọn dẹp file nộp
        if os.path.exists(path_a): os.remove(path_a)
        if os.path.exists(path_b): os.remove(path_b)
        print("✔ [Priority 2] Cô lập tệp nộp đa lớp và tạo mã checksum SHA-256 thành công!")

    # =========================================================================
    # PRIORITY 3: CÔ LẬP TRẠNG THÁI PHÒNG THI CHUẨN XÁC GIỮA CÁC LỚP
    # =========================================================================
    def test_priority_3_class_session_isolation(self):
        """[Priority 3] Khóa lớp A trong khi mở lớp B: Lớp A bị chặn 403 trên mọi API, Lớp B hoạt động bình thường"""
        # Khóa lớp A, Mở lớp B
        save_session_state({"is_open": False, "enforce_roster": True}, self.class_a)
        save_session_state({"is_open": True, "enforce_roster": True}, self.class_b)

        headers_force = {"X-Test-Force-Check-Open": "0"}

        # Kiểm tra /api/quiz/get: Lớp A bị 403, Lớp B được 200
        res_q_a = self.client.post("/api/quiz/get", json={
            "class_code": self.class_a, "mssv": self.mssv, "doc_type": "cong_van_de_nghi"
        }, headers=headers_force)
        self.assertEqual(res_q_a.status_code, 403)

        res_q_b = self.client.post("/api/quiz/get", json={
            "class_code": self.class_b, "mssv": self.mssv, "doc_type": "cong_van_de_nghi"
        })
        self.assertEqual(res_q_b.status_code, 200)

        # Kiểm tra /api/template/generate: Lớp A bị 403
        res_t_a = self.client.post("/api/template/generate", json={
            "class_code": self.class_a, "sbd": self.sbd, "mssv": self.mssv, "name": self.name, "doc_type": "cong_van_de_nghi"
        }, headers=headers_force)
        self.assertEqual(res_t_a.status_code, 403)
        print("✔ [Priority 3] Cô lập trạng thái phòng thi theo mã lớp thành công!")

    # =========================================================================
    # PRIORITY 4: CHẶN TEST HEADERS KHI Ở CHẾ ĐỘ PRODUCTION
    # =========================================================================
    def test_priority_4_production_mode_ignores_test_headers(self):
        """[Priority 4] Chế độ production tuyệt đối không cho phép dùng X-Test-* để bypass auth hoặc anti-cheat"""
        old_testing = self.app.testing
        old_config_testing = self.app.config.get("TESTING", True)
        old_env = os.environ.get("EDUDOC_TESTING")
        try:
            self.app.testing = False
            self.app.config["TESTING"] = False
            if "EDUDOC_TESTING" in os.environ:
                del os.environ["EDUDOC_TESTING"]
            # Gửi request đến API giảng viên nhạy cảm với header giả mạo
            res = self.client.get("/api/teacher/data", headers={"X-Test-Auth-Bypass": "1"})
            # Phải bị 401 Unauthorized vì không có PIN
            self.assertEqual(res.status_code, 401)
        finally:
            self.app.testing = old_testing
            self.app.config["TESTING"] = old_config_testing
            if old_env is not None:
                os.environ["EDUDOC_TESTING"] = old_env
        print("✔ [Priority 4] Chặn hoàn toàn bypass qua X-Test-* ở chế độ production thành công!")

    # =========================================================================
    # PRIORITY 5: THẨM ĐỊNH TOÀN VẸN CẤU TRÚC DOCX VÀ TỪ CHỐI PHÔI GIẢ MẠO
    # =========================================================================
    def test_priority_5_docx_integrity_and_hmac_tamper_rejection(self):
        """[Priority 5] Từ chối file ZIP thiếu XML hoặc XML hỏng; từ chối phôi bị sửa đổi HMAC với HTTP 400"""
        save_session_state({"is_open": True, "enforce_roster": False}, self.class_a)

        # 1. Tạo file ZIP có [Content_Types].xml nhưng thiếu word/document.xml
        corrupt_zip_path = os.path.join(STORAGE_UPLOADS, f"temp_{self.mssv}_corrupt_missing_doc.docx")
        with zipfile.ZipFile(corrupt_zip_path, "w") as z:
            z.writestr("[Content_Types].xml", "<Types></Types>")

        # Thẩm định tài nguyên phải phát hiện không hợp lệ
        valid, msg, _ = validate_docx_resource_limits(corrupt_zip_path)
        self.assertFalse(valid, "ZIP thiếu word/document.xml phải bị từ chối!")

        # 2. Tạo file ZIP có word/document.xml nhưng XML bị lỗi cú pháp
        malformed_xml_path = os.path.join(STORAGE_UPLOADS, f"temp_{self.mssv}_malformed_xml.docx")
        with zipfile.ZipFile(malformed_xml_path, "w") as z:
            z.writestr("[Content_Types].xml", "<Types></Types>")
            z.writestr("word/document.xml", "<w:document><w:body><w:p>Unclosed Tag")

        valid_m, msg_m, _ = validate_docx_resource_limits(malformed_xml_path)
        self.assertFalse(valid_m, "XML bị lỗi cú pháp phải bị từ chối!")

        # 3. Tạo file Word có token HMAC giả mạo
        tampered_path = os.path.join(STORAGE_UPLOADS, f"temp_{self.mssv}_tampered_hmac.docx")
        create_student_raw_template(self.sbd, self.mssv, self.name, "cong_van_de_nghi", "Văn bản mẫu", tampered_path)
        # Sửa token trong core_properties
        doc = docx.Document(tampered_path)
        doc.core_properties.identifier = "STVB_SIGNATURE:fake_forged_hmac_token_123"
        doc.save(tampered_path)

        # Nộp bài với phôi giả mạo phải bị từ chối ngay với HTTP 400
        res_tamper = self.client.post("/api/submit", json={
            "class_code": self.class_a,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": "cong_van_de_nghi",
            "temp_file": os.path.basename(tampered_path)
        })
        self.assertEqual(res_tamper.status_code, 400)
        self.assertIn("làm giả hoặc chỉnh sửa", res_tamper.get_json().get("error", ""))

        # Dọn dẹp
        for p in [corrupt_zip_path, malformed_xml_path, tampered_path]:
            if os.path.exists(p): os.remove(p)
        print("✔ [Priority 5] Thẩm định cấu trúc DOCX và từ chối phôi giả mạo thành công!")

    # =========================================================================
    # PRIORITY 6: XÁC THỰC GIẢNG VIÊN VÀ TẢI XUỐNG BẢN SAO LƯU DATABASE
    # =========================================================================
    def test_priority_6_teacher_auth_and_database_download(self):
        """[Priority 6] API tải xuống edudoc.db yêu cầu xác thực PIN và trả về tệp nhị phân SQLite"""
        # Không có PIN -> 401
        res_unauth = self.client.get("/api/teacher/database/download", headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_unauth.status_code, 401)

        # Có PIN gv2026 -> 200 và nội dung SQLite
        res_auth = self.client.get("/api/teacher/database/download", headers={"X-Teacher-PIN": "gv2026"})
        self.assertEqual(res_auth.status_code, 200)
        self.assertTrue(res_auth.data.startswith(b"SQLite format 3"))
        print("✔ [Priority 6] Xác thực Giảng viên và tải xuống backup SQLite thành công!")

if __name__ == "__main__":
    unittest.main()
