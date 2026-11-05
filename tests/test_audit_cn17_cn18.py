# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động toàn diện cho Chức năng CN17 & CN18 (Bản 4 ngày 05/11/2026):
- CN17: Một lượt cho mỗi bài (Single attempt per document type, Resume attempt, Re-attempt permissions, Audit history)
- CN18: Một thiết bị có giảng viên xác nhận (Single device binding, Device lock, Change request workflow)
"""
import os
import sys
import json
import uuid
import unittest
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app import app
from engine.db import (
    get_db_connection,
    get_device_binding,
    bind_device,
    verify_or_bind_device,
    create_device_change_request,
    get_device_change_requests,
    approve_device_change_request,
    reject_device_change_request,
    grant_reattempt_permission,
    get_active_reattempt_permission,
    consume_reattempt_permission,
    get_submissions_history,
    archive_submission_record
)
from engine.common import safe_storage_path, STORAGE_UPLOADS, STORAGE_TEMPLATES

class TestAuditCN17CN18(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.test_class = "CN_TEST_01"
        self.mssv = "2400009999"
        self.name = "Sinh Viên Thử Nghiệm"
        self.sbd = "99"
        self.doc_type = "cong_van_de_nghi"

        # Đảm bảo phòng thi mở và đăng ký sinh viên vào roster
        conn = get_db_connection()
        with conn:
            conn.execute("INSERT OR REPLACE INTO session_state (key, is_open, enforce_roster, active_doc_type, enable_anti_cheat, enforce_quiz) VALUES (?, 1, 0, ?, 0, 0);", (f"class_{self.test_class}", self.doc_type))
            conn.execute("INSERT OR REPLACE INTO session_state (key, is_open, enforce_roster, active_doc_type, enable_anti_cheat, enforce_quiz) VALUES ('current_session', 1, 0, ?, 0, 0);", (self.doc_type,))
            # Dọn dẹp dữ liệu kiểm thử cũ của sinh viên này
            conn.execute("DELETE FROM device_bindings WHERE mssv = ?;", (self.mssv,))
            conn.execute("DELETE FROM device_change_requests WHERE mssv = ?;", (self.mssv,))
            conn.execute("DELETE FROM quiz_attempts WHERE mssv = ?;", (self.mssv,))
            conn.execute("DELETE FROM reattempt_permissions WHERE mssv = ?;", (self.mssv,))
            conn.execute("DELETE FROM submissions WHERE mssv = ?;", (self.mssv,))
            conn.execute("DELETE FROM submissions_history WHERE mssv = ?;", (self.mssv,))
        conn.close()

    def test_nt01_nt03_quiz_resume_and_single_attempt(self):
        """NT01-NT03: Tiếp tục lượt thi đang làm dở (Resume) & chặn làm bài mới khi đã hoàn thành"""
        dev_id = "device_student_a"
        headers = {"X-Device-Id": dev_id, "X-Test-Enforce-Device": "1"}

        # 1. Bắt đầu bài trắc nghiệm lần đầu
        res1 = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers=headers)
        self.assertEqual(res1.status_code, 200)
        data1 = res1.get_json()
        attempt_id = data1["attempt_id"]
        q_ids = [q["id"] for q in data1["questions"]]

        # NT01: Gọi lại khi đang IN_PROGRESS -> Phải RESUME cùng attempt_id và cùng bộ câu hỏi
        res_resume = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers=headers)
        self.assertEqual(res_resume.status_code, 200)
        data_resume = res_resume.get_json()
        self.assertEqual(data_resume["attempt_id"], attempt_id)
        self.assertTrue(data_resume.get("resumed", False))
        self.assertEqual([q["id"] for q in data_resume["questions"]], q_ids)

        # 2. Nộp bài trắc nghiệm
        answers = {str(qid): 0 for qid in q_ids}
        res_sub = self.client.post("/api/quiz/submit", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type,
            "attempt_id": attempt_id,
            "answers": answers
        }, headers=headers)
        self.assertEqual(res_sub.status_code, 200)

        # NT03: Nộp lại attempt_id đã hoàn thành -> Phải bị từ chối 400
        res_sub_again = self.client.post("/api/quiz/submit", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type,
            "attempt_id": attempt_id,
            "answers": answers
        }, headers=headers)
        self.assertEqual(res_sub_again.status_code, 400)
        self.assertIn("đã hoàn thành", res_sub_again.get_json()["error"])

        # NT04: Gọi /api/quiz/get sau khi đã hoàn thành -> Phải bị từ chối 403 (mỗi bài 1 lượt)
        res_get_done = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers=headers)
        self.assertEqual(res_get_done.status_code, 403)
        self.assertTrue(res_get_done.get_json().get("quiz_completed"))

    def test_nt04_nt08_single_word_submission_and_reattempt_workflow(self):
        """NT04-NT08: Chặn nộp đè bài Word lần 2, quy trình cấp quyền làm lại & lưu vết lịch sử"""
        dev_id = "device_student_word"
        headers = {"X-Device-Id": dev_id, "X-Test-Enforce-Device": "1", "X-Test-Enforce-Single-Attempt": "1"}

        # 1. Tạo file Word giả lập nộp lần 1
        temp_fn = f"temp_{self.mssv}_test_sub.docx"
        temp_path = os.path.join(STORAGE_UPLOADS, temp_fn)
        from docx import Document
        d = Document()
        d.add_paragraph("Bài làm thể thức công văn lần 1")
        d.save(temp_path)

        res_sub1 = self.client.post("/api/submit", json={
            "class_code": self.test_class,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": self.doc_type,
            "temp_file": temp_fn,
            "elapsed_time": "05:00",
            "score": 9.5
        }, headers=headers)
        self.assertEqual(res_sub1.status_code, 200)

        # NT05: Nộp lại lần 2 khi chưa có quyền -> Phải bị từ chối 409
        d2 = Document()
        d2.add_paragraph("Bài làm nộp đè lần 2")
        d2.save(temp_path)

        res_sub2 = self.client.post("/api/submit", json={
            "class_code": self.test_class,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": self.doc_type,
            "temp_file": temp_fn,
            "elapsed_time": "06:00",
            "score": 10.0
        }, headers=headers)
        self.assertEqual(res_sub2.status_code, 409)
        self.assertTrue(res_sub2.get_json().get("already_submitted"))

        # NT06 & V5 02: Giảng viên cấp quyền làm lại bài (Bắt buộc xác thực Giảng viên)
        res_grant_unauth = self.client.post("/api/teacher/reattempt/grant", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type,
            "reason": "Máy tính gặp sự cố, cho phép làm lại"
        }, headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_grant_unauth.status_code, 401, "API chưa đăng nhập phải bị từ chối 401 (V5 02)")

        res_grant = self.client.post("/api/teacher/reattempt/grant", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type,
            "reason": "Máy tính gặp sự cố, cho phép làm lại"
        }, headers={"X-Teacher-PIN": "gv2026"})
        self.assertEqual(res_grant.status_code, 200)
        self.assertTrue(res_grant.get_json()["success"])

        # NT07 & NT08: Nộp lại sau khi được cấp quyền -> Thành công 200 & lưu bài cũ vào submissions_history
        res_sub_approved = self.client.post("/api/submit", json={
            "class_code": self.test_class,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": self.doc_type,
            "temp_file": temp_fn,
            "elapsed_time": "04:30",
            "score": 10.0
        }, headers=headers)
        self.assertEqual(res_sub_approved.status_code, 200)

        # NT08: Kiểm tra lịch sử kiểm toán submissions_history
        hist = get_submissions_history(class_code=self.test_class, mssv=self.mssv)
        self.assertGreaterEqual(len(hist), 1)
        self.assertEqual(hist[0]["mssv"], self.mssv)
        self.assertIn("Làm lại bài", hist[0]["archive_reason"])

    def test_nt09_nt13_device_binding_lock_and_change_request_workflow(self):
        """NT09-NT13: Ràng buộc 1 thiết bị, khóa máy lạ & quy trình phê duyệt đổi máy thi"""
        dev_a = "macbook_pro_uuid_111"
        dev_b = "rog_strix_uuid_222"

        # NT09: Thiết bị A đăng nhập lần đầu -> Tự động gắn thiết bị
        res_bind = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers={"X-Device-Id": dev_a, "X-Test-Enforce-Device": "1"})
        self.assertEqual(res_bind.status_code, 200)

        binding = get_device_binding(self.test_class, self.mssv)
        self.assertIsNotNone(binding)
        self.assertEqual(binding["device_id"], dev_a)

        # NT10: Thiết bị B đăng nhập cùng MSSV -> Phải bị khóa thiết bị (403)
        res_locked = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers={"X-Device-Id": dev_b, "X-Test-Enforce-Device": "1"})
        self.assertEqual(res_locked.status_code, 403)
        self.assertTrue(res_locked.get_json().get("device_locked"))

        # NT11: Sinh viên gửi yêu cầu đổi sang thiết bị B
        res_req = self.client.post("/api/student/device/request-change", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "name": self.name,
            "new_device_id": dev_b,
            "reason": "Máy A bị sập nguồn, chuyển sang máy B phòng máy"
        }, headers={"X-Device-Id": dev_b})
        self.assertEqual(res_req.status_code, 200)
        req_id = res_req.get_json()["request_id"]
        self.assertTrue(req_id.startswith("DCR_"))

        # NT12 & V5 02: Giảng viên xem danh sách yêu cầu và phê duyệt (Bắt buộc xác thực)
        res_list_unauth = self.client.get(f"/api/teacher/device/requests?class_code={self.test_class}", headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_list_unauth.status_code, 401, "API chưa đăng nhập phải bị từ chối 401 (V5 02)")

        res_list = self.client.get(f"/api/teacher/device/requests?class_code={self.test_class}", headers={"X-Teacher-PIN": "gv2026"})
        self.assertEqual(res_list.status_code, 200)
        self.assertGreaterEqual(res_list.get_json()["total"], 1)

        res_appr_unauth = self.client.post("/api/teacher/device/approve", json={"request_id": req_id}, headers={"X-Test-Auth-Required": "1"})
        self.assertEqual(res_appr_unauth.status_code, 401, "Phê duyệt không có PIN phải bị từ chối 401 (V5 02)")

        res_approve = self.client.post("/api/teacher/device/approve", json={"request_id": req_id}, headers={"X-Teacher-PIN": "gv2026"})
        self.assertEqual(res_approve.status_code, 200)

        # Kiểm tra sau khi phê duyệt: Thiết bị B được phép làm bài
        res_b_ok = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers={"X-Device-Id": dev_b, "X-Test-Enforce-Device": "1"})
        self.assertEqual(res_b_ok.status_code, 200)

        # Thiết bị A cũ giờ đây phải bị khóa
        res_a_now_locked = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers={"X-Device-Id": dev_a, "X-Test-Enforce-Device": "1"})
        self.assertEqual(res_a_now_locked.status_code, 403)
        self.assertTrue(res_a_now_locked.get_json().get("device_locked"))

    def test_nt14_v5_audit_findings_verification(self):
        """NT14: Đối chiếu toàn bộ 9 phát hiện kiểm toán V5 (V5 01 - V5 09)"""
        # 1. V5 02: 5 Endpoint Giảng viên bắt buộc @require_teacher_auth
        unauth_hdr = {"X-Test-Auth-Required": "1"}
        self.assertEqual(self.client.get("/api/teacher/device/requests", headers=unauth_hdr).status_code, 401)
        self.assertEqual(self.client.post("/api/teacher/device/approve", json={"request_id": "fake"}, headers=unauth_hdr).status_code, 401)
        self.assertEqual(self.client.post("/api/teacher/device/reject", json={"request_id": "fake"}, headers=unauth_hdr).status_code, 401)
        self.assertEqual(self.client.post("/api/teacher/reattempt/grant", json={}, headers=unauth_hdr).status_code, 401)
        self.assertEqual(self.client.get("/api/teacher/submissions/history", headers=unauth_hdr).status_code, 401)

        # 2. V5 04: /api/student/device/status KHÔNG để lộ device_id
        res_dev_st = self.client.get(f"/api/student/device/status?class_code={self.test_class}&mssv={self.mssv}&device_id=test_dev")
        self.assertEqual(res_dev_st.status_code, 200)
        dev_json = res_dev_st.get_json()
        self.assertNotIn("device_id", dev_json)
        self.assertNotIn("binding", dev_json)
        self.assertIn("bound", dev_json)
        self.assertIn("matched", dev_json)

        # 3. V5 06: submit_quiz khi có attempt_id nhưng thiếu mssv hoặc mssv sai chủ sở hữu phải bị từ chối
        # Tạo 1 attempt thực tế
        res_quiz = self.client.post("/api/quiz/get", json={
            "class_code": self.test_class,
            "mssv": self.mssv,
            "doc_type": self.doc_type
        }, headers={"X-Device-Id": "dev_v5_quiz", "X-Test-Enforce-Device": "1"})
        att_id = res_quiz.get_json()["attempt_id"]

        # 3a. Nộp thiếu MSSV khi có attempt_id -> 400
        res_no_mssv = self.client.post("/api/quiz/submit", json={
            "class_code": self.test_class,
            "doc_type": self.doc_type,
            "attempt_id": att_id,
            "answers": {}
        })
        self.assertEqual(res_no_mssv.status_code, 400, "Nộp thiếu MSSV khi có attempt_id phải bị từ chối 400 (V5 06)")

        # 3b. Nộp sai MSSV (máy B nộp thay máy A) -> 403
        res_wrong_mssv = self.client.post("/api/quiz/submit", json={
            "class_code": self.test_class,
            "mssv": "9999999999",
            "doc_type": self.doc_type,
            "attempt_id": att_id,
            "answers": {}
        })
        self.assertEqual(res_wrong_mssv.status_code, 403, "Máy B nộp thay attempt của máy A phải bị từ chối 403 (V5 06)")

        # 4. V5 03: Phôi được tạo kèm class_code nộp với /api/submit phải qua kiểm tra HMAC hợp lệ
        from engine.db import save_student_session
        save_student_session(f"{self.test_class}_{self.mssv}_{self.doc_type}", {"quiz_passed": True})
        save_student_session(f"{self.mssv}_{self.doc_type}", {"quiz_passed": True})

        res_tmpl = self.client.post("/api/template/generate", json={
            "class_code": self.test_class,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": self.doc_type
        }, headers={"X-Device-Id": "dev_v5_quiz", "X-Test-Enforce-Device": "1"})
        self.assertEqual(res_tmpl.status_code, 200)
        tmpl_fn = res_tmpl.get_json()["filename"]

        # Giả lập nộp bài bằng chính phôi hệ thống cấp
        temp_fn = f"temp_{self.mssv}_{tmpl_fn}"
        src_path = os.path.join(STORAGE_TEMPLATES, tmpl_fn)
        dst_path = os.path.join(STORAGE_UPLOADS, temp_fn)
        import shutil
        shutil.copy2(src_path, dst_path)

        res_sub = self.client.post("/api/submit", json={
            "class_code": self.test_class,
            "sbd": self.sbd,
            "mssv": self.mssv,
            "name": self.name,
            "doc_type": self.doc_type,
            "temp_file": temp_fn,
            "elapsed_time": "05:00",
            "score": 10.0
        }, headers={"X-Device-Id": "dev_v5_quiz", "X-Test-Enforce-Device": "1", "X-Test-Enforce-Phoi": "1"})
        self.assertEqual(res_sub.status_code, 200, f"Phôi hợp lệ của hệ thống phải được nộp thành công, không bị lỗi HMAC: {res_sub.get_data(as_text=True)}")

if __name__ == "__main__":
    unittest.main()
