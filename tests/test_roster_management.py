# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tính năng Quản lý Danh sách Sinh viên theo lớp (Roster Authentication).
Bảo vệ hệ thống khảo thí:
- Chỉ sinh viên có trong danh sách lớp mới được đăng nhập, làm bài, nhận file mẫu và nộp bài.
- Chặn tuyệt đối việc sinh viên chia sẻ link làm bài tràn lan hoặc người ngoài vào thi hộ.
- Giảng viên có thể thêm từng sinh viên, import hàng loạt từ Excel/Sheets, xóa sinh viên, bật/tắt chế độ khóa.
"""
import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import (
    app, STUDENTS_ROSTER_FILE, SESSION_STATE_FILE,
    load_json_file, save_json_file, parse_students_text,
    is_student_in_roster, get_student_from_roster
)

class TestRosterManagement(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Sao lưu trạng thái và roster
        self.original_roster = load_json_file(STUDENTS_ROSTER_FILE, {})
        self.original_state = load_json_file(SESSION_STATE_FILE, {"is_open": True, "enforce_roster": True})

    def tearDown(self):
        # Khôi phục dữ liệu gốc
        save_json_file(STUDENTS_ROSTER_FILE, self.original_roster)
        save_json_file(SESSION_STATE_FILE, self.original_state)

    def test_parse_students_text(self):
        """Kiểm tra thuật toán bóc tách danh sách từ Excel/Word/Sheets"""
        # 1. Định dạng 3 cột chuẩn tab từ Excel: SBD <tab> MSSV <tab> Họ tên
        text_tab = "01\t2100001234\tNguyễn Văn A\n02\t2100005555\tTrần Thị B"
        res_tab = parse_students_text(text_tab)
        self.assertEqual(len(res_tab), 2)
        self.assertEqual(res_tab[0]["sbd"], "01")
        self.assertEqual(res_tab[0]["mssv"], "2100001234")
        self.assertEqual(res_tab[0]["name"], "Nguyễn Văn A")

        # 2. Định dạng 2 cột: MSSV <tab> Họ tên
        text_2col = "2100009999\tLê Hoàng C\n2100008888\tPhạm Văn D"
        res_2col = parse_students_text(text_2col)
        self.assertEqual(len(res_2col), 2)
        self.assertEqual(res_2col[0]["mssv"], "2100009999")
        self.assertEqual(res_2col[0]["name"], "Lê Hoàng C")

        # 3. Định dạng gạch nối: MSSV - Họ tên
        text_hyphen = "2280601234 - Đặng Hoàng E\n2280605678 - Vũ Thị F"
        res_hyphen = parse_students_text(text_hyphen)
        self.assertEqual(len(res_hyphen), 2)
        self.assertEqual(res_hyphen[0]["mssv"], "2280601234")
        self.assertEqual(res_hyphen[0]["name"], "Đặng Hoàng E")

        # 4. Bỏ qua dòng trống và comment
        text_mixed = "# Danh sách sinh viên\n\n01\t2100001111\tNguyễn Văn 1\n   \n"
        res_mixed = parse_students_text(text_mixed)
        self.assertEqual(len(res_mixed), 1)

    def test_student_verify_api(self):
        """API /api/student/verify xác thực sinh viên có trong danh sách hay không"""
        # Chuẩn bị roster lớp TEST_CLS
        roster = {
            "TEST_CLS": [
                {"sbd": "01", "mssv": "2100009999", "name": "Sinh Viên Thử Nghiệm"}
            ]
        }
        save_json_file(STUDENTS_ROSTER_FILE, roster)
        save_json_file(SESSION_STATE_FILE, {"is_open": True, "enforce_roster": True})

        # 1. Sinh viên có trong danh sách
        res_valid = self.client.post("/api/student/verify", json={
            "class_code": "TEST_CLS",
            "mssv": "2100009999"
        })
        self.assertEqual(res_valid.status_code, 200)
        data_valid = res_valid.get_json()
        self.assertTrue(data_valid["valid"])
        self.assertEqual(data_valid["student"]["name"], "Sinh Viên Thử Nghiệm")

        # 2. Sinh viên KHÔNG có trong danh sách
        res_invalid = self.client.post("/api/student/verify", json={
            "class_code": "TEST_CLS",
            "mssv": "9999999999"
        })
        self.assertEqual(res_invalid.status_code, 403)
        data_invalid = res_invalid.get_json()
        self.assertFalse(data_invalid["valid"])

        # 3. Khi Giảng viên tắt enforce_roster (chế độ mở tự do)
        save_json_file(SESSION_STATE_FILE, {"is_open": True, "enforce_roster": False})
        res_free = self.client.post("/api/student/verify", json={
            "class_code": "TEST_CLS",
            "mssv": "9999999999"
        })
        data_free = res_free.get_json()
        self.assertTrue(data_free["valid"])
        self.assertFalse(data_free["enforce_roster"])

    def test_teacher_add_and_delete_student(self):
        """Giảng viên thêm sinh viên lẻ và xóa sinh viên khỏi lớp"""
        # Thêm sinh viên mới
        res_add = self.client.post("/api/teacher/students/add", json={
            "class_code": "TEST_ADD_CLS",
            "sbd": "10",
            "mssv": "2100007777",
            "name": "Trần Văn Thêm"
        })
        self.assertEqual(res_add.status_code, 200)
        data_add = res_add.get_json()
        self.assertTrue(data_add["success"])

        # Kiểm tra danh sách lớp
        res_list = self.client.get("/api/teacher/students?class_code=TEST_ADD_CLS")
        self.assertEqual(res_list.status_code, 200)
        data_list = res_list.get_json()
        self.assertEqual(len(data_list["students"]), 1)
        self.assertEqual(data_list["students"][0]["mssv"], "2100007777")

        # Xóa sinh viên
        res_del = self.client.post("/api/teacher/students/delete", json={
            "class_code": "TEST_ADD_CLS",
            "mssv": "2100007777"
        })
        self.assertEqual(res_del.status_code, 200)

        # Kiểm tra lại danh sách lớp đã trống
        res_list_after = self.client.get("/api/teacher/students?class_code=TEST_ADD_CLS")
        self.assertEqual(len(res_list_after.get_json()["students"]), 0)

    def test_teacher_import_and_clear_roster(self):
        """Giảng viên dán hàng loạt sinh viên từ Excel và làm trống danh sách"""
        paste_text = """
        01\t2100000001\tSinh Viên Một
        02\t2100000002\tSinh Viên Hai
        03\t2100000003\tSinh Viên Ba
        """
        res_import = self.client.post("/api/teacher/students/import", json={
            "class_code": "TEST_IMPORT_CLS",
            "raw_text": paste_text
        })
        self.assertEqual(res_import.status_code, 200)
        data_import = res_import.get_json()
        self.assertEqual(data_import["added_count"], 3)
        self.assertEqual(data_import["total"], 3)

        # Xóa toàn bộ danh sách lớp
        res_clear = self.client.post("/api/teacher/students/clear", json={
            "class_code": "TEST_IMPORT_CLS"
        })
        self.assertEqual(res_clear.status_code, 200)

        res_check = self.client.get("/api/teacher/students?class_code=TEST_IMPORT_CLS")
        self.assertEqual(len(res_check.get_json()["students"]), 0)

    def test_teacher_roster_toggle(self):
        """Giảng viên bật/tắt chế độ bắt buộc có tên trong danh sách"""
        res_off = self.client.post("/api/teacher/roster-toggle", json={"enforce_roster": False})
        self.assertEqual(res_off.status_code, 200)
        self.assertFalse(res_off.get_json()["enforce_roster"])

        res_on = self.client.post("/api/teacher/roster-toggle", json={"enforce_roster": True})
        self.assertEqual(res_on.status_code, 200)
        self.assertTrue(res_on.get_json()["enforce_roster"])

    def test_roster_blocking_unauthorized_students(self):
        """Khi enforce_roster=True, sinh viên ngoài danh sách bị chặn 403 ở các endpoint khảo thí"""
        roster = {
            "BLOCK_CLS": [
                {"sbd": "01", "mssv": "2100001234", "name": "Sinh Viên Hợp Lệ"}
            ]
        }
        save_json_file(STUDENTS_ROSTER_FILE, roster)
        save_json_file(SESSION_STATE_FILE, {"is_open": True, "enforce_roster": True})

        # Bật kiểm tra roster thực tế (bằng cách tạm vô hiệu cờ testing)
        app.testing = False
        old_env = os.environ.get("EDUDOC_TESTING")
        if "EDUDOC_TESTING" in os.environ:
            del os.environ["EDUDOC_TESTING"]

        try:
            # 1. Thử lấy đề trắc nghiệm với MSSV lạ -> Phải bị chặn 403
            res_quiz_blocked = self.client.post("/api/quiz/get", json={
                "class_code": "BLOCK_CLS",
                "mssv": "9999999999",
                "doc_type": "cong_van_de_nghi"
            })
            self.assertEqual(res_quiz_blocked.status_code, 403)
            data_q = res_quiz_blocked.get_json()
            self.assertTrue(data_q.get("not_in_roster"))

            # 2. Thử tạo file mẫu với MSSV lạ -> Phải bị chặn 403
            res_tmpl_blocked = self.client.post("/api/template/generate", json={
                "class_code": "BLOCK_CLS",
                "sbd": "99",
                "mssv": "9999999999",
                "name": "Người Ngoài",
                "doc_type": "cong_van_de_nghi"
            })
            self.assertEqual(res_tmpl_blocked.status_code, 403)

            # 3. Thử với MSSV hợp lệ có trong danh sách -> Được phép tạo đề (200)
            res_quiz_allowed = self.client.post("/api/quiz/get", json={
                "class_code": "BLOCK_CLS",
                "mssv": "2100001234",
                "doc_type": "cong_van_de_nghi"
            })
            self.assertEqual(res_quiz_allowed.status_code, 200)
        finally:
            app.testing = True
            if old_env is not None:
                os.environ["EDUDOC_TESTING"] = old_env

if __name__ == "__main__":
    unittest.main()
