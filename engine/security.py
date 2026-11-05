import os
import difflib
import hmac
import hashlib
import datetime
import re
import zipfile
from docx import Document
from docx.shared import Inches, Pt, RGBColor

SECRET_KEY = os.environ.get("EDUDOC_SECRET_KEY", "STVB_NTTU_EDUCATIONAL_SECRET_2026")

ZERO_BIN_0 = '\u200b'  # Zero-width space -> bit 0
ZERO_BIN_1 = '\u200c'  # Zero-width non-joiner -> bit 1

def generate_anti_cheat_token(sbd, mssv, doc_type, timestamp, class_code=""):
    """Tạo mã xác thực HMAC cho phôi bài tập sinh viên (D14)"""
    msg_parts = [str(sbd).strip(), str(mssv).strip(), str(doc_type).strip(), str(timestamp).strip()]
    if class_code:
        msg_parts.append(str(class_code).strip().upper())
    message = "_".join(msg_parts)
    return hmac.new(SECRET_KEY.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).hexdigest()

def verify_anti_cheat_token(token, sbd, mssv, doc_type, timestamp, class_code=""):
    """Xác minh mã HMAC bảo mật phôi bài bằng compare_digest (D14)"""
    if not token:
        return False
    t_clean = str(token).strip()
    if class_code:
        expected_with_class = generate_anti_cheat_token(sbd, mssv, doc_type, timestamp, class_code)
        if hmac.compare_digest(t_clean, expected_with_class):
            return True
    expected_legacy = generate_anti_cheat_token(sbd, mssv, doc_type, timestamp, "")
    return hmac.compare_digest(t_clean, expected_legacy)

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

def plant_watermark_in_line(line, mssv):
    """
    Cấy thủy ấn số MSSV vào dòng văn bản ở các vị trí chiến lược
    đảm bảo người dùng định dạng / cắt dán / xóa nhãn vẫn giữ nguyên thủy ấn.
    """
    binary = ''.join(format(ord(c), '08b') for c in str(mssv))
    zero_width_str = binary.replace('0', ZERO_BIN_0).replace('1', ZERO_BIN_1)
    
    res = line
    # Nếu là dòng hướng dẫn trong ngoặc vuông, cấy vào cuối dòng để không làm vỡ cụm từ kiểm thử
    if res.strip().startswith('['):
        return res + zero_width_str

    # 1. Cấy trực tiếp vào các từ khóa bất biến trong thể thức Nghị định 30
    anchors = [
        "CỘNG", "Độc", "Nơi", "Kính", "TRƯỜNG", "PHÒNG", 
        "ĐOÀN", "THÔNG", "TỜ", "ỦY BAN", "SỞ", "CÔNG TY"
    ]
    for anchor in anchors:
        if anchor in res and zero_width_str not in res:
            res = res.replace(anchor, anchor + zero_width_str, 1)
            
    # 2. Cấy thêm vào sau từ đầu tiên của dòng
    words = res.split(' ', 1)
    if len(words) >= 2 and zero_width_str not in words[0]:
        res = words[0] + zero_width_str + ' ' + words[1]
    elif zero_width_str not in res:
        res = res + zero_width_str
        
    return res

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

def create_student_raw_template(sbd, mssv, student_name, doc_type_id, raw_text, output_path, class_code=""):
    """
    Khởi tạo file docx thô:
    - Chưa căn lề Nghị định 30 (để lề mặc định 1 inch)
    - Chưa chỉnh font Times New Roman (để Calibri 11pt, đen, không đậm/nghiêng)
    - Cấy mã token bảo mật và thủy ấn số MSSV
    """
    doc = Document()
    
    # 1. Khổ giấy A4 chuẩn NĐ 30, để lề mặc định 1 inch (2.54 cm) - Sinh viên bắt buộc phải tự chỉnh lề sang NĐ 30
    for section in doc.sections:
        section.page_width = Inches(21.0 / 2.54)
        section.page_height = Inches(29.7 / 2.54)
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        
    # 2. Tạo Token bảo mật & Ghi vào Metadata ẩn của file Word
    now_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    token = generate_anti_cheat_token(sbd, mssv, doc_type_id, now_str, class_code)
    
    core_props = doc.core_properties
    core_props.identifier = f"STVB_SIGNATURE:{token}"
    kw_parts = [str(sbd), str(mssv), str(student_name), str(doc_type_id), str(now_str)]
    if class_code:
        kw_parts.append(str(class_code).strip().upper())
    core_props.keywords = "|".join(kw_parts)
    core_props.author = f"STVB Educational System - NTTU"
    core_props.comments = f"Bai tap STVB - Sinh vien: {student_name} - MSSV: {mssv}"
    
    # 3. Ghi nội dung thô kèm thủy ấn vô hình
    lines = raw_text.strip().split("\n")
    for idx, line in enumerate(lines):
        line_to_write = plant_watermark_in_line(line, mssv)
            
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


def compute_box6_similarity(text1: str, text2: str) -> float:
    """
    Tính độ tương đồng nội dung văn bản Ô 6:
    Kết hợp SequenceMatcher theo cấp độ từ (word-level) và N-gram overlap (cụm 3 từ).
    Trả về tỷ lệ % từ 0.0 đến 100.0
    """
    if not text1 or not text2:
        return 0.0

    # Làm sạch và tách từ (loại bỏ dấu câu, chuyển chữ thường)
    w1 = [w.strip(".,;:?!-()\"'“”‘’+*") for w in text1.lower().split() if len(w.strip(".,;:?!-()\"'“”‘’+*")) > 0]
    w2 = [w.strip(".,;:?!-()\"'“”‘’+*") for w in text2.lower().split() if len(w.strip(".,;:?!-()\"'“”‘’+*")) > 0]

    if not w1 or not w2:
        return 0.0

    seq = difflib.SequenceMatcher(None, w1, w2)
    seq_ratio = seq.ratio()

    if len(w1) >= 3 and len(w2) >= 3:
        ng1 = set(tuple(w1[i:i+3]) for i in range(len(w1)-2))
        ng2 = set(tuple(w2[i:i+3]) for i in range(len(w2)-2))
        ngram_overlap = len(ng1 & ng2) / max(len(ng1), len(ng2))
    else:
        ngram_overlap = seq_ratio

    final_score = max(seq_ratio, ngram_overlap)
    return round(final_score * 100, 1)

def extract_box6_from_docx(doc_or_path) -> str:
    """Trích xuất toàn bộ văn bản phần thân bài (Ô 6) từ cả đoạn văn và các ô bảng biểu (S04)"""
    if isinstance(doc_or_path, str):
        if not os.path.exists(doc_or_path):
            return ""
        doc = Document(doc_or_path)
    else:
        doc = doc_or_path

    paras = []
    in_kinh_gui = False

    def clean_box6_paragraph(p_text: str):
        nonlocal in_kinh_gui
        t = p_text.strip()
        if not t:
            in_kinh_gui = False
            return None

        t_clean = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', t).strip()
        if not t_clean:
            return None

        # Bỏ qua các dòng nhãn hướng dẫn trong phôi đề
        if t_clean.startswith('[') and t_clean.endswith(']'):
            return None
        if any(t_clean.lower().startswith(kw) for kw in [
            'cơ quan chủ quản', 'cơ quan ban hành', 'quốc hiệu', 'tiêu ngữ',
            'số ký hiệu', 'địa danh ngày tháng', 'trích yếu', 'tên loại'
        ]):
            return None

        if 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA' in t_clean or 'Độc lập - Tự do - Hạnh phúc' in t_clean:
            return None
        if re.match(r'^Số\s*:', t_clean, re.IGNORECASE) or t_clean.startswith('SỐ:'):
            return None
        if 'ngày' in t_clean.lower() and 'tháng' in t_clean.lower() and 'năm' in t_clean.lower() and len(t_clean) < 60:
            return None
        if t_clean.startswith(('V/v', 'v/v', 'Về việc', 'về việc')) and len(t_clean) < 80:
            return None

        # Bỏ qua Kính gửi
        if t_clean.lower().startswith('kính gửi'):
            in_kinh_gui = True
            return None

        if in_kinh_gui:
            if t_clean.startswith(('-', '–', '—', '+')) or t_clean.endswith(';') or t_clean.endswith('.'):
                if any(t_clean.startswith(kw) for kw in ['Hiện nay', 'Căn cứ', 'Thực hiện', 'Nhằm', 'Để ']):
                    in_kinh_gui = False
                else:
                    return None
            else:
                in_kinh_gui = False

        if t_clean.startswith('Nơi nhận') or t_clean.startswith('Lưu:') or t_clean == '- Như kính gửi;' or t_clean == '- Lưu: VT.':
            return None
        if any(kw in t_clean.upper() for kw in ['HIỆU TRƯỞNG', 'GIÁM ĐỐC', 'TRƯỞNG PHÒNG', 'TRƯỞNG KHOA', 'BÍ THƯ']):
            return None
        # Bỏ qua dòng họ tên người ký nếu là chuỗi ngắn 2-4 từ không dấu câu
        if len(t_clean.split()) in [2, 3, 4] and not any(punc in t_clean for punc in ['.', ',', ';', '!', '?', ':']):
            if t_clean in ['Trần Ái Cầm', 'Nguyễn Văn An', 'Lê Văn Bình', 'Nguyễn Hoàng Long', 'Nguyễn Văn A']:
                return None

        return t_clean

    # 1. Duyệt các đoạn văn bản chính ngoài bảng
    for p in doc.paragraphs:
        cleaned = clean_box6_paragraph(p.text)
        if cleaned:
            paras.append(cleaned)

    # 2. S04: Duyệt đệ quy nội dung các ô trong bảng và bảng lồng nhau (tránh bỏ sót khi SV đưa thân bài vào bảng)
    seen_cells = set()
    def traverse_table(tbl, depth=0):
        if depth > 5:
            return
        for row in tbl.rows:
            for cell in row.cells:
                cell_id = id(cell._tc)
                if cell_id in seen_cells:
                    continue
                seen_cells.add(cell_id)
                for p in cell.paragraphs:
                    cleaned = clean_box6_paragraph(p.text)
                    if cleaned and cleaned not in paras:
                        paras.append(cleaned)
                for nested_tbl in cell.tables:
                    traverse_table(nested_tbl, depth + 1)

    for table in doc.tables:
        traverse_table(table, 0)

    return '\n'.join(paras)

def check_box6_plagiarism(docx_path, current_sbd, current_mssv, current_name, doc_type=None, class_code=None, students_db=None):
    """
    Kiểm tra đạo văn Thân bài (Ô 6):
    - D23: Loại trừ boilerplate đề bài trước khi so khớp
    - D23: Chỉ áp dụng khi đề bài yêu cầu tự soạn thảo (is_body_blank hoặc bai_thu_hoach)
    - Đối chiếu trong cùng mã lớp học
    """
    try:
        curr_box6 = extract_box6_from_docx(docx_path)
        # D23: Loại bỏ các đoạn boilerplate hướng dẫn trước khi kiểm tra
        clean_curr_box6 = re.sub(r'\[Nội dung văn bản:[^\]]*\]', '', curr_box6).strip()
        words = [w for w in clean_curr_box6.split() if w]
        if len(words) < 15:
            return {"is_fraud": False, "box6_text": clean_curr_box6}

        from engine.common import DATA_DIR, load_json_file, STORAGE_UPLOADS, STORAGE_SUBMITTED
        from engine.db import get_all_box6_submissions, save_box6_submission

        templates_path = os.path.join(DATA_DIR, "document_templates.json")
        all_tmpls = load_json_file(templates_path, {})
        curr_tmpl = all_tmpls.get(doc_type, {})
        is_curr_blank = bool(curr_tmpl.get("is_body_blank", False)) or (doc_type == "bai_thu_hoach")

        # D23: Nếu đề bài có phần thân bài cố định do giảng viên giao,
        # sinh viên làm theo đề bài sẽ có nội dung giống nhau -> không tính là đạo văn
        if not is_curr_blank:
            return {"is_fraud": False, "box6_text": clean_curr_box6}

        # 1. Kiểm tra đối chiếu với các mẫu văn bản khác trong hệ thống
        for other_id, other_tmpl in all_tmpls.items():
            if other_id == doc_type:
                continue
            other_body = other_tmpl.get("body_part", "")
            if other_body and len(other_body.split()) >= 15:
                sim = compute_box6_similarity(clean_curr_box6, other_body)
                if sim >= 70.0:
                    return {
                        "is_fraud": True,
                        "fraud_type": "COPY_NOI_DUNG_BEN_NGOAI",
                        "reason": "Sao chép nội dung từ mẫu văn bản khác",
                        "student_a": {
                            "sbd": current_sbd,
                            "mssv": current_mssv,
                            "name": current_name,
                            "class_code": class_code or "Chung"
                        },
                        "similarity": sim,
                        "evidence": f"Sinh viên {current_name} (MSSV: {current_mssv}) đã copy nội dung Thân bài từ mẫu '{other_tmpl.get('name', other_id)}' dán vào bài làm! (Độ trùng lặp: {sim}%)"
                    }

        # 2. Kiểm tra đối chiếu với các bài làm của sinh viên khác trong SQLite box6_submissions
        other_submissions = get_all_box6_submissions(doc_type=doc_type, exclude_mssv=current_mssv, class_code=class_code)
        for other in other_submissions:
            other_text = other.get("box6_text", "")
            if not other_text:
                continue
            clean_other = re.sub(r'\[Nội dung văn bản:[^\]]*\]', '', other_text).strip()
            if len(clean_other.split()) < 15:
                continue
            sim = compute_box6_similarity(clean_curr_box6, clean_other)
            if sim >= 75.0:
                target_name = other.get("name") or f"Sinh viên (MSSV: {other['mssv']})"
                if students_db and str(other['mssv']) in students_db:
                    target_name = students_db[str(other['mssv'])].get("name", target_name)
                return {
                    "is_fraud": True,
                    "fraud_type": "COPY_PASTE_NOI_DUNG_O6",
                    "reason": "Sao chép nội dung Thân bài (Ô 6) từ bạn học",
                    "student_a": {
                        "sbd": current_sbd,
                        "mssv": current_mssv,
                        "name": current_name,
                        "class_code": class_code or "Chung"
                    },
                    "student_b": {
                        "mssv": other["mssv"],
                        "name": target_name,
                        "class_code": other.get("class_code", "")
                    },
                    "similarity": sim,
                    "evidence": f"Sinh viên A ({current_name} - MSSV: {current_mssv}) đã sao chép {sim}% nội dung Thân bài (Ô 6) từ bài làm của Sinh viên B ({target_name} - MSSV: {other['mssv']})."
                }

        # 3. Quét kiểm tra các file docx khác trong storage/uploads/ và storage/submitted/ (nếu cùng lớp)
        scan_dirs = [STORAGE_UPLOADS, STORAGE_SUBMITTED]
        for sdir in scan_dirs:
            if not os.path.exists(sdir):
                continue
            for fn in os.listdir(sdir):
                if not fn.endswith(".docx") or fn.startswith("~"):
                    continue
                # Bỏ qua chính file hiện tại của sinh viên này
                if str(current_mssv) in fn:
                    continue
                fn_class = "Chung"
                # P1: Tra cứu mã lớp chính xác từ CSDL submissions để tránh chia cắt nhầm lớp có dấu gạch dưới (VD: TEST_PHASE2_A)
                try:
                    from engine.db import get_db_connection
                    c_conn = get_db_connection()
                    db_row = c_conn.execute("SELECT class_code, mssv, name, doc_type FROM submissions WHERE filename = ? LIMIT 1;", (fn,)).fetchone()
                    c_conn.close()
                    if db_row and db_row["class_code"]:
                        fn_class = db_row["class_code"]
                    else:
                        fn_parts = fn.split("_")
                        if len(fn_parts) >= 4 and not fn.startswith("temp_"):
                            fn_class = fn_parts[0]
                except Exception:
                    fn_parts = fn.split("_")
                    if len(fn_parts) >= 4 and not fn.startswith("temp_"):
                        fn_class = fn_parts[0]

                # S11: Chỉ đối chiếu trong cùng phạm vi lớp học, không lẫn lộn giữa các lớp
                if class_code and class_code.upper() != "CHUNG" and fn_class != "Chung":
                    if fn_class.upper() != class_code.upper():
                        continue

                fpath = os.path.join(sdir, fn)
                try:
                    other_doc = Document(fpath)
                    props = other_doc.core_properties
                    kw = getattr(props, "keywords", "") or ""
                    kw_parts = kw.split("|")
                    if len(kw_parts) >= 4:
                        # Chỉ so sánh nếu cùng doc_type
                        if doc_type and kw_parts[3].strip() != str(doc_type).strip():
                            continue
                        other_mssv = kw_parts[1]
                        other_name = kw_parts[2]
                    else:
                        m_mssv = re.search(r'\b(\d{10})\b', fn)
                        other_mssv = m_mssv.group(1) if m_mssv else "Bạn cùng lớp"
                        other_name = f"Sinh viên (MSSV: {other_mssv})"

                    if str(other_mssv).strip() == str(current_mssv).strip():
                        continue

                    other_text = extract_box6_from_docx(other_doc)
                    clean_other_disk = re.sub(r'\[Nội dung văn bản:[^\]]*\]', '', other_text).strip()
                    if clean_other_disk and len(clean_other_disk.split()) >= 15:
                        sim = compute_box6_similarity(clean_curr_box6, clean_other_disk)
                        if sim >= 75.0:
                            save_box6_submission(other_mssv, other_name, fn_class, doc_type or "", clean_other_disk)
                            return {
                                "is_fraud": True,
                                "fraud_type": "COPY_PASTE_NOI_DUNG_O6",
                                "reason": "Sao chép nội dung Thân bài (Ô 6) từ bạn học",
                                "student_a": {
                                    "sbd": current_sbd,
                                    "mssv": current_mssv,
                                    "name": current_name,
                                    "class_code": class_code or "Chung"
                                },
                                "student_b": {
                                    "mssv": other_mssv,
                                    "name": other_name,
                                    "class_code": fn_class
                                },
                                "similarity": sim,
                                "evidence": f"Sinh viên A ({current_name} - MSSV: {current_mssv}) đã sao chép {sim}% nội dung Thân bài (Ô 6) từ file '{fn}' của Sinh viên B ({other_name} - MSSV: {other_mssv})."
                            }
                except Exception:
                    continue

        return {"is_fraud": False, "box6_text": clean_curr_box6}
    except Exception as e:
        return {"is_fraud": False, "box6_text": ""}

def check_anti_cheat(docx_path, current_sbd, current_mssv, current_name, students_db=None, doc_type=None, class_code=None):
    """
    Kiểm tra gian lận (S01 - S12, Priority 5):
    - Chiêu 1: SV A nộp nguyên file của SV B (Đổi tên file)
    - Chiêu 2: SV A mở file mình nhưng Copy-Paste nội dung từ file của SV B
    - Chiêu 3: SV copy toàn bộ nội dung từ tài liệu bên ngoài dán đè vào file mẫu
    - Chiêu 4: Giả mạo/xóa metadata hoặc dùng phôi sai loại văn bản (S09, S10)
    """
    try:
        doc = Document(docx_path)
        core_props = doc.core_properties
        
        # KIỂM TRA 1: METADATA & TOKEN (S08, S09, S10)
        token_header = getattr(core_props, "identifier", "") or ""
        keywords = getattr(core_props, "keywords", "") or ""
        
        if not token_header.startswith("STVB_SIGNATURE:") or not keywords:
            return {
                "is_fraud": True,
                "fraud_type": "FILE_KHONG_HOP_LE",
                "reason": "File không có chữ ký số STVB",
                "message": "File bài làm không chứa mã bảo mật hợp lệ của hệ thống! Sinh viên phải sử dụng đúng file mẫu tải về từ phần mềm."
            }
            
        parts = keywords.split("|")
        if len(parts) < 5:
            return {
                "is_fraud": True,
                "fraud_type": "FILE_KHONG_HOP_LE",
                "reason": "Metadata phôi thiếu trường thông tin bảo mật",
                "message": "Phôi bài làm không đầy đủ các thông tin bảo mật hợp lệ theo quy chế thi!"
            }

        orig_sbd, orig_mssv, orig_name, orig_doc_type, timestamp = parts[0], parts[1], parts[2], parts[3], parts[4]
        orig_class = parts[5] if len(parts) >= 6 else (class_code or "")

        # S10: Đối chiếu loại văn bản được cấp phôi với loại văn bản đang nộp/thẩm định
        if doc_type and orig_doc_type and orig_doc_type.strip() != str(doc_type).strip():
            return {
                "is_fraud": True,
                "fraud_type": "FILE_KHONG_HOP_LE",
                "reason": "Phôi đề không đúng loại văn bản",
                "message": f"Phôi đề này được cấp phát cho loại văn bản [{orig_doc_type}], không khớp với bài nộp [{doc_type}]! Vui lòng nộp đúng loại văn bản."
            }

        # R6: Đối chiếu mã lớp của phôi đề với lớp đang làm bài nếu phôi có gắn mã lớp
        if class_code and len(parts) >= 6 and parts[5] and str(parts[5]).strip().upper() != str(class_code).strip().upper():
            return {
                "is_fraud": True,
                "fraud_type": "FILE_KHONG_HOP_LE",
                "reason": "Phôi đề cấp cho lớp khác",
                "message": f"Phôi đề này được cấp phát cho lớp [{parts[5]}], không khớp với lớp [{class_code}] đang làm bài! Vui lòng làm bài trên đúng phôi đề của lớp."
            }

        # D14 & S08: Xác minh mã bảo mật HMAC phôi bài bằng hmac.compare_digest
        token_val = token_header[len("STVB_SIGNATURE:"):].strip()
        if not verify_anti_cheat_token(token_val, orig_sbd, orig_mssv, orig_doc_type, timestamp, orig_class):
            return {
                "is_fraud": True,
                "fraud_type": "FILE_KHONG_HOP_LE",
                "reason": "Mã xác thực phôi đề (HMAC) không khớp hoặc đã bị chỉnh sửa giả mạo",
                "message": "Phát hiện mã xác thực phôi đề thi bị sửa đổi! Bạn phải làm bài trên đúng phôi chính thức được cấp phát."
            }

        # Nếu MSSV trong file không khớp với MSSV người đang đăng nhập nộp bài
        if str(orig_mssv).strip() != str(current_mssv).strip():
            return {
                "is_fraud": True,
                "fraud_type": "NOP_NGUYEN_FILE_BAN",
                "reason": "Nộp nguyên file của bạn học",
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
        
        # 2a. Phát hiện mã thủy ấn của sinh viên khác -> Chép bài từ bạn học
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
                "reason": "Sao chép bài bạn học",
                "student_a": {
                    "sbd": current_sbd,
                    "mssv": current_mssv,
                    "name": current_name
                },
                "student_b": {
                    "mssv": target_b_mssv,
                    "name": student_b_name
                },
                "evidence": f"Sinh viên A ({current_name} - MSSV: {current_mssv}) đã copy-paste nội dung bài làm từ file của Sinh viên B ({student_b_name} - MSSV: {target_b_mssv}). Thủy ấn số bí mật của Sinh viên B đã bị phát hiện trong nội dung văn bản."
            }

        # 2b. Phát hiện copy nội dung bên ngoài dán đè vào file mẫu:
        # File có mã bảo mật phôi STVB nhưng toàn bộ thủy ấn MSSV của chính sinh viên đã bị xóa sạch
        # VÀ tài liệu không chứa bất kỳ từ khóa cơ quan/đơn vị ban hành nào của phôi mẫu (NTTU).
        effective_doc_type = doc_type or (parts[3] if 'parts' in locals() and len(parts) >= 4 else None)
        
        nttu_keywords = ["NGUYỄN TẤT THÀNH", "NGUYEN TAT THANH", "DNTT", "ĐẠI HỌC NGUYỄN TẤT THÀNH"]
        curr_tmpl = {}
        try:
            from engine.common import DATA_DIR, load_json_file
            templates_path = os.path.join(DATA_DIR, "document_templates.json")
            all_tmpls = load_json_file(templates_path, {})
            curr_tmpl = all_tmpls.get(effective_doc_type, {})
            header_part = curr_tmpl.get("header_part", "")
            for line in header_part.split("\n"):
                if "cơ quan" in line.lower() and ":" in line:
                    agency = line.split(":", 1)[1].strip().upper()
                    if agency and len(agency) >= 4 and agency not in nttu_keywords:
                        nttu_keywords.append(agency)
        except Exception:
            pass

        full_text_upper = full_text.upper()
        has_template_agency = any(kw in full_text_upper for kw in nttu_keywords)

        is_blank = bool(curr_tmpl.get("is_body_blank", False)) or (effective_doc_type == "bai_thu_hoach")
        has_no_tables = (len(doc.tables) == 0)
        if not is_blank and str(current_mssv).strip() not in all_found_mssvs and not has_template_agency and has_no_tables:
            return {
                "is_fraud": True,
                "fraud_type": "COPY_NOI_DUNG_BEN_NGOAI",
                "reason": "Sao chép toàn bộ văn bản bên ngoài",
                "student_a": {
                    "sbd": current_sbd,
                    "mssv": current_mssv,
                    "name": current_name
                },
                "evidence": f"Sinh viên {current_name} (MSSV: {current_mssv}) đã copy toàn bộ nội dung từ tài liệu bên ngoài dán đè vào file mẫu! Bài làm không còn chứa mã thủy ấn số bảo mật của phôi đề thi được hệ thống cấp phát."
            }

        # 3. KIỂM TRA ĐẠO VĂN NỘI DUNG THÂN BÀI (Ô 6) GIỮA CÁC SINH VIÊN
        box6_result = check_box6_plagiarism(
            docx_path=docx_path,
            current_sbd=current_sbd,
            current_mssv=current_mssv,
            current_name=current_name,
            doc_type=effective_doc_type,
            class_code=class_code,
            students_db=students_db
        )
        if box6_result.get("is_fraud"):
            return box6_result

        return {"is_fraud": False, "message": "File chính chủ và bảo mật hợp lệ.", "box6_text": box6_result.get("box6_text", "")}

    except Exception as e:
        return {
            "is_fraud": True,
            "fraud_type": "ERROR_READING_FILE",
            "message": f"Không thể đọc file: {str(e)}"
        }

def sanitize_identifier(value: str, default: str = "") -> str:
    """
    Làm sạch định danh (sbd, mssv, doc_type, class_code) để chống Path Traversal (D21).
    Chỉ cho phép ký tự an toàn: a-z, A-Z, 0-9, gạch dưới, gạch ngang.
    Loại bỏ mọi ký tự phân cách thư mục (/, \\) và ký tự điều hướng (..).
    """
    if value is None:
        return default
    s = str(value).strip()
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]', '', s)
    return cleaned if cleaned else default

def safe_storage_path(base_dir: str, filename: str) -> str:
    """
    Đảm bảo đường dẫn tệp nằm hoàn toàn bên trong base_dir (chống Path Traversal - D21).
    Ngăn chặn việc ghi hoặc đọc tệp ra ngoài thư mục lưu trữ được chỉ định.
    """
    if not filename:
        raise ValueError("Filename không được để trống!")
    
    # Phát hiện nỗ lực thoát thư mục (Path Traversal)
    if ".." in filename or filename.startswith("/") or filename.startswith("\\"):
        raise ValueError(f"Phát hiện hành vi Path Traversal không hợp lệ: {filename}")

    safe_name = os.path.basename(filename)
    safe_name = re.sub(r'[\\/]', '', safe_name)
    resolved_base = os.path.realpath(base_dir)
    full_path = os.path.realpath(os.path.join(resolved_base, safe_name))
    if not (full_path == resolved_base or full_path.startswith(resolved_base + os.sep)):
        raise ValueError(f"Phát hiện hành vi Path Traversal không hợp lệ: {filename}")
    return full_path

MAX_DOCX_FILE_COUNT = 500
MAX_DOCX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50MB
MAX_COMPRESSION_RATIO = 100.0

def validate_docx_resource_limits(file_path: str):
    """
    D28: Kiểm tra giới hạn tài nguyên và chống Zip Bomb:
    - Số lượng tệp nén bên trong <= 500
    - Tổng kích thước giải nén <= 50MB
    - Tỷ lệ nén giải nén <= 100 lần (nếu kích thước tệp con > 1MB)
    - Trả về (is_valid: bool, error_message: str, is_too_large: bool)
    """
    if not file_path or not os.path.exists(file_path):
        return False, "Tệp không tồn tại hoặc đường dẫn rỗng.", False
    
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, "Tệp rỗng (0 bytes).", False
    
    if file_size > 16 * 1024 * 1024:
        return False, f"Dung lượng tệp ({file_size / (1024*1024):.1f}MB) vượt quá giới hạn tối đa 16MB!", True

    if not zipfile.is_zipfile(file_path):
        return False, "Tệp tải lên không phải là định dạng Word (.docx) hợp lệ hoặc đã bị hỏng!", False

    try:
        with zipfile.ZipFile(file_path, "r") as z:
            infolist = z.infolist()
            if len(infolist) > MAX_DOCX_FILE_COUNT:
                return False, f"Tệp chứa quá nhiều thành phần bên trong ({len(infolist)} > {MAX_DOCX_FILE_COUNT}). Phát hiện nguy cơ Zip Bomb!", True
            
            total_uncompressed = 0
            for info in infolist:
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_DOCX_UNCOMPRESSED_SIZE:
                    return False, f"Tổng kích thước sau giải nén ({total_uncompressed / (1024*1024):.1f}MB) vượt quá giới hạn an toàn 50MB!", True
                
                # Kiểm tra tỷ lệ nén bất thường (Decompression bomb)
                if info.file_size > 1024 * 1024 and info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > MAX_COMPRESSION_RATIO:
                        return False, f"Tỷ lệ nén bất thường ({ratio:.1f}x). Phát hiện nguy cơ Decompression Bomb!", True

            names = [info.filename for info in infolist]
            # Priority 5: Bắt buộc cả [Content_Types].xml và word/document.xml phải tồn tại
            if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                return False, "Tệp không có cấu trúc tài liệu Word (.docx) chuẩn (thiếu [Content_Types].xml hoặc word/document.xml).", False

            try:
                import xml.etree.ElementTree as ET
                doc_xml_bytes = z.read("word/document.xml")
                ET.fromstring(doc_xml_bytes)
            except Exception:
                return False, "Cấu trúc XML của tài liệu Word bị hỏng hoặc không đúng định dạng OpenXML!", False

            return True, "Hợp lệ", False
    except Exception as e:
        return False, f"Không thể đọc cấu trúc tệp .docx: {str(e)}", False

def is_valid_docx(file_path: str) -> bool:
    """
    Kiểm tra xem tệp có phải là định dạng Word .docx chuẩn và không bị hỏng (D01, D28).
    Bao gồm kiểm tra chữ ký số ZIP, cấu trúc OpenXML và giới hạn tài nguyên an toàn.
    """
    valid, _, _ = validate_docx_resource_limits(file_path)
    return valid
