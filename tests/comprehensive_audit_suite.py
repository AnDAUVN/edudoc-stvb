import requests
import json
import os
import shutil
import io
import csv
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

BASE_URL = "http://127.0.0.1:5000"

def run_comprehensive_audit():
    print("=" * 70)
    print("     BẮT ĐẦU KIỂM TRA TOÀN DIỆN PHẦN MỀM EDUDOC - NGHỊ ĐỊNH 30")
    print("=" * 70)

    # ---------------------------------------------------------
    # TEST 1: KIỂM TRA DANH SÁCH 8 LOẠI VĂN BẢN VÀ NGÂN HÀNG CÂU HỎI
    # ---------------------------------------------------------
    print("\n--- [TEST 1] RÀ SOÁT DỮ LIỆU ĐỀ BÀI & CÂU HỎI TRẮC NGHIỆM ---")
    res_docs = requests.get(f"{BASE_URL}/api/documents")
    assert res_docs.status_code == 200, "Lỗi lấy danh sách văn bản"
    docs = res_docs.json()
    assert len(docs) == 8, f"Mong muốn có 8 loại văn bản, có: {len(docs)}"
    print(f" [+] Đã tải thành công 8 loại văn bản bài tập:")
    for d in docs:
        print(f"     - {d['id']}: {d['name']} ({d['category']})")

    # Kiểm tra mỗi loại văn bản đều có câu hỏi trắc nghiệm
    for d in docs:
        q_res = requests.post(f"{BASE_URL}/api/quiz/get", json={"doc_type": d["id"]})
        assert q_res.status_code == 200
        q_data = q_res.json()
        assert q_data["total"] >= 5, f"Loại {d['id']} có ít hơn 5 câu hỏi: {q_data['total']}"
        assert q_data["pass_score"] >= 4, f"Pass score không hợp lệ: {q_data['pass_score']}"
        print(f"     ✔ {d['id']}: {q_data['total']} câu hỏi, điểm đạt: {q_data['pass_score']}/{q_data['total']}")

    # ---------------------------------------------------------
    # TEST 2: KIỂM TRA CHỨC NĂNG QUẢN LÝ MÃ LỚP KN CỦA GIẢNG VIÊN
    # ---------------------------------------------------------
    print("\n--- [TEST 2] KIỂM TRA CHỨC NĂNG QUẢN LÝ MÃ LỚP KN ---")
    test_class = "TEST_KN99"
    # Thêm lớp mới
    add_c = requests.post(f"{BASE_URL}/api/classes/add", json={"class_code": test_class})
    assert add_c.status_code == 200
    assert test_class in add_c.json()["classes"]
    print(f" [+] Thêm thành công mã lớp mới: '{test_class}'")

    # Lấy danh sách lớp
    get_c = requests.get(f"{BASE_URL}/api/classes")
    assert test_class in get_c.json()["classes"]
    print(f" [+] Danh sách lớp hiện tại có: {get_c.json()['classes']}")

    # Xóa lớp vừa thêm
    del_c = requests.post(f"{BASE_URL}/api/classes/delete", json={"class_code": test_class})
    assert del_c.status_code == 200
    assert test_class not in del_c.json()["classes"]
    print(f" [+] Xóa thành công mã lớp test: '{test_class}'")

    # ---------------------------------------------------------
    # TEST 3: QUẢN LÝ CÂU HỎI TRẮC NGHIỆM TỪ PHÍA GIẢNG VIÊN (CRUD)
    # ---------------------------------------------------------
    print("\n--- [TEST 3] KIỂM TRA THÊM - SỬA - XÓA CÂU HỎI TRẮC NGHIỆM ---")
    doc_type_test = "cong_van_de_nghi"
    new_q_payload = {
        "doc_type": doc_type_test,
        "question": "Câu hỏi kiểm tra tự động do hệ thống tạo",
        "options": ["Phương án A", "Phương án B", "Phương án C", "Phương án D"],
        "correct": 1,
        "explanation": "Phương án B là đáp án chính xác theo Nghị định 30."
    }
    save_q_res = requests.post(f"{BASE_URL}/api/teacher/quiz/save", json=new_q_payload)
    assert save_q_res.status_code == 200
    q_list = save_q_res.json()["questions"]
    created_q = next((q for q in q_list if q["question"] == new_q_payload["question"]), None)
    assert created_q is not None, "Không tìm thấy câu hỏi vừa tạo"
    created_q_id = created_q["id"]
    print(f" [+] Đã thêm mới thành công câu hỏi (ID: {created_q_id})")

    # Sửa câu hỏi
    edit_payload = {
        "doc_type": doc_type_test,
        "id": created_q_id,
        "question": "Câu hỏi kiểm tra tự động ĐÃ ĐƯỢC CHỈNH SỬA",
        "options": ["Phương án A mới", "Phương án B mới", "Phương án C mới", "Phương án D mới"],
        "correct": 2,
        "explanation": "Giải thích đã được cập nhật."
    }
    edit_res = requests.post(f"{BASE_URL}/api/teacher/quiz/save", json=edit_payload)
    assert edit_res.status_code == 200
    q_list_edited = edit_res.json()["questions"]
    edited_q = next((q for q in q_list_edited if q["id"] == created_q_id), None)
    assert edited_q["question"] == edit_payload["question"]
    print(f" [+] Đã chỉnh sửa thành công câu hỏi (ID: {created_q_id})")

    # Xóa câu hỏi
    del_q_res = requests.post(f"{BASE_URL}/api/teacher/quiz/delete", json={"doc_type": doc_type_test, "id": created_q_id})
    assert del_q_res.status_code == 200
    rem_list = del_q_res.json()["questions"]
    assert not any(q["id"] == created_q_id for q in rem_list)
    print(f" [+] Đã xóa thành công câu hỏi test (ID: {created_q_id})")

    # ---------------------------------------------------------
    # TEST 4: SINH FILE MẪU & TẢI VỀ CHO TẤT CẢ 8 LOẠI VĂN BẢN
    # ---------------------------------------------------------
    print("\n--- [TEST 4] KIỂM TRA TỰ ĐỘNG SINH FILE MẪU CHO CẢ 8 LOẠI VĂN BẢN ---")
    for d in docs:
        gen_res = requests.post(f"{BASE_URL}/api/template/generate", json={
            "class_code": "KN01",
            "sbd": "01",
            "mssv": "2280609999",
            "name": "Nguyễn Kiểm Tra",
            "doc_type": d["id"]
        })
        assert gen_res.status_code == 200, f"Sinh template thất bại cho {d['id']}"
        gen_data = gen_res.json()
        assert "filename" in gen_data
        assert "download_url" in gen_data
        
        # Test download endpoint
        dl_res = requests.get(f"{BASE_URL}{gen_data['download_url']}")
        assert dl_res.status_code == 200, f"Download failed for {gen_data['filename']}"
        assert len(dl_res.content) > 1000, "File rỗng hoặc quá nhỏ"
        print(f"     ✔ {d['id']}: Sinh file '{gen_data['filename']}' ({len(dl_res.content)} bytes) - OK")

    # ---------------------------------------------------------
    # TEST 5: KIỂM TRA BẢO MẬT & CHỐNG GIAN LẬN (ANTI-CHEAT)
    # ---------------------------------------------------------
    print("\n--- [TEST 5] KIỂM TRA HỆ THỐNG AN NINH & BẮT GIAN LẬN ---")
    # 1. File Word tự tạo bên ngoài (không qua hệ thống)
    ext_doc = Document()
    ext_doc.add_paragraph("Nội dung bài làm tùy tiện bên ngoài")
    ext_path = "temp_ext_unauth.docx"
    ext_doc.save(ext_path)

    with open(ext_path, "rb") as f:
        files = {"file": (ext_path, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        data = {
            "class_code": "KN01",
            "sbd": "01",
            "mssv": "2280609999",
            "name": "Nguyễn Kiểm Tra",
            "doc_type": "cong_van_de_nghi"
        }
        res_chk = requests.post(f"{BASE_URL}/api/validate", files=files, data=data)

    if os.path.exists(ext_path):
        os.remove(ext_path)

    assert res_chk.status_code == 200
    res_fraud = res_chk.json()
    assert res_fraud.get("status") == "FRAUD_DETECTED"
    assert res_fraud["fraud_info"]["fraud_type"] == "FILE_KHONG_HOP_LE"
    print(" [+] Chặn thành công file Word bên ngoài không có chữ ký số (FILE_KHONG_HOP_LE).")

    # ---------------------------------------------------------
    # TEST 6: XUẤT BẢNG ĐIỂM CSV & BỘ LỌC
    # ---------------------------------------------------------
    print("\n--- [TEST 6] KIỂM TRA XUẤT CSV & ĐẢM BẢO UTF-8 BOM CHO EXCEL ---")
    csv_res = requests.get(f"{BASE_URL}/api/teacher/export-csv?class_code=ALL")
    assert csv_res.status_code == 200
    csv_bytes = csv_res.content
    assert csv_bytes.startswith(b'\xef\xbb\xbf'), "CSV thiếu UTF-8 BOM để Excel hiển thị đúng tiếng Việt"
    csv_text = csv_bytes.decode('utf-8')
    assert "Mã lớp KN" in csv_text
    assert "Họ và tên" in csv_text
    print(" [+] Xuất file CSV thành công, có chuẩn UTF-8 BOM hiển thị tiếng Việt hoàn hảo trên Excel.")

    # ---------------------------------------------------------
    # TEST 7: QUẢN LÝ NHẬT KÝ GIAN LẬN & LỌC THEO MÃ LỚP
    # ---------------------------------------------------------
    print("\n--- [TEST 7] KIỂM TRA NHẬT KÝ THANH TRA VI PHẠM & CÔ LẬP LỚP ---")
    t_data_res = requests.get(f"{BASE_URL}/api/teacher/data")
    assert t_data_res.status_code == 200
    f_logs = t_data_res.json()["fraud_logs"]
    print(f" [+] Hiện có {len(f_logs)} biên bản vi phạm trong hệ thống.")
    if f_logs:
        sample_log_id = f_logs[0]["id"]
        # Xóa 1 log
        del_f_res = requests.post(f"{BASE_URL}/api/teacher/fraud/delete", json={"id": sample_log_id})
        assert del_f_res.status_code == 200
        print(f" [+] Xóa đơn lẻ thành công biên bản ID '{sample_log_id}'")

    # Xóa sạch nhật ký
    clr_res = requests.post(f"{BASE_URL}/api/teacher/fraud/clear", json={"class_code": "ALL"})
    assert clr_res.status_code == 200
    t_data_after = requests.get(f"{BASE_URL}/api/teacher/data").json()
    assert len(t_data_after["fraud_logs"]) == 0
    print(" [+] Xóa sạch toàn bộ nhật ký vi phạm thành công!")

    print("\n" + "=" * 70)
    print(" 🎉 TẤT CẢ 7 HẠNG MỤC KIỂM TRA TOÀN DIỆN ĐỀU ĐẠT 100% HOÀN HẢO!")
    print("=" * 70)

def ensure_server():
    import socket, subprocess, sys, time
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        if s.connect_ex(("127.0.0.1", 5000)) == 0:
            return None
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    proc = subprocess.Popen([sys.executable, "app.py"], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        time.sleep(0.5)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", 5000)) == 0:
                break
    return proc

if __name__ == "__main__":
    proc = ensure_server()
    try:
        run_comprehensive_audit()
    finally:
        if proc:
            proc.terminate()
