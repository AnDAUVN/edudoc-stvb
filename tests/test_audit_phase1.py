# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động dành cho ĐỢT 1: ĐIỂM SỐ, QUYỀN TRUY CẬP & BẢO MẬT (Phase 1 Audit)
Khắc phục triệt để các lỗ hổng:
- D01 (P0): Loại bỏ hoàn toàn điểm 10.0 mặc định khi có lỗi xử lý file; kiểm tra file docx hợp lệ
- D03 (P0): Chấm điểm trắc nghiệm đủ mẫu số (mặc định 5 câu), không cho phép gian lận nộp 1 câu đúng để đỗ
- D04 (P1): Chặn đề thi không tồn tại hoặc rỗng trong /api/quiz/submit
- D05 (P1): Ràng buộc danh tính sinh viên khi làm bài (is_student_in_roster từ chối khi thiếu MSSV/Lớp)
- D06 (P1): Ràng buộc phải vượt qua trắc nghiệm trước khi được cấp phôi bài tập
- D16 (P0): Chống nộp chéo tệp tạm giữa các sinh viên
- D20 (P0): Xác thực & phân quyền Giảng viên (PIN gv2026, session, header)
- D21 (P0): Chống tấn công thoát thư mục Path Traversal (../)
"""
import os
import sys
import json
import unittest
import zipfile
import io

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import (
    app, STUDENTS_ROSTER_FILE, SESSION_STATE_FILE,
    STORAGE_TEMPLATES, STORAGE_UPLOADS, STORAGE_SUBMITTED,
    load_json_file, save_json_file
)
from engine.common import (
    is_student_in_roster, sanitize_identifier, safe_storage_path, is_valid_docx
)
from engine.db import get_student_session, save_student_session

class TestAuditPhase1(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.original_roster = load_json_file(STUDENTS_ROSTER_FILE, {})
        self.original_state = load_json_file(SESSION_STATE_FILE, {"is_open": True, "enforce_roster": True})

        # Thiết lập dữ liệu lớp kiểm thử
        test_roster = {
            "PHASE1_CLS": [
                {"sbd": "01", "mssv": "2100001111", "name": "Sinh Viên A"},
                {"sbd": "02", "mssv": "2100002222", "name": "Sinh Viên B"}
            ]
        }
        save_json_file(STUDENTS_ROSTER_FILE, test_roster)
        save_json_file(SESSION_STATE_FILE, {
            "is_open": True,
            "enforce_roster": True,
            "enforce_quiz": True,
            "active_doc_type": "cong_van_de_nghi"
        })

    def tearDown(self):
        save_json_file(STUDENTS_ROSTER_FILE, self.original_roster)
        save_json_file(SESSION_STATE_FILE, self.original_state)

    # =========================================================================
    # D01: LOẠI BỎ ĐIỂM 10 MẶC ĐỊNH & KIỂM TRA FILE WORD HỢP LỆ
    # =========================================================================
    def test_d01_reject_corrupt_docx_on_validate_and_submit(self):
        """D01: Tệp giả mạo hoặc hỏng phải bị từ chối 400, không bao giờ được gán điểm 10.0"""
        corrupted_data = b"This is not a valid docx file content!"

        # 1. Thử gửi lên /api/validate
        res_val = self.client.post("/api/validate", data={
            "file": (io.BytesIO(corrupted_data), "corrupted.docx"),
            "class_code": "PHASE1_CLS",
            "sbd": "01",
            "mssv": "2100001111",
            "name": "Sinh Viên A",
            "doc_type": "cong_van_de_nghi"
        }, content_type="multipart/form-data")
        self.assertEqual(res_val.status_code, 400)
        self.assertIn("không phải là định dạng Word", res_val.get_json()["error"])

        # 2. Thử nộp tệp giả mạo lên /api/submit
        fake_temp_name = "temp_2100001111_fake_corrupt.docx"
        fake_temp_path = os.path.join(STORAGE_UPLOADS, fake_temp_name)
        with open(fake_temp_path, "wb") as f:
            f.write(corrupted_data)

        try:
            res_sub = self.client.post("/api/submit", json={
                "class_code": "PHASE1_CLS",
                "sbd": "01",
                "mssv": "2100001111",
                "name": "Sinh Viên A",
                "doc_type": "cong_van_de_nghi",
                "temp_file": fake_temp_name
            })
            self.assertEqual(res_sub.status_code, 400)
            self.assertIn("không phải là định dạng Word", res_sub.get_json()["error"])
        finally:
            if os.path.exists(fake_temp_path):
                os.remove(fake_temp_path)

    # =========================================================================
    # D03 & D04: CHẤM ĐIỂM TRẮC NGHIỆM ĐỦ MẪU SỐ & CHẶN ĐỀ KHÔNG TỒN TẠI
    # =========================================================================
    def test_d03_d04_quiz_scoring_and_invalid_doc_type(self):
        """D03: Không cho phép gửi 1 câu đúng để đỗ (mẫu số phải là 5 câu). D04: Chặn đề không tồn tại"""
        # 1. D04: Loại đề không tồn tại
        res_inv = self.client.post("/api/quiz/submit", json={
            "doc_type": "loai_de_khong_ton_tai_xyz",
            "answers": {"1": 0}
        })
        self.assertEqual(res_inv.status_code, 400)
        self.assertFalse(res_inv.get_json()["passed"])

        # 2. D03: Chỉ gửi 1 câu trả lời đúng cho đề công văn đề nghị
        # Bộ câu hỏi công văn có 5 câu hỏi; nếu chỉ gửi 1 câu thì total = 5, pass_score = 4, passed = False
        res_partial = self.client.post("/api/quiz/submit", json={
            "doc_type": "cong_van_de_nghi",
            "answers": {"1": 0},  # Giả định gửi 1 câu
            "mssv": "2100001111",
            "class_code": "PHASE1_CLS"
        })
        self.assertEqual(res_partial.status_code, 200)
        data_partial = res_partial.get_json()
        self.assertEqual(data_partial["total"], 5)
        self.assertEqual(data_partial["pass_score"], 4)
        self.assertFalse(data_partial["passed"])  # 1/5 không được phép đỗ!

    # =========================================================================
    # D05: RÀNG BUỘC DANH TÍNH KHI THI (ROSTER IDENTITY ENFORCEMENT)
    # =========================================================================
    def test_d05_roster_empty_params_rejected(self):
        """D05: is_student_in_roster từ chối khi class_code hoặc mssv rỗng"""
        # Khi enforce_roster = True, thiếu mssv hoặc class_code phải trả về False
        self.assertFalse(is_student_in_roster("", ""))
        self.assertFalse(is_student_in_roster("PHASE1_CLS", ""))
        self.assertFalse(is_student_in_roster("", "2100001111"))

        # Kiểm tra API /api/quiz/get với header kiểm tra roster
        res_no_id = self.client.post("/api/quiz/get", json={
            "doc_type": "cong_van_de_nghi"
        }, headers={"X-Test-Enforce-Roster": "1"})
        self.assertEqual(res_no_id.status_code, 400)

        res_wrong_id = self.client.post("/api/quiz/get", json={
            "class_code": "PHASE1_CLS",
            "mssv": "9999999999",
            "doc_type": "cong_van_de_nghi"
        }, headers={"X-Test-Enforce-Roster": "1"})
        self.assertEqual(res_wrong_id.status_code, 403)

    # =========================================================================
    # D06: RÀNG BUỘC PHẢI QUA TRẮC NGHIỆM TRƯỚC KHI CẤP PHÔI
    # =========================================================================
    def test_d06_template_requires_quiz_passed(self):
        """D06: Sinh viên chưa qua trắc nghiệm không được phép sinh phôi làm bài"""
        # Đảm bảo phiên làm bài của sinh viên chưa vượt qua trắc nghiệm
        save_student_session("2100001111_cong_van_de_nghi", {
            "quiz_passed": False,
            "preview_count": 0
        })

        # 1. Thử sinh phôi khi chưa làm trắc nghiệm
        res_blocked = self.client.post("/api/template/generate", json={
            "class_code": "PHASE1_CLS",
            "sbd": "01",
            "mssv": "2100001111",
            "name": "Sinh Viên A",
            "doc_type": "cong_van_de_nghi"
        }, headers={"X-Test-Enforce-Quiz": "1"})
        self.assertEqual(res_blocked.status_code, 403)
        self.assertTrue(res_blocked.get_json().get("quiz_required"))

        # 2. Sinh viên làm và đạt trắc nghiệm (ghi nhận quiz_passed = True)
        save_student_session("2100001111_cong_van_de_nghi", {
            "quiz_passed": True,
            "preview_count": 0
        })

        # 3. Thử sinh phôi lại -> Thành công 200
        res_allowed = self.client.post("/api/template/generate", json={
            "class_code": "PHASE1_CLS",
            "sbd": "01",
            "mssv": "2100001111",
            "name": "Sinh Viên A",
            "doc_type": "cong_van_de_nghi"
        }, headers={"X-Test-Enforce-Quiz": "1"})
        self.assertEqual(res_allowed.status_code, 200)
        self.assertTrue(res_allowed.get_json()["success"])

    # =========================================================================
    # D16: CHỐNG NỘP CHÉO TỆP TẠM CỦA SINH VIÊN KHÁC
    # =========================================================================
    def test_d16_cross_student_temp_file_blocked(self):
        """D16: Sinh viên B không thể nộp file tạm của sinh viên A"""
        # Tạo file tạm hợp lệ của sinh viên A
        temp_a_name = "temp_2100001111_test_file.docx"
        temp_a_path = os.path.join(STORAGE_UPLOADS, temp_a_name)
        
        # Tạo file docx zip tối thiểu
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("[Content_Types].xml", b"<Types/>")
            z.writestr("word/document.xml", b"<w:document/>")
        with open(temp_a_path, "wb") as f:
            f.write(buf.getvalue())

        try:
            # Sinh viên B (MSSV: 2100002222) cố tình gửi temp_file của sinh viên A
            res_cross = self.client.post("/api/submit", json={
                "class_code": "PHASE1_CLS",
                "sbd": "02",
                "mssv": "2100002222",
                "name": "Sinh Viên B",
                "doc_type": "cong_van_de_nghi",
                "temp_file": temp_a_name
            })
            self.assertEqual(res_cross.status_code, 403)
            self.assertIn("không thuộc về sinh viên này", res_cross.get_json()["error"])
        finally:
            if os.path.exists(temp_a_path):
                os.remove(temp_a_path)

    # =========================================================================
    # D20: XÁC THỰC VÀ PHÂN QUYỀN GIẢNG VIÊN (PIN / SESSION)
    # =========================================================================
    def test_d20_teacher_authentication(self):
        """D20: Toàn bộ API giảng viên yêu cầu xác thực PIN gv2026 hoặc session"""
        # 1. Truy cập khi chưa xác thực -> 401 Unauthorized
        res_unauth = self.client.get("/api/teacher/data", headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_unauth.status_code, 401)
        self.assertTrue(res_unauth.get_json().get("auth_required"))

        # 2. Truy cập với Header X-Teacher-PIN đúng (gv2026) -> 200 OK
        res_header = self.client.get("/api/teacher/data", headers={
            "X-Test-Auth-Required": "1",
            "X-Teacher-PIN": "gv2026"
        })
        self.assertEqual(res_header.status_code, 200)

        # 3. Đăng nhập qua API /api/teacher/auth với PIN sai -> 401
        res_bad_pin = self.client.post("/api/teacher/auth", json={"pin": "wrong_pin"})
        self.assertEqual(res_bad_pin.status_code, 401)

        # 4. Đăng nhập qua API /api/teacher/auth với PIN đúng -> 200 và cấp session
        res_login = self.client.post("/api/teacher/auth", json={"pin": "gv2026"})
        self.assertEqual(res_login.status_code, 200)
        self.assertTrue(res_login.get_json()["success"])

        # Truy cập tiếp theo tự động hợp lệ nhờ session cookie
        res_with_sess = self.client.get("/api/teacher/data", headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_with_sess.status_code, 200)

        # 5. Đăng xuất Giảng viên
        res_logout = self.client.post("/api/teacher/logout")
        self.assertEqual(res_logout.status_code, 200)

        # Truy cập sau khi đăng xuất lại bị chặn 401
        res_after_logout = self.client.get("/api/teacher/data", headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_after_logout.status_code, 401)

    # =========================================================================
    # D21: CHỐNG TẤN CÔNG THOÁT THƯ MỤC PATH TRAVERSAL (../)
    # =========================================================================
    def test_d21_path_traversal_prevention(self):
        """D21: Chặn đứng ký tự điều hướng thư mục ../ trong mọi tham số và đường dẫn"""
        # 1. Kiểm tra hàm sanitize_identifier
        self.assertEqual(sanitize_identifier("../../etc/passwd"), "etcpasswd")
        self.assertEqual(sanitize_identifier("..\\..\\windows\\system32"), "windowssystem32")
        self.assertEqual(sanitize_identifier("2100001234"), "2100001234")
        self.assertEqual(sanitize_identifier("bai_thu_hoach"), "bai_thu_hoach")

        # 2. Kiểm tra hàm safe_storage_path ngăn chặn thoát thư mục
        with self.assertRaises(ValueError):
            safe_storage_path(STORAGE_UPLOADS, "../../evil.txt")

        # 3. Kiểm tra API tải phôi chặn Path Traversal
        res_dl = self.client.get("/api/template/download/..%2f..%2fconfig.json")
        self.assertIn(res_dl.status_code, [400, 404])

if __name__ == "__main__":
    unittest.main()
