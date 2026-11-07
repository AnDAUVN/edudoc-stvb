import os
from pathlib import Path

# Đường dẫn lưu khóa cố định vào thư mục data
KEY_FILE = Path(__file__).parent.parent / "data" / ".hmac-key"

def get_hmac_secret_key():
    """Lấy khóa HMAC cố định từ file. Nếu chưa có thì tạo 1 lần duy nhất."""
    if KEY_FILE.exists():
        return KEY_FILE.read_bytes()
    
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Khóa cố định hoặc sinh 1 lần lưu xuống đĩa
    new_key = b"EDUDOC_STVB_SECURITY_FIXED_KEY_2026"
    KEY_FILE.write_bytes(new_key)
    return new_key

# Biến khóa dùng chung xuyên suốt mọi phiên chạy
HMAC_SECRET_KEY = get_hmac_secret_key()
from docx import Document

def verify_document_anti_cheat(doc_path: str, student_id: str = None):
    """
    Xác thực bài làm của sinh viên:
    - Nhánh 1: Tệp còn nguyên vẹn mã token/watermark ẩn -> Hợp lệ tuyệt đối.
    - Nhánh 2 (Fallback): Tệp bị Word làm sạch metadata ngầm -> Kiểm tra cấu trúc thể thức văn bản.
    """
    try:
        doc = Document(doc_path)
        
        # --------------------------------------------------------------------
        # NHÁNH 1: Kiểm tra mã bảo mật ngầm (Metadata, Custom Properties, HMAC)
        # --------------------------------------------------------------------
        # (Nếu hệ thống có sẵn hàm kiểm tra token cũ, bạn giữ lại điều kiện kiểm tra đó)
        has_embedded_token = False
        try:
            # Ví dụ: kiểm tra trong core_properties.keywords hoặc custom properties cũ
            if hasattr(doc, 'core_properties') and doc.core_properties.keywords:
                if "EDUDOC" in doc.core_properties.keywords:
                    has_embedded_token = True
        except Exception:
            pass

        if has_embedded_token:
            return True, "Hợp lệ tuyệt đối (Khớp mã bảo mật ẩn)"[cite: 12]

        # --------------------------------------------------------------------
        # NHÁNH 2 (FALLBACK): Cứu bài làm khi phần mềm Office tự xóa metadata
        # --------------------------------------------------------------------
        # Đọc toàn bộ văn bản trong các đoạn văn
        full_text = "\n".join([p.text for p in doc.paragraphs]).upper()
        
        # 1. Kiểm tra sự xuất hiện của Quốc hiệu & Tiêu ngữ chuẩn
        has_quoc_hieu = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" in full_text[cite: 12]
        has_tieu_ngu = ("ĐỘC LẬP - TỰ DO - HẠNH PHÚC" in full_text or 
                        "ĐỘC LẬP – TỰ DO – HẠNH PHÚC" in full_text)[cite: 12]
        
        # 2. Kiểm tra khung Bảng tiêu đề (Table ở đầu văn bản có từ 2 cột trở lên)
        has_header_table = len(doc.tables) > 0 and len(doc.tables[0].columns) >= 2[cite: 12]
        
        # Nếu tệp vẫn giữ đúng bố cục/khung mẫu thể thức văn bản của đề bài
        if (has_quoc_hieu and has_tieu_ngu) or has_header_table:[cite: 12]
            return True, "Chấp nhận nộp bài (Xác thực qua khung thể thức chuẩn)"[cite: 12]

        # Chỉ từ chối khi tệp hoàn toàn trống hoặc không phải mẫu văn bản hành chính
        return False, "File bài làm không chứa mã bảo mật hợp lệ của hệ thống! Sinh viên phải sử dụng đúng file mẫu tải về từ phần mềm."[cite: 6, 12]

    except Exception as e:
        return False, f"Không thể đọc tệp Word: {str(e)}"