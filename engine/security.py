import hmac
import hashlib
import datetime
import re
from docx import Document
from docx.shared import Inches, Pt, RGBColor

SECRET_KEY = "STVB_NTTU_EDUCATIONAL_SECRET_2026"

ZERO_BIN_0 = '\u200b'  # Zero-width space -> bit 0
ZERO_BIN_1 = '\u200c'  # Zero-width non-joiner -> bit 1

def generate_anti_cheat_token(sbd, mssv, doc_type, timestamp):
    """Tạo chữ ký số bảo mật cho sinh viên"""
    message = f"{sbd}_{mssv}_{doc_type}_{timestamp}"
    token = hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()
    return token

def encode_hidden_mssv_to_text(text, mssv):
    """
    Cấy mã MSSV của sinh viên dưới dạng ký tự vô hình vào giữa nội dung văn bản
    """
    binary = ''.join(format(ord(c), '08b') for c in str(mssv))
    zero_width_str = binary.replace('0', ZERO_BIN_0).replace('1', ZERO_BIN_1)
    
    # Cấy vào sau từ đầu tiên
    words = text.split(' ', 1)
    if len(words) >= 2:
        return words[0] + zero_width_str + ' ' + words[1]
    return text + zero_width_str

def extract_all_hidden_mssvs(text):
    """
    Trích xuất và giải mã toàn bộ các thủy ấn số vô hình có trong văn bản
    """
    pattern = f"[{ZERO_BIN_0}{ZERO_BIN_1}]{{16,}}"
    matches = re.findall(pattern, text)
    if not matches:
        return []
    
    found_mssvs = []
    for candidate in matches:
        raw_binary = candidate.replace(ZERO_BIN_0, '0').replace(ZERO_BIN_1, '1')
        chars = []
        for i in range(0, len(raw_binary), 8):
            byte = raw_binary[i:i+8]
            if len(byte) == 8:
                try:
                    val = int(byte, 2)
                    if 32 <= val <= 126:  # Ký tự ASCII in được
                        chars.append(chr(val))
                    else:
                        break
                except:
                    break
        decoded = ''.join(chars)
        if len(decoded) >= 4 and any(c.isdigit() for c in decoded):
            if decoded not in found_mssvs:
                found_mssvs.append(decoded)
            
    return found_mssvs

def create_student_raw_template(sbd, mssv, student_name, doc_type_id, raw_text, output_path):
    """
    Khởi tạo file docx thô:
    - Chưa căn lề Nghị định 30 (để lề mặc định 1 inch)
    - Chưa chỉnh font Times New Roman (để Calibri 11pt, đen, không đậm/nghiêng)
    - Cấy mã token bảo mật và thủy ấn số MSSV
    """
    doc = Document()
    
    # 1. Để lề mặc định 1 inch (2.54 cm) - Sinh viên bắt buộc phải tự chỉnh sang NĐ 30
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        
    # 2. Tạo Token bảo mật & Ghi vào Metadata ẩn của file Word
    now_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    token = generate_anti_cheat_token(sbd, mssv, doc_type_id, now_str)
    
    core_props = doc.core_properties
    core_props.identifier = f"STVB_SIGNATURE:{token}"
    core_props.keywords = f"{sbd}|{mssv}|{student_name}|{doc_type_id}|{now_str}"
    core_props.author = f"STVB Educational System - NTTU"
    core_props.comments = f"Bai tap STVB - Sinh vien: {student_name} - MSSV: {mssv}"
    
    # 3. Ghi nội dung thô kèm thủy ấn vô hình
    lines = raw_text.strip().split("\n")
    for idx, line in enumerate(lines):
        line_to_write = line
        # Cấy thủy ấn vô hình vào dòng tiêu ngữ / cơ quan ban hành / nơi nhận và thân bài
        # Đảm bảo dù phần thân bài để trống hay tự gõ, mã định danh chống gian lận vẫn hiện diện 100%
        line_lower = line.lower()
        if (idx in [1, 3] or "tiêu ngữ" in line_lower or "quốc hiệu" in line_lower 
            or "cơ quan ban hành" in line_lower or "nơi nhận" in line_lower
            or "căn cứ" in line_lower or "thực hiện" in line_lower or "nhằm" in line_lower):
            line_to_write = encode_hidden_mssv_to_text(line, mssv)
            
        p = doc.add_paragraph()
        run = p.add_run(line_to_write)
        run.font.name = "Calibri"
        run.font.size = Pt(11)
        run.font.bold = False
        run.font.italic = False
        run.font.color.rgb = RGBColor(0, 0, 0)
        
        # Chưa căn lề Justify, không thụt đầu dòng
        p.paragraph_format.first_line_indent = Inches(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0

    doc.save(output_path)
    return token

def check_anti_cheat(docx_path, current_sbd, current_mssv, current_name, students_db=None):
    """
    Kiểm tra gian lận:
    - Chiêu 1: SV A nộp nguyên file của SV B (Đổi tên file)
    - Chiêu 2: SV A mở file mình nhưng Copy-Paste nội dung từ file của SV B
    """
    try:
        doc = Document(docx_path)
        core_props = doc.core_properties
        
        # KIỂM TRA 1: METADATA & TOKEN
        token_header = getattr(core_props, "identifier", "") or ""
        keywords = getattr(core_props, "keywords", "") or ""
        
        if not token_header.startswith("STVB_SIGNATURE:") or not keywords:
            return {
                "is_fraud": True,
                "fraud_type": "FILE_KHONG_HOP_LE",
                "message": "File bài làm không chứa mã bảo mật hợp lệ của hệ thống! Sinh viên phải sử dụng đúng file mẫu tải về từ phần mềm."
            }
            
        parts = keywords.split("|")
        if len(parts) >= 5:
            orig_sbd, orig_mssv, orig_name, orig_doc_type, timestamp = parts[0], parts[1], parts[2], parts[3], parts[4]
            
            # Nếu MSSV trong file không khớp với MSSV người đang đăng nhập nộp bài
            if str(orig_mssv).strip() != str(current_mssv).strip():
                return {
                    "is_fraud": True,
                    "fraud_type": "NOP_NGUYEN_FILE_BAN",
                    "student_a": {
                        "sbd": current_sbd,
                        "mssv": current_mssv,
                        "name": current_name
                    },
                    "student_b": {
                        "sbd": orig_sbd,
                        "mssv": orig_mssv,
                        "name": orig_name
                    },
                    "evidence": f"Sinh viên A ({current_name} - MSSV: {current_mssv}) đã lấy nguyên file gốc được cấp phát cho Sinh viên B ({orig_name} - MSSV: {orig_mssv}) để nộp."
                }
                
        # KIỂM TRA 2: THỦY ẤN VÔ HÌNH TRONG VĂN BẢN (COPY - PASTE NỘI DUNG)
        full_text = "\n".join([p.text for p in doc.paragraphs])
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text += "\n" + cell.text
                    
        all_found_mssvs = extract_all_hidden_mssvs(full_text)
        
        # Tìm xem có MSSV nào khác MSSV của sinh viên hiện tại hay không
        stolen_mssvs = [m for m in all_found_mssvs if str(m).strip() != str(current_mssv).strip()]
        
        if stolen_mssvs:
            target_b_mssv = stolen_mssvs[0]
            # Tra cứu thông tin sinh viên B theo MSSV từ Database nếu có
            student_b_name = "Sinh viên lớp (MSSV: " + str(target_b_mssv) + ")"
            if students_db and str(target_b_mssv) in students_db:
                student_b_name = students_db[str(target_b_mssv)].get("name", student_b_name)
                
            return {
                "is_fraud": True,
                "fraud_type": "COPY_PASTE_NOI_DUNG",
                "student_a": {
                    "sbd": current_sbd,
                    "mssv": current_mssv,
                    "name": current_name
                },
                "student_b": {
                    "mssv": target_b_mssv,
                    "name": student_b_name
                },
                "evidence": f"Sinh viên A ({current_name} - MSSV: {current_mssv}) đã copy-paste nội dung bài làm từ file của Sinh viên B (MSSV: {target_b_mssv}). Thủy ấn số bí mật của Sinh viên B đã bị phát hiện trong nội dung văn bản."
            }

        return {"is_fraud": False, "message": "File chính chủ và bảo mật hợp lệ."}

    except Exception as e:
        return {
            "is_fraud": True,
            "fraud_type": "ERROR_READING_FILE",
            "message": f"Không thể đọc file: {str(e)}"
        }
