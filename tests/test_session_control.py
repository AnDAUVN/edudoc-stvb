# -*- coding: utf-8 -*-
"""
Kiểm thử tính năng Điều khiển Phòng học: Khóa làm bài khi Giảng viên đang giảng lý thuyết.
Chỉ khi nào Giảng viên cho phép mở phòng thì sinh viên mới được bắt đầu làm bài.
"""
import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import app, SESSION_STATE_FILE, save_json_file, load_json_file

class TestSessionControl(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        # Lưu lại state ban đầu
        self.original_state = load_json_file(SESSION_STATE_FILE, {"is_open": False})

    def tearDown(self):
        # Khôi phục state
        save_json_file(SESSION_STATE_FILE, self.original_state)

    def test_session_state_api(self):
        """API /api/session-state trả về đúng trạng thái và thông điệp"""
        res = self.client.get("/api/session-state")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("is_open", data)
        self.assertIn("message", data)

    def test_teacher_toggle_session(self):
        """Giảng viên có thể bật / tắt trạng thái làm bài"""
        # 1. Bật cho phép làm bài
        res = self.client.post("/api/teacher/session-state", json={"is_open": True})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["session_state"]["is_open"])
        self.assertIn("Đã mở quyền làm bài", data["message"])

        # 2. Khóa lại để giảng bài tiếp
        res2 = self.client.post("/api/teacher/session-state", json={"is_open": False})
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertFalse(data2["session_state"]["is_open"])
        self.assertIn("Đã khóa hệ thống", data2["message"])

    def test_locked_session_blocks_student_actions(self):
        """Khi đang khóa (is_open=False), sinh viên không thể làm bài hoặc nộp bài"""
        # Tắt cờ testing tạm thời để kiểm thử chức năng bảo vệ
        save_json_file(SESSION_STATE_FILE, {"is_open": False, "message": "Đang giảng lý thuyết"})
        
        # Gọi thử với header hoặc tạm gỡ EDUDOC_TESTING
        old_env = os.environ.get("EDUDOC_TESTING")
        if "EDUDOC_TESTING" in os.environ:
            del os.environ["EDUDOC_TESTING"]
            
        app.testing = False
        try:
            # Thử lấy câu hỏi trắc nghiệm
            res_quiz = self.client.post("/api/quiz/get", json={"doc_type": "cong_van_de_nghi"})
            self.assertEqual(res_quiz.status_code, 403)
            self.assertTrue(res_quiz.get_json().get("is_locked"))

            # Thử sinh file bài tập
            res_gen = self.client.post("/api/template/generate", json={"sbd": "01", "mssv": "123", "name": "Test", "doc_type": "cong_van_de_nghi"})
            self.assertEqual(res_gen.status_code, 403)

            # Thử nộp bài
            res_sub = self.client.post("/api/submit", json={"sbd": "01", "mssv": "123", "name": "Test", "doc_type": "cong_van_de_nghi", "temp_file": "x.docx"})
            self.assertEqual(res_sub.status_code, 403)
        finally:
            app.testing = True
            if old_env:
                os.environ["EDUDOC_TESTING"] = old_env

    def test_unlocked_session_allows_student_actions(self):
        """Khi Giảng viên mở khóa (is_open=True), sinh viên vào làm bài bình thường"""
        save_json_file(SESSION_STATE_FILE, {"is_open": True, "message": "Đang mở làm bài"})
        res_quiz = self.client.post("/api/quiz/get", json={"doc_type": "cong_van_de_nghi"})
        self.assertEqual(res_quiz.status_code, 200)
        self.assertIn("questions", res_quiz.get_json())

if __name__ == "__main__":
    unittest.main()
