# -*- coding: utf-8 -*-
"""
Kiểm thử tự động chuyên sâu:
1. Cổng sinh viên (/thi) không có nút hoặc modal Bàn làm việc Giảng viên.
2. Ngân hàng câu hỏi trắc nghiệm có đầy đủ chức năng Sửa (Edit) và Thêm mới câu hỏi.
3. Hỗ trợ nhiều giảng viên: Chọn giảng viên phụ trách, thêm/sửa/xóa giảng viên, đồng bộ vào ca thi và bảng điểm Excel.
"""
import os
import sys
import json
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ["EDUDOC_TESTING"] = "1"

from app import app
from engine.common import (
    SESSION_STATE_FILE, TEACHERS_FILE, QUESTIONS_FILE,
    load_json_file, save_json_file, get_session_state, save_session_state,
    get_teachers_data, get_active_teacher, set_active_teacher
)

class TestTeacherSelectorAndQuizEdit(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.orig_state = get_session_state()
        self.orig_teachers = get_teachers_data()

    def tearDown(self):
        save_session_state(self.orig_state)
        save_json_file(TEACHERS_FILE, self.orig_teachers)

    def test_01_student_view_has_no_teacher_portal_button(self):
        """Bên cổng sinh viên (/thi và /) không có nút dẫn vào Bàn làm việc Giảng viên"""
        res = self.client.get("/thi")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Đảm bảo không có nút Bàn làm việc Giảng viên
        self.assertNotIn("Bàn làm việc Giảng viên (/quan-tri)", html)
        self.assertNotIn('href="/quan-tri"', html)
        self.assertNotIn("modal-quiz-editor", html)
        self.assertNotIn("modal-import-students", html)

        # Đảm bảo sinh viên vẫn có cẩm nang NĐ 30 và thấy tên GV phụ trách
        self.assertIn("modal-decree30-guide", html)
        self.assertIn("lbl-student-teacher-name", html)

    def test_02_teacher_portal_has_multi_teacher_selector_and_modals(self):
        """Bàn làm việc Giảng viên (/quan-tri) có bộ chọn Giảng viên và modal Sửa câu hỏi"""
        res = self.client.get("/quan-tri")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("sel-active-teacher", html)
        self.assertIn("lbl-card-active-teacher", html)
        self.assertIn("modal-manage-teachers", html)
        self.assertIn("modal-quiz-editor", html)
        self.assertIn("openEditQuestionModal", html)

    def test_03_quiz_edit_functionality(self):
        """Kiểm tra chức năng SỬA câu hỏi trong ngân hàng trắc nghiệm"""
        res_list = self.client.get("/api/teacher/quiz/cong_van_de_nghi")
        self.assertEqual(res_list.status_code, 200)
        questions = res_list.get_json()["questions"]
        self.assertGreater(len(questions), 0)

        target_q = questions[0]
        q_id = target_q["id"]
        orig_question = target_q["question"]
        new_text = orig_question + " [KIỂM THỬ SỬA CÂU HỎI]"

        # Gửi request SỬA câu hỏi
        res_save = self.client.post("/api/teacher/quiz/save", json={
            "doc_type": "cong_van_de_nghi",
            "id": q_id,
            "question": new_text,
            "options": ["Phương án A cập nhật", "Phương án B cập nhật", "Phương án C cập nhật", "Phương án D cập nhật"],
            "correct": 2,
            "explanation": "Giải thích chuẩn Nghị định 30 sau khi sửa."
        })
        self.assertEqual(res_save.status_code, 200)
        save_data = res_save.get_json()
        self.assertTrue(save_data["success"])

        # Xác thực câu hỏi đã cập nhật trong danh sách
        updated_q = [q for q in save_data["questions"] if q["id"] == q_id][0]
        self.assertEqual(updated_q["question"], new_text)
        self.assertEqual(updated_q["correct"], 2)
        self.assertEqual(updated_q["options"][2], "Phương án C cập nhật")

        # Khôi phục lại nội dung ban đầu
        self.client.post("/api/teacher/quiz/save", json={
            "doc_type": "cong_van_de_nghi",
            "id": q_id,
            "question": orig_question,
            "options": target_q["options"],
            "correct": target_q["correct"],
            "explanation": target_q.get("explanation", "")
        })

    def test_04_teacher_selection_and_management(self):
        """Kiểm tra chọn giảng viên đang làm việc, thêm mới và xóa giảng viên"""
        # 1. Lấy danh sách giảng viên
        res_get = self.client.get("/api/teacher/teachers")
        self.assertEqual(res_get.status_code, 200)
        data_t = res_get.get_json()
        teachers = data_t["teachers"]
        self.assertGreaterEqual(len(teachers), 1)

        # 2. Thêm một Giảng viên mới
        res_add = self.client.post("/api/teacher/teachers/save", json={
            "name": "ThS. Phạm Thị Dung",
            "title": "Phó Trưởng Bộ môn",
            "department": "Bộ môn Hành chính Văn phòng",
            "email": "dungpt@truong.edu.vn",
            "phone": "0988776655"
        })
        self.assertEqual(res_add.status_code, 200)
        new_teacher = res_add.get_json()["teacher"]
        new_id = new_teacher["id"]
        self.assertEqual(new_teacher["name"], "ThS. Phạm Thị Dung")

        # 3. Chọn giảng viên vừa thêm
        res_sel_new = self.client.post("/api/teacher/teachers/select", json={"id": new_id})
        self.assertEqual(res_sel_new.status_code, 200)
        self.assertEqual(res_sel_new.get_json()["active_teacher"]["name"], "ThS. Phạm Thị Dung")

        # Cổng sinh viên kiểm tra thấy đúng tên giảng viên vừa chọn
        res_state = self.client.get("/api/session-state")
        self.assertEqual(res_state.get_json().get("active_teacher"), "ThS. Phạm Thị Dung")

        # 4. Xuất CSV có tên giảng viên đang phụ trách
        res_csv = self.client.get("/api/teacher/export-csv")
        self.assertEqual(res_csv.status_code, 200)
        csv_text = res_csv.get_data(as_text=True)
        self.assertIn("ThS. Phạm Thị Dung", csv_text)

        # 5. Xóa giảng viên vừa thêm
        res_del = self.client.post("/api/teacher/teachers/delete", json={"id": new_id})
        self.assertEqual(res_del.status_code, 200)
        del_data = res_del.get_json()
        self.assertTrue(del_data["success"])
        self.assertNotIn(new_id, [t["id"] for t in del_data["teachers"]])

if __name__ == "__main__":
    unittest.main()
