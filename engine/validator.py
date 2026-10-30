import os
import re
import unicodedata
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, Inches

class Decree30Validator:
    def __init__(self, docx_path, doc_type_id, template_info=None, mssv=None):
        self.doc_path = str(docx_path) if isinstance(docx_path, str) else ""
        self.doc = docx_path if hasattr(docx_path, "paragraphs") else Document(docx_path)
        self.doc_type_id = doc_type_id
        self.template_info = template_info or {}
        self.mssv = str(mssv).strip() if mssv else None
        self.results = {}
        # Hồ sơ quy ước cỡ chữ: "SO_TRUOC" (Bộ nhỏ: 12-13) hoặc "SO_SAU" (Bộ lớn: 13-14)
        self.font_profile = "SO_TRUOC"
        # Mặc định tài liệu theo OpenXML (docDefaults)
        self.doc_default_font = "Times New Roman"
        self.doc_default_size = 13.0
        self._load_doc_defaults()

    def _load_doc_defaults(self):
        """Đọc thuộc tính mặc định của tài liệu Word từ OpenXML docDefaults (styles.xml)"""
        try:
            styles_elem = self.doc.styles.element
            docDefaults = styles_elem.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}docDefaults')
            if docDefaults is not None:
                rPrDefault = docDefaults.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPrDefault')
                if rPrDefault is not None:
                    rPr = rPrDefault.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
                    if rPr is not None:
                        sz = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
                        if sz is not None:
                            val = sz.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                            if val and val.isdigit():
                                self.doc_default_size = float(val) / 2.0
                        rFonts = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts')
                        if rFonts is not None:
                            f_name = (rFonts.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii') or
                                      rFonts.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hAnsi'))
                            if f_name:
                                self.doc_default_font = f_name
        except Exception:
            pass

    def _clean_text(self, paragraph_or_str):
        """Chuẩn hóa chuỗi tiếng Việt: NFC, xóa ký tự vô hình, non-breaking space, khoảng trắng thừa"""
        if paragraph_or_str is None:
            return ""
        if hasattr(paragraph_or_str, "text"):
            raw = paragraph_or_str.text
        else:
            raw = str(paragraph_or_str)

        norm = unicodedata.normalize('NFC', raw)
        cleaned = re.sub(r'[\u200b\u200c\u200d\ufeff\xa0]', ' ', norm)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _is_quoc_hieu(self, text):
        c = self._clean_text(text)
        return bool(re.search(r"CỘNG\s+H[ÒO][ÀA]\s+XÃ\s+HỘI\s+CHỦ\s+NGHĨA\s+VIỆT\s+NAM", c, re.IGNORECASE))

    def _is_tieu_ngu(self, text):
        c = self._clean_text(text).upper()
        return ("ĐỘC LẬP" in c and "HẠNH PHÚC" in c)

    def _get_dominant_font_and_size(self, paragraph):
        """Trích xuất chính xác Font, Size, Bold, Italic theo chuẩn phân tầng OpenXML: Run -> Paragraph pPr -> Style -> DocDefaults"""
        if not paragraph:
            return self.doc_default_font, self.doc_default_size, False, False

        fonts = []
        sizes = []
        bolds = []
        italics = []

        # Tầng 1: Quét từ các Runs (định dạng trực tiếp cho từng đoạn chữ)
        for r in paragraph.runs:
            if r.font.name:
                fonts.append(r.font.name)
            if r.font.size:
                sizes.append(round(r.font.size.pt, 1))
            if r.bold is not None:
                bolds.append(bool(r.bold))
            if r.italic is not None:
                italics.append(bool(r.italic))

            rPr = getattr(r._element, "rPr", None)
            if rPr is not None:
                b_elem = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}b')
                if b_elem is not None:
                    val = b_elem.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '1')
                    if val not in ['0', 'false']:
                        bolds.append(True)

                i_elem = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}i')
                if i_elem is not None:
                    val = i_elem.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val', '1')
                    if val not in ['0', 'false']:
                        italics.append(True)

                sz_elem = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
                if sz_elem is not None:
                    val = sz_elem.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                    if val and val.isdigit():
                        sizes.append(float(val) / 2.0)

                rFonts = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts')
                if rFonts is not None:
                    f_name = (rFonts.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}ascii') or 
                              rFonts.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hAnsi'))
                    if f_name:
                        fonts.append(f_name)

        # Tầng 2: Nếu chưa có từ Runs, kiểm tra Paragraph Style & Document Defaults
        has_text_runs = any(r.text.strip() for r in paragraph.runs)
        if not sizes and not has_text_runs:
            # Chỉ dùng pPr/rPr/sz khi đoạn văn không có text run (đoạn trống ký tên)
            pPr = getattr(paragraph._element, "pPr", None)
            if pPr is not None:
                rPr_p = pPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
                if rPr_p is not None:
                    sz_elem = rPr_p.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
                    if sz_elem is not None:
                        val = sz_elem.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')
                        if val and val.isdigit():
                            sizes.append(float(val) / 2.0)

        # Tầng 3: Nếu chưa có, kế thừa từ Style của Paragraph (kể cả base styles)
        st = getattr(paragraph, "style", None)
        while st is not None:
            if not sizes and st.font and st.font.size:
                sizes.append(round(st.font.size.pt, 1))
            if not fonts and st.font and st.font.name:
                fonts.append(st.font.name)
            if not bolds and st.font and st.font.bold is not None:
                bolds.append(bool(st.font.bold))
            if not italics and st.font and st.font.italic is not None:
                italics.append(bool(st.font.italic))
            st = getattr(st, "base_style", None)

        # Tầng 4: Nếu vẫn chưa có, kế thừa từ Document Defaults (docDefaults của file Word)
        main_font = fonts[0] if fonts else self.doc_default_font
        main_size = sizes[0] if sizes else self.doc_default_size
        is_bold = any(bolds)
        is_italic = any(italics)
        return main_font, main_size, is_bold, is_italic

    def get_expected_size(self, box_key):
        """
        Quy tắc Thống nhất Thẩm mỹ Số Trước - Số Sau:
        'SO_TRUOC' (Bộ nhỏ): Quốc hiệu 12, Tiêu ngữ 13, CQ 12, Địa danh 13, Thân bài 13, Ký 13...
        'SO_SAU'   (Bộ lớn): Quốc hiệu 13, Tiêu ngữ 14, CQ 13, Địa danh 14, Thân bài 14, Ký 14...
        """
        mapping = {
            "quoc_hieu": (12.0, 13.0),
            "tieu_ngu": (13.0, 14.0),
            "co_quan": (12.0, 13.0),
            "so_ky_hieu": (13.0, 13.0), # Cố định 13pt
            "dia_danh": (13.0, 14.0),
            "ten_loai_5a": (13.0, 14.0),
            "trich_yeu_5a": (13.0, 14.0),
            "trich_yeu_5b": (12.0, 13.0),
            "noi_dung": (13.0, 14.0),
            "chuc_vu": (13.0, 14.0),
            "ho_ten": (13.0, 14.0),
            "kinh_gui": (13.0, 14.0),
            "noi_nhan_title": (12.0, 12.0), # Cố định 12pt
            "noi_nhan_item": (11.0, 11.0)   # Cố định 11pt
        }
        pair = mapping.get(box_key, (13.0, 14.0))
        return pair[0] if self.font_profile == "SO_TRUOC" else pair[1]

    # =========================================================================
    # CĂN LỀ TRANG GIẤY (PAGE MARGINS)
    # =========================================================================
    def check_page_margins(self):
        errors = []
        for section in self.doc.sections:
            top_cm = section.top_margin.inches * 2.54
            bot_cm = section.bottom_margin.inches * 2.54
            left_cm = section.left_margin.inches * 2.54
            right_cm = section.right_margin.inches * 2.54

            # Nếu vẫn là lề mặc định 2.54cm
            if abs(top_cm - 2.54) < 0.05 and abs(left_cm - 2.54) < 0.05 and abs(right_cm - 2.54) < 0.05:
                errors.append({
                    "issue": "Bạn chưa căn lề trang văn bản (đang để lề mặc định 2.54 cm).",
                    "fix": "Vào thẻ Layout ➔ Margins ➔ Custom Margins: Trên: 2.0-2.5cm, Dưới: 2.0-2.5cm, Trái: 3.0-3.5cm, Phải: 1.5-2.0cm."
                })
                break

            if not (1.9 <= top_cm <= 2.6):
                errors.append({
                    "issue": f"Lề trên chưa đạt chuẩn NĐ 30 (Hiện tại: {top_cm:.2f} cm).",
                    "fix": "Đặt lại lề trên từ 2.0 cm đến 2.5 cm (Số trước: 2.0cm, Số sau: 2.5cm)."
                })
            if not (1.9 <= bot_cm <= 2.6):
                errors.append({
                    "issue": f"Lề dưới chưa đạt chuẩn NĐ 30 (Hiện tại: {bot_cm:.2f} cm).",
                    "fix": "Đặt lại lề dưới từ 2.0 cm đến 2.5 cm (Số trước: 2.0cm, Số sau: 2.5cm)."
                })
            if not (2.9 <= left_cm <= 3.6):
                errors.append({
                    "issue": f"Lề trái chưa đạt chuẩn NĐ 30 (Hiện tại: {left_cm:.2f} cm).",
                    "fix": "Đặt lại lề trái từ 3.0 cm đến 3.5 cm (Số trước: 3.0cm, Số sau: 3.5cm)."
                })
            if not (1.4 <= right_cm <= 2.1):
                errors.append({
                    "issue": f"Lề phải chưa đạt chuẩn NĐ 30 (Hiện tại: {right_cm:.2f} cm).",
                    "fix": "Đặt lại lề phải từ 1.5 cm đến 2.0 cm (Số trước: 1.5cm, Số sau: 2.0cm)."
                })
            break

        return {
            "box_id": "margins",
            "name": "Căn lề trang giấy (Page Margins)",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # KIỂM TRA BẮT BUỘC VỀ BẢNG (TABLE STRUCTURE: ĐẦU 2x2, CUỐI 1x2)
    # =========================================================================
    def check_table_structures(self, header_table, footer_table):
        errors = []
        is_cong_van = (self.doc_type_id in ["cong_van_de_nghi", "bai_thu_hoach"])

        # 1. BẢNG ĐẦU TRANG: Phải là 2 cột x 2 dòng
        if not header_table:
            errors.append({
                "issue": "Chưa có Bảng đầu trang (Header Table).",
                "fix": "Tạo 1 Table gồm 2 cột và 2 dòng ở đầu trang (Đối với Công văn chứa Ô 1-5b; đối với Thông báo, Tờ trình chứa Ô 1-4)."
            })
        else:
            rows_cnt = len(header_table.rows)
            cols_cnt = len(header_table.columns) if hasattr(header_table, 'columns') else len(header_table.rows[0].cells)
            if rows_cnt != 2 or cols_cnt != 2:
                errors.append({
                    "issue": f"Bảng đầu trang bắt buộc phải gồm đúng 2 CỘT và 2 DÒNG (Hiện tại: {rows_cnt} dòng, {cols_cnt} cột).",
                    "fix": "Chỉnh sửa Bảng đầu trang thành 2 cột x 2 dòng: Hàng 1 chứa [Ô 2 / Ô 1]; Hàng 2 chứa [Ô 3 (+5b) / Ô 4]."
                })

        # 2. BẢNG CUỐI TRANG: Phải là 2 cột x 1 dòng
        if not footer_table:
            errors.append({
                "issue": "Chưa có Bảng cuối trang (Footer Table).",
                "fix": "Tạo 1 Table gồm 2 cột và 1 dòng ở cuối văn bản chứa Ô 9b (cột trái) và Ô 7a, 7b (cột phải)."
            })
        else:
            rows_cnt_f = len(footer_table.rows)
            cols_cnt_f = len(footer_table.columns) if hasattr(footer_table, 'columns') else len(footer_table.rows[0].cells)
            if rows_cnt_f != 1 or cols_cnt_f != 2:
                errors.append({
                    "issue": f"Bảng cuối trang bắt buộc phải gồm đúng 2 CỘT và 1 DÒNG (Hiện tại: {rows_cnt_f} dòng, {cols_cnt_f} cột).",
                    "fix": "Chỉnh sửa Bảng cuối trang thành 1 dòng x 2 cột: Cột 1 chứa Ô 9b (Nơi nhận), Cột 2 chứa Ô 7a, 7b (Chức vụ, Chữ ký, Họ tên)."
                })

        # 3. KIỂM TRA ĐỐI PHÓ: LẠM DỤNG PHÍM SPACE ĐỂ CĂN CHỈNH THAY VÌ DÙNG BẢNG HOẶC TAB
        space_abuse_found = False
        for p in self.doc.paragraphs:
            if re.search(r' {4,}', p.text):
                space_abuse_found = True
                break
        if not space_abuse_found:
            for t in self.doc.tables:
                for row in t.rows:
                    for cell in row.cells:
                        for p in cell.paragraphs:
                            if re.search(r' {4,}', p.text):
                                space_abuse_found = True
                                break

        if space_abuse_found:
            errors.append({
                "issue": "Phát hiện lạm dụng phím Space (từ 4 dấu cách liên tiếp trở lên) để căn chỉnh vị trí chữ.",
                "fix": "Nhấn tổ hợp Ctrl + H, tìm 2 dấu cách liên tiếp ('  ') và thay thế bằng Tab ('^t') hoặc dùng công cụ Canh lề (Ctrl + E / Ctrl + J). Tuyệt đối không gõ Space liên tiếp để đẩy chữ."
            })

        # 4. KIỂM TRA ĐỐI PHÓ: LẠM DỤNG PHÍM ENTER LIÊN TIẾP DỒN TRANG
        consecutive_empty = 0
        max_consecutive_empty = 0
        for p in self.doc.paragraphs:
            if not self._clean_text(p):
                consecutive_empty += 1
                if consecutive_empty > max_consecutive_empty:
                    max_consecutive_empty = consecutive_empty
            else:
                consecutive_empty = 0

        if max_consecutive_empty >= 4:
            errors.append({
                "issue": f"Lạm dụng phím Enter tạo {max_consecutive_empty} dòng trống liên tiếp ngoài bảng để dồn trang.",
                "fix": "Xóa các dòng Enter trống thừa. Sử dụng định dạng Spacing Before/After trong Paragraph hoặc ngắt trang Page Break (Ctrl+Enter)."
            })

        return {
            "box_id": "tables",
            "name": "Cấu trúc Bảng đầu trang (2x2) và Bảng cuối trang (1x2)",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 1: QUỐC HIỆU VÀ TIÊU NGỮ (ĐỊNH HÌNH QUY ƯỚC CỠ CHỮ SỐ TRƯỚC / SỐ SAU)
    # =========================================================================
    def check_box_1_quoc_hieu(self, p_quoc_hieu, p_tieu_ngu):
        errors = []
        if not p_quoc_hieu or not p_tieu_ngu:
            missing = []
            if not p_quoc_hieu: missing.append("dòng Quốc hiệu ('CỘNG HÒA/HOÀ XÃ HỘI CHỦ NGHĨA VIỆT NAM')")
            if not p_tieu_ngu: missing.append("dòng Tiêu ngữ ('Độc lập – Tự do – Hạnh phúc')")
            return {
                "box_id": 1,
                "name": "Ô 1: Quốc hiệu và Tiêu ngữ",
                "passed": False,
                "errors": [{
                    "issue": f"Chưa tìm thấy {', '.join(missing)} ở góc trên bên phải.",
                    "fix": "Trình bày Quốc hiệu (dòng 1) và Tiêu ngữ (dòng 2) trong ô trên bên phải (Hàng 1, Cột 2) của Bảng đầu trang."
                }]
            }

        t1 = self._clean_text(p_quoc_hieu)
        t2 = self._clean_text(p_tieu_ngu)

        # 1. QUỐC HIỆU
        if not self._is_quoc_hieu(t1):
            errors.append({"issue": "Dòng Quốc hiệu viết sai chính tả hoặc thiếu chữ.", "fix": "Ghi chính xác: 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'."})
        if t1 != t1.upper():
            errors.append({"issue": "Dòng Quốc hiệu chưa viết IN HOA toàn bộ.", "fix": "Chuyển thành chữ IN HOA (UPPERCASE)." })

        font1, size1, bold1, italic1 = self._get_dominant_font_and_size(p_quoc_hieu)
        if not bold1:
            errors.append({"issue": "Dòng Quốc hiệu chưa in đậm.", "fix": "Bôi đen dòng Quốc hiệu và nhấn Ctrl + B để in đậm."})
        if italic1:
            errors.append({"issue": "Dòng Quốc hiệu không được in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I). Kiểu chữ phải là đứng."})
        if size1 not in [12.0, 13.0]:
            errors.append({"issue": f"Cỡ chữ Quốc hiệu phải là 12 hoặc 13 (Hiện tại: {size1}pt).", "fix": "Chỉnh cỡ chữ về 12 (nếu chọn số trước) hoặc 13 (nếu chọn số sau)."})
        if p_quoc_hieu.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
            errors.append({"issue": "Dòng Quốc hiệu chưa được canh giữa (Center).", "fix": "Nhấn Ctrl + E để canh giữa."})

        # XÁC ĐỊNH HỒ SƠ QUY ƯỚC CỠ CHỮ TOÀN BÀI: SỐ TRƯỚC (12) HAY SỐ SAU (13)
        if size1 == 13.0:
            self.font_profile = "SO_SAU"
        else:
            self.font_profile = "SO_TRUOC"

        # 2. TIÊU NGỮ
        if not self._is_tieu_ngu(t2):
            errors.append({"issue": "Dòng Tiêu ngữ viết chưa đúng nội dung.", "fix": "Ghi chính xác: 'Độc lập - Tự do - Hạnh phúc'."})
        if t2 == t2.upper():
            errors.append({"issue": "Dòng Tiêu ngữ không được viết hoa toàn bộ.", "fix": "Chỉ viết hoa các chữ cái đầu Đ, T, H: 'Độc lập - Tự do - Hạnh phúc'."})
        elif not re.search(r"Độc\s+lập.*Tự\s+do.*Hạnh\s+phúc", t2):
            errors.append({"issue": "Tiêu ngữ phải viết hoa các chữ cái đầu của 3 cụm từ: Đ, T, H.", "fix": "Sửa đúng thành: 'Độc lập - Tự do - Hạnh phúc'."})
        if not re.search(r"\s+[-–—]\s+", t2):
            errors.append({"issue": "Giữa các cụm từ trong Tiêu ngữ phải có dấu gạch nối CÓ CÁCH CHỮ (khoảng trắng 2 bên).", "fix": "Thêm dấu cách trước và sau dấu gạch nối (Ví dụ: 'Độc lập - Tự do - Hạnh phúc')."})

        font2, size2, bold2, italic2 = self._get_dominant_font_and_size(p_tieu_ngu)
        if not bold2:
            errors.append({"issue": "Dòng Tiêu ngữ chưa in đậm.", "fix": "Bôi đen dòng Tiêu ngữ và nhấn Ctrl + B để in đậm."})
        if italic2:
            errors.append({"issue": "Dòng Tiêu ngữ không được in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I). Kiểu chữ phải là đứng."})

        # KIỂM TRA ĐỒNG NHẤT CỠ CHỮ TIÊU NGỮ THEO QUY ƯỚC
        expected_tn_size = self.get_expected_size("tieu_ngu") # 13 if SO_TRUOC, 14 if SO_SAU
        if size2 != expected_tn_size:
            errors.append({
                "issue": f"Tính thống nhất cỡ chữ: Bạn chọn Quốc hiệu cỡ {int(size1)}pt ({'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}), do đó Tiêu ngữ bắt buộc phải là cỡ {int(expected_tn_size)}pt (Hiện tại: {size2}pt).",
                "fix": f"Chỉnh cỡ chữ Tiêu ngữ về đúng {int(expected_tn_size)}pt để đảm bảo tính đồng nhất và thẩm mỹ."
            })

        if p_tieu_ngu.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
            errors.append({"issue": "Dòng Tiêu ngữ chưa được canh giữa (Center).", "fix": "Nhấn Ctrl + E để canh giữa."})

        # Tuyệt đối không dùng Underline
        if any(r.underline for r in p_tieu_ngu.runs):
            errors.append({
                "issue": "Dòng Tiêu ngữ đang dùng lệnh Underline (gạch chân). Theo NĐ 30, bắt buộc phải dùng lệnh vẽ Shape line thay thế.",
                "fix": "Tắt gạch chân (Ctrl + U), sau đó vào Insert ➔ Shapes ➔ Chọn Line để vẽ đường kẻ nét liền có độ dài bằng độ dài dòng chữ Tiêu ngữ."
            })

        # 3. KHOẢNG CÁCH DÒNG ĐƠN (Single line, Before: 0pt, After: 0pt)
        sp_after = getattr(p_quoc_hieu.paragraph_format.space_after, "pt", 0) or 0
        sp_before = getattr(p_tieu_ngu.paragraph_format.space_before, "pt", 0) or 0
        line_sp = p_quoc_hieu.paragraph_format.line_spacing or 1.0
        if sp_after > 3 or sp_before > 3 or (isinstance(line_sp, float) and line_sp > 1.15):
            errors.append({
                "issue": "Hai dòng Quốc hiệu và Tiêu ngữ phải cách nhau dòng đơn (Single line, Before: 0pt, After: 0pt).",
                "fix": "Chọn cả 2 dòng ➔ Vào Paragraph ➔ Line spacing: Single, Before: 0pt, After: 0pt."
            })

        return {
            "box_id": 1,
            "name": f"Ô 1: Quốc hiệu và Tiêu ngữ (Quy ước: {'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'})",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 2: TÊN CƠ QUAN, TỔ CHỨC BAN HÀNH VĂN BẢN
    # =========================================================================
    def check_box_2_co_quan(self, p_cq_quan_ly, p_cq_ban_hanh):
        errors = []
        if not p_cq_ban_hanh:
            return {
                "box_id": 2,
                "name": "Ô 2: Tên cơ quan, tổ chức ban hành",
                "passed": False,
                "errors": [{"issue": "Chưa tìm thấy Tên cơ quan ban hành văn bản ở Hàng 1 Cột 1 của Bảng đầu trang.", "fix": "Trình bày tên cơ quan ban hành ở ô trên bên trái của Bảng đầu trang."}]
            }

        t_ban_hanh = self._clean_text(p_cq_ban_hanh)
        if t_ban_hanh != t_ban_hanh.upper():
            errors.append({"issue": "Tên cơ quan ban hành văn bản phải viết IN HOA toàn bộ.", "fix": "Chuyển thành chữ IN HOA (UPPERCASE)."})

        font, size, bold, italic = self._get_dominant_font_and_size(p_cq_ban_hanh)
        if not bold:
            errors.append({"issue": "Tên cơ quan ban hành văn bản phải in đậm.", "fix": "Bôi đen và nhấn Ctrl + B để in đậm."})
        if italic:
            errors.append({"issue": "Tên cơ quan ban hành văn bản không được in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I). Kiểu chữ phải là đứng."})

        # ĐỒNG NHẤT CỠ CHỮ: 12 if SO_TRUOC, 13 if SO_SAU
        expected_cq_size = self.get_expected_size("co_quan")
        if size != expected_cq_size:
            errors.append({
                "issue": f"Tính thống nhất cỡ chữ: Bạn chọn quy ước '{'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}', do đó Tên cơ quan ban hành phải là cỡ {int(expected_cq_size)}pt (Hiện tại: {size}pt).",
                "fix": f"Chỉnh cỡ chữ Tên cơ quan ban hành về đúng {int(expected_cq_size)}pt."
            })
        if p_cq_ban_hanh.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
            errors.append({"issue": "Tên cơ quan ban hành văn bản chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

        # Cơ quan chủ quản cấp trên (nếu có 2 cơ quan)
        if p_cq_quan_ly:
            t_ql = self._clean_text(p_cq_quan_ly)
            if t_ql and t_ql != t_ql.upper():
                errors.append({"issue": "Tên cơ quan chủ quản cấp trên phải viết IN HOA toàn bộ.", "fix": "Chuyển thành chữ IN HOA."})
            font_ql, size_ql, bold_ql, italic_ql = self._get_dominant_font_and_size(p_cq_quan_ly)
            if bold_ql:
                errors.append({
                    "issue": "Tên cơ quan chủ quản cấp trên KHÔNG in đậm (khi có 2 cơ quan, chỉ in đậm cơ quan thứ 2).",
                    "fix": "Bỏ in đậm dòng cơ quan cấp trên (Ctrl + B)."
                })
            if italic_ql:
                errors.append({"issue": "Tên cơ quan chủ quản cấp trên không được in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I)."})
            if size_ql != expected_cq_size:
                errors.append({
                    "issue": f"Cỡ chữ Cơ quan chủ quản phải thống nhất là {int(expected_cq_size)}pt (Hiện tại: {size_ql}pt).",
                    "fix": f"Chỉnh cỡ chữ về {int(expected_cq_size)}pt."
                })

            sp_after_ql = getattr(p_cq_quan_ly.paragraph_format.space_after, "pt", 0) or 0
            if sp_after_ql > 3:
                errors.append({
                    "issue": "Hai dòng tên cơ quan được trình bày cách nhau dòng đơn (Line spacing: Single, Before/After: 0pt).",
                    "fix": "Vào Paragraph ➔ Line spacing: Single, Space Before: 0pt, Space After: 0pt."
                })

        return {
            "box_id": 2,
            "name": "Ô 2: Tên cơ quan, tổ chức ban hành",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 3: SỐ VÀ KÝ HIỆU VĂN BẢN
    # =========================================================================
    def check_box_3_so_ky_hieu(self, p_so):
        errors = []
        if not p_so:
            return {
                "box_id": 3,
                "name": "Ô 3: Số và ký hiệu văn bản",
                "passed": False,
                "errors": [{"issue": "Không tìm thấy Số, ký hiệu văn bản ở Hàng 2 Cột 1 của Bảng đầu trang.", "fix": "Trình bày 'Số: ...' tại Dòng 2 Cột 1 của Bảng đầu trang."}]
            }

        t = self._clean_text(p_so)
        if t.startswith("SỐ"):
            errors.append({"issue": "Từ 'Số' phải viết in thường (chỉ viết hoa chữ cái S: 'Số: ...').", "fix": "Sửa 'SỐ:' thành 'Số:'."})
        elif not re.match(r"^Số\s*:", t):
            errors.append({"issue": "Số văn bản phải bắt đầu bằng từ 'Số:' và có dấu hai chấm ngay sau.", "fix": "Sửa thành 'Số: ...'."})

        # Kiểm tra khoảng cách sau dấu hai chấm trong 'Số:'
        if re.search(r"^Số:[^\s]", t):
            errors.append({
                "issue": "Ô 3: Quy tắc khoảng cách trống: Sau chữ 'Số:' phải có 1 khoảng trắng (dấu cách) (Đang viết: 'Số:...').",
                "fix": "Thêm 1 dấu cách sau dấu hai chấm (Ví dụ: 'Số: 01/TB-ĐT' thay vì 'Số:01/TB-ĐT')."
            })
        elif re.search(r"^Số\s+:", t):
            errors.append({
                "issue": "Ô 3: Quy tắc khoảng cách trống: Không chừa khoảng trắng trước dấu hai chấm trong 'Số:'.",
                "fix": "Xóa khoảng trắng trước dấu hai chấm: 'Số: ...'."
            })

        if "/" not in t:
            errors.append({"issue": "Giữa số ban hành và ký hiệu văn bản phải có dấu gạch chéo (/).", "fix": "Thêm dấu '/' (Ví dụ: Số: 01/TB-ĐT hoặc Số: 01/HT)." })

        if re.search(r"\s+[-–—]|[-–—]\s+", t):
            errors.append({
                "issue": "Giữa các nhóm chữ viết tắt có dấu nối (-) KHÔNG ĐƯỢC CÁCH CHỮ (không có khoảng trắng).",
                "fix": "Xóa khoảng trắng thừa quanh dấu gạch nối (Ví dụ: 'TB-NS' thay vì 'TB - NS')."
            })
        if " /" in t or "/ " in t:
            errors.append({
                "issue": "Quanh dấu gạch chéo (/) không được có khoảng cách thừa.",
                "fix": "Xóa khoảng trắng thừa (Ví dụ: 'Số: 01/HT' thay vì 'Số: 01 / HT')."
            })

        # KIỂM TRA ĐỐI CHIẾU CÔNG THỨC Ô SỐ 3
        if "/" in t:
            after_slash = t.split("/", 1)[1].strip()
            # 1. CÔNG VĂN: Số: .../<Tên viết tắt CQ>-<Đơn vị> (hoặc Số: .../<Tên viết tắt CQ>)
            # QUY TẮC CỐT LÕI: TUYỆT ĐỐI KHÔNG CÓ TÊN LOẠI VĂN BẢN 'CV'
            is_cv = (self.doc_type_id in ["cong_van_de_nghi", "bai_thu_hoach"]) or getattr(self, "is_cong_van", False)
            if is_cv:
                if re.search(r"^(CV\b|CV[-–—])", after_slash, re.IGNORECASE) or re.search(r"[-–—]CV\b", after_slash, re.IGNORECASE):
                    errors.append({
                        "issue": "Sai công thức Công văn: Trong số và ký hiệu của Công văn tuyệt đối KHÔNG có tên loại văn bản viết tắt 'CV'.",
                        "fix": "Xóa chữ 'CV-' trong ký hiệu (Công thức đúng: Số: .../<Tên viết tắt CQ>-<Đơn vị>, ví dụ 'Số: 01/HT' hoặc 'Số: 12/ĐHNTT-ĐT')."
                    })

            # 2. VĂN BẢN CÓ TÊN LOẠI: BẮT BUỘC CÓ TÊN LOẠI VIẾT TẮT ĐỨNG ĐẦU KÝ HIỆU
            elif self.doc_type_id in ["thong_bao_nhiem_vu", "thong_bao_hoat_dong"]:
                if not re.search(r"^TB[-–—]", after_slash, re.IGNORECASE):
                    errors.append({
                        "issue": "Sai công thức Thông báo: Ký hiệu của văn bản có tên loại (Thông báo) bắt buộc phải có tên loại viết tắt 'TB-' đứng đầu ký hiệu (Công thức: Số: .../TB-<Tên viết tắt đơn vị>).",
                        "fix": "Thêm tiền tố 'TB-' sau dấu gạch chéo (Ví dụ: 'Số: 45/TB-ĐT' hoặc 'Số: 08/TB-ĐTN')."
                    })
            elif self.doc_type_id in ["to_trinh_nhan_su", "to_trinh_thiet_bi", "to_trinh_xin_kinh_phi"]:
                if re.search(r"^TT[-–—]", after_slash, re.IGNORECASE):
                    errors.append({
                        "issue": "Tên loại viết tắt của Tờ trình là 'TTr', không phải 'TT'.",
                        "fix": "Sửa 'TT-' thành 'TTr-' (Ví dụ: 'Số: 15/TTr-CNTT' hoặc 'Số: 22/TTr-KNN')."
                    })
                elif not re.search(r"^TTr[-–—]", after_slash, re.IGNORECASE):
                    errors.append({
                        "issue": "Sai công thức Tờ trình: Ký hiệu của văn bản có tên loại (Tờ trình) bắt buộc phải có tên loại viết tắt 'TTr-' đứng đầu ký hiệu (Công thức: Số: .../TTr-<Tên viết tắt đơn vị>).",
                        "fix": "Thêm tiền tố 'TTr-' sau dấu gạch chéo (Ví dụ: 'Số: 15/TTr-CNTT' hoặc 'Số: 22/TTr-KNN')."
                    })
            elif self.doc_type_id == "bao_cao":
                if not re.search(r"^BC[-–—]", after_slash, re.IGNORECASE):
                    errors.append({
                        "issue": "Sai công thức Báo cáo: Ký hiệu của văn bản có tên loại (Báo cáo) bắt buộc phải có tên loại viết tắt 'BC-' đứng đầu ký hiệu (Công thức: Số: .../BC-<Tên viết tắt đơn vị/cơ quan>).",
                        "fix": "Thêm tiền tố 'BC-' sau dấu gạch chéo (Ví dụ: 'Số: 18/BC-CNTT')."
                    })

            # 3. KIỂM TRA TÍNH HỢP THỨC CỦA SỐ THỨ TỰ VĂN BẢN (ĐIỀU 8 NGHỊ ĐỊNH 30)
            # Theo Nghị định 30: Số của văn bản là chữ số Ả Rập bắt đầu từ 01, không được là 0 hoặc 000.
            # Toàn bộ việc chống gian lận & truy nguyên bài nộp được đảm nhiệm độc lập bởi Thủy ấn số vô hình.
            num_match = re.search(r"^Số\s*:\s*([0-9A-Za-z]+)/", t, re.IGNORECASE)
            if num_match:
                found_num = num_match.group(1).strip()
                if not found_num.isdigit():
                    errors.append({
                        "issue": f"Số thứ tự của văn bản ({found_num}) phải được ghi bằng chữ số Ả-rập theo Điều 8 Nghị định 30.",
                        "fix": "Sửa phần số trước dấu gạch chéo thành chữ số (Ví dụ: 'Số: 01/...', 'Số: 12/...')."
                    })
                elif int(found_num) == 0:
                    errors.append({
                        "issue": f"Số thứ tự của văn bản ({found_num}) không hợp lệ: Theo Điều 8 Nghị định 30, số của văn bản bắt đầu từ số 01 vào ngày đầu năm, không thể là số 0 hoặc 000.",
                        "fix": "Sửa lại số ban hành hợp lệ bắt đầu từ 01 (Ví dụ: 'Số: 01/...', 'Số: 12/...')."
                    })

        font, size, bold, italic = self._get_dominant_font_and_size(p_so)
        if bold:
            errors.append({"issue": "Số, ký hiệu văn bản là chữ in thường, KHÔNG in đậm.", "fix": "Bỏ in đậm dòng Số, ký hiệu (Ctrl + B)."})
        if italic:
            errors.append({"issue": "Số, ký hiệu văn bản là chữ đứng, KHÔNG in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I)."})
        # Cỡ chữ Số ký hiệu: Theo Phụ lục I Nghị định 30, Ô 3 chỉ có duy nhất một cỡ chữ 13pt
        if size != 13.0:
            errors.append({
                "issue": f"Cỡ chữ Số, ký hiệu văn bản (Ô 3) bắt buộc phải là 13pt (Hiện tại: {size}pt). Theo Phụ lục I Nghị định 30, Ô 3 chỉ có duy nhất một cỡ chữ là 13.",
                "fix": "Chỉnh cỡ chữ dòng 'Số: ...' về đúng 13."
            })
        if p_so.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
            errors.append({"issue": "Số và ký hiệu văn bản chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

        return {
            "box_id": 3,
            "name": "Ô 3: Số và ký hiệu văn bản",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 4: ĐỊA DANH, NGÀY THÁNG NĂM
    # =========================================================================
    def check_box_4_dia_danh(self, p_dia_danh, same_row=True):
        errors = []
        if not p_dia_danh:
            return {
                "box_id": 4,
                "name": "Ô 4: Địa danh, ngày, tháng, năm",
                "passed": False,
                "errors": [{"issue": "Không tìm thấy dòng Địa danh, ngày tháng năm ở Hàng 2 Cột 2 của Bảng đầu trang.", "fix": "Trình bày địa danh ngày tháng tại Dòng 2 Cột 2 của Bảng đầu trang."}]
            }

        t = self._clean_text(p_dia_danh)

        # Chữ 'Tp.' được viết tắt (Tp. Hồ Chí Minh / TP. Hồ Chí Minh / Tp.Hồ Chí Minh), 
        # nhưng tên địa danh không được viết tắt thành 'HCM', 'HN', 'ĐN'
        if re.search(r"\b(HCM|H\.C\.M|HN|ĐN)\b", t, re.IGNORECASE):
            errors.append({
                "issue": "Tên địa danh không được viết tắt thành 'HCM' (Chữ 'Tp.' được phép viết tắt, nhưng địa danh 'Hồ Chí Minh' không được viết tắt).",
                "fix": "Sửa lại thành 'Tp. Hồ Chí Minh' (hoặc 'Thành phố Hồ Chí Minh')."
            })

        # Kiểm tra viết hoa tên địa danh theo Mục III Phụ lục II NĐ 30
        if "," in t:
            dia_danh_str = t.split(",", 1)[0].strip()
            if re.match(r"^tp\.", dia_danh_str) or re.match(r"^thành phố", dia_danh_str):
                errors.append({
                    "issue": "Chữ cái đầu của địa danh phải viết hoa (Ví dụ: 'Tp.' hoặc 'Thành phố').",
                    "fix": "Sửa lại thành 'Tp. Hồ Chí Minh' (hoặc 'Thành phố Hồ Chí Minh')."
                })
            if "hồ chí minh" in dia_danh_str:
                errors.append({
                    "issue": "Tên địa danh 'Hồ Chí Minh' phải viết hoa chữ cái đầu theo Mục III Phụ lục II NĐ 30.",
                    "fix": "Sửa 'hồ chí minh' thành 'Hồ Chí Minh'."
                })
        else:
            errors.append({"issue": "Sau địa danh phải có dấu phẩy ','.", "fix": "Thêm dấu phẩy sau địa danh (Ví dụ: 'Thành phố Hồ Chí Minh, ngày...')."})

        if not same_row:
            errors.append({
                "issue": "Địa danh, ngày tháng năm phải nằm cùng 1 hàng ngang với Số và ký hiệu văn bản (Dòng 2 của Bảng đầu trang).",
                "fix": "Đặt Ô 3 và Ô 4 nằm cùng 1 hàng (Row 2) trong Bảng đầu trang."
            })

        day_match = re.search(r"ngày\s+(\d+)", t)
        if day_match:
            d = int(day_match.group(1))
            if d < 10 and not day_match.group(1).startswith("0"):
                errors.append({"issue": f"Ngày {d} nhỏ hơn 10 nhưng chưa thêm số 0 phía trước.", "fix": f"Sửa 'ngày {d}' thành 'ngày 0{d}'."})

        month_match = re.search(r"tháng\s+(\d+)", t)
        if month_match:
            m = int(month_match.group(1))
            if m < 3 and not month_match.group(1).startswith("0"):
                errors.append({"issue": f"Tháng {m} nhỏ hơn 3 nhưng chưa thêm số 0 phía trước.", "fix": f"Sửa 'tháng {m}' thành 'tháng 0{m}'."})

        font, size, bold, italic = self._get_dominant_font_and_size(p_dia_danh)
        if not italic:
            errors.append({"issue": "Địa danh, ngày tháng năm bắt buộc phải IN NGHIÊNG.", "fix": "Bôi đen và nhấn Ctrl + I để in nghiêng."})
        if bold:
            errors.append({"issue": "Địa danh, ngày tháng năm là chữ in thường, KHÔNG in đậm.", "fix": "Tắt in đậm (Ctrl + B)."})

        # ĐỒNG NHẤT CỠ CHỮ: 13 if SO_TRUOC, 14 if SO_SAU
        expected_dd_size = self.get_expected_size("dia_danh")
        if size != expected_dd_size:
            errors.append({
                "issue": f"Tính thống nhất cỡ chữ: Bạn chọn quy ước '{'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}', do đó Địa danh ngày tháng phải là cỡ {int(expected_dd_size)}pt (Hiện tại: {size}pt).",
                "fix": f"Chỉnh cỡ chữ Địa danh ngày tháng về đúng {int(expected_dd_size)}pt."
            })
        if p_dia_danh.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
            errors.append({"issue": "Địa danh, ngày tháng năm chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

        return {
            "box_id": 4,
            "name": "Ô 4: Địa danh, ngày, tháng, năm",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 5a / 5b: TÊN LOẠI & TRÍCH YẾU NỘI DUNG VĂN BẢN
    # =========================================================================
    def check_box_5_trich_yeu(self, p_type=None, p_trich_yeu=None, p_so=None, is_5b_in_table=True, p_trich_yeu_outside_extra=None, p_5b_table=None, p_trich_yeu_outside=None, outside_header_paras=None):
        errors = []
        is_cong_van = getattr(self, "is_cong_van", False) or (self.doc_type_id in ["cong_van_de_nghi", "bai_thu_hoach"])

        # Tương thích ngược các tham số
        if p_5b_table is None:
            if is_5b_in_table is True and p_trich_yeu is not None:
                p_5b_table = p_trich_yeu
        if p_trich_yeu_outside is None:
            if is_5b_in_table is False and p_trich_yeu is not None:
                p_trich_yeu_outside = p_trich_yeu
            elif p_trich_yeu_outside_extra is not None:
                p_trich_yeu_outside = p_trich_yeu_outside_extra

        outside_header_paras = outside_header_paras or []

        if is_cong_van:
            # =================================================================
            # CÔNG VĂN (SƠ ĐỒ 2 - HÌNH 2 NGHỊ ĐỊNH 30)
            # =================================================================
            # 1. KIỂM TRA VI PHẠM SƠ ĐỒ BỐ TRÍ: CÔNG VĂN KHÔNG CÓ Ô 5a
            # Quy tắc sư phạm cốt lõi: Đã sai sơ đồ bố trí thì TUYỆT ĐỐI KHÔNG HƯỚNG DẪN
            # CÁCH CHỈNH SỬA (không bắt in đậm, cỡ chữ, canh lề...), CHỈ YÊU CẦU BỎ (XÓA)
            # RA KHỎI SƠ ĐỒ VĂN BẢN!
            illegal_paras = []
            if p_type and p_type not in illegal_paras:
                illegal_paras.append(p_type)
            if p_trich_yeu_outside and p_trich_yeu_outside not in illegal_paras:
                illegal_paras.append(p_trich_yeu_outside)
            for p_out in outside_header_paras:
                if p_out not in illegal_paras:
                    illegal_paras.append(p_out)

            for p_ill in illegal_paras:
                t_ill = self._clean_text(p_ill)
                if t_ill:
                    if p_ill == p_type or "CÔNG VĂN" in t_ill.upper():
                        errors.append({
                            "issue": f"Sai sơ đồ bố trí theo Nghị định 30 (Sơ đồ 2 - Hình 2): Đối với Công văn thì KHÔNG CÓ TÊN LOẠI (Ô 5a). Bài làm xuất hiện dòng tên loại '{t_ill[:60]}' ở giữa trang ngoài bảng.",
                            "fix": "Bỏ (xóa) dòng chữ này ra khỏi sơ đồ văn bản. Sau Bảng đầu trang, Công văn bắt đầu ngay bằng Ô 9a (Kính gửi) và phần Nội dung (Ô 6)."
                        })
                    else:
                        errors.append({
                            "issue": f"Sai sơ đồ bố trí theo Nghị định 30 (Sơ đồ 2 - Hình 2): Đối với Công văn thì không được có dòng trích yếu đặt ở giữa trang ngoài bảng ('{t_ill[:60]}...').",
                            "fix": "Bỏ (xóa) dòng chữ này ra khỏi sơ đồ văn bản. Trích yếu 'V/v ...' của Công văn (Ô 5b) bắt buộc phải nằm trong Bảng đầu trang tại Dòng 2 Cột 1 ngay dưới Ô 3."
                        })

            # 2. KIỂM TRA Ô 5b TRONG BẢNG ĐẦU TRANG (DÒNG 2, CỘT 1 DƯỚI Ô 3)
            if not p_5b_table:
                # Báo rõ ràng lỗi "Thiếu Ô 5b"
                errors.append({
                    "issue": "Thiếu Ô 5b: Trích yếu nội dung Công văn (V/v).",
                    "fix": "Trình bày trích yếu nội dung công văn (bắt đầu bằng 'V/v ...') tại Dòng 2, Cột 1 của Bảng đầu trang (ngay dưới Ô 3 Số và ký hiệu văn bản, cách dòng 6pt)."
                })
            else:
                # Chỉ khi Ô 5b ĐÃ CÓ trong bảng mới kiểm tra các tiêu chuẩn định dạng của Ô 5b
                t_5b = self._clean_text(p_5b_table)
                if not t_5b.startswith("V/v"):
                    errors.append({
                        "issue": "Trích yếu công văn (Ô 5b) phải bắt đầu bằng 'V/v'.",
                        "fix": "Thêm tiền tố 'V/v ' vào đầu câu trích yếu (Ví dụ: 'V/v đề nghị hỗ trợ kinh phí')."
                    })

                font_5b, size_5b, bold_5b, italic_5b = self._get_dominant_font_and_size(p_5b_table)
                expected_5b_size = self.get_expected_size("trich_yeu_5b")
                if size_5b != expected_5b_size:
                    errors.append({
                        "issue": f"Tính thống nhất cỡ chữ: Theo quy ước '{'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}', trích yếu công văn (V/v) phải là cỡ {int(expected_5b_size)}pt (Hiện tại: {size_5b}pt).",
                        "fix": f"Chỉnh cỡ chữ trích yếu V/v về đúng {int(expected_5b_size)}pt."
                    })

                if bold_5b:
                    errors.append({
                        "issue": "Trích yếu công văn (Ô 5b) là chữ in thường đứng, KHÔNG in đậm.",
                        "fix": "Bỏ in đậm (Ctrl + B)."
                    })

                if italic_5b:
                    errors.append({
                        "issue": "Trích yếu công văn là chữ đứng, KHÔNG in nghiêng.",
                        "fix": "Tắt in nghiêng (Ctrl + I)."
                    })

                if p_5b_table.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
                    errors.append({
                        "issue": "Trích yếu công văn chưa được canh giữa dưới Số và ký hiệu.",
                        "fix": "Nhấn Ctrl + E để canh giữa."
                    })

                sp_before = getattr(p_5b_table.paragraph_format.space_before, "pt", 0) or 0
                sp_after_so = getattr(p_so.paragraph_format.space_after, "pt", 0) if p_so else 0
                if sp_before < 5 and sp_after_so < 5:
                    errors.append({
                        "issue": "Trích yếu công văn (V/v) cần cách dòng 6pt so với số và ký hiệu văn bản.",
                        "fix": "Chọn dòng V/v ➔ Vào Paragraph ➔ Spacing Before: chọn 6pt (hoặc Space After của dòng Số: 6pt)."
                    })

            return {
                "box_id": "5b",
                "name": "Ô 5b: Trích yếu nội dung Công văn (V/v)",
                "passed": len(errors) == 0,
                "errors": errors
            }
        else:
            # =================================================================
            # VĂN BẢN CÓ TÊN LOẠI: THÔNG BÁO, TỜ TRÌNH, BÁO CÁO, BÀI THU HOẠCH
            # (SƠ ĐỒ 1 & 3 - HÌNH 1 & HÌNH 3 NGHỊ ĐỊNH 30)
            # =================================================================
            if p_5b_table:
                errors.append({
                    "issue": "Sai sơ đồ bố trí theo Nghị định 30 (Sơ đồ 1 & 3): Văn bản có tên loại (Thông báo, Tờ trình, Báo cáo, Bài thu hoạch) không trình bày trích yếu trong Bảng đầu trang (Ô 5b). Trích yếu (Ô 5a) bắt buộc phải nằm ngoài bảng, căn giữa trang ngay dưới Tên loại văn bản.",
                    "fix": "Bỏ (xóa) dòng trích yếu trong Bảng đầu trang ra khỏi sơ đồ văn bản và trình bày trích yếu (Ô 5a) ở giữa trang dưới Tên loại văn bản."
                })

            if not p_type:
                errors.append({
                    "issue": "Thiếu Tên loại văn bản: Chưa có Tên loại văn bản (THÔNG BÁO, TỜ TRÌNH, BÁO CÁO hoặc BÀI THU HOẠCH) ở ngoài bảng, giữa trang.",
                    "fix": "Thêm tên loại văn bản viết in hoa, in đậm, căn giữa."
                })
            else:
                t_type = self._clean_text(p_type)
                if t_type != t_type.upper():
                    errors.append({"issue": "Tên loại văn bản phải viết IN HOA toàn bộ.", "fix": "Chuyển thành chữ IN HOA (UPPERCASE)."})
                font_t, size_t, bold_t, italic_t = self._get_dominant_font_and_size(p_type)
                if not bold_t:
                    errors.append({"issue": "Tên loại văn bản phải IN ĐẬM.", "fix": "Nhấn Ctrl + B để in đậm tên loại."})
                if italic_t:
                    errors.append({"issue": "Tên loại văn bản là chữ đứng, KHÔNG in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I)."})

                expected_5a_size = self.get_expected_size("ten_loai_5a")
                if size_t != expected_5a_size:
                    errors.append({
                        "issue": f"Tính thống nhất cỡ chữ: Bạn chọn quy ước '{'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}', do đó Tên loại phải là cỡ {int(expected_5a_size)}pt (Hiện tại: {size_t}pt).",
                        "fix": f"Chỉnh cỡ chữ tên loại về đúng {int(expected_5a_size)}pt."
                    })
                if p_type.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
                    errors.append({"issue": "Tên loại văn bản chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

            if not p_trich_yeu_outside:
                errors.append({
                    "issue": "Thiếu Trích yếu nội dung văn bản (Ô 5a) đặt dưới Tên loại văn bản.",
                    "fix": "Thêm dòng trích yếu nội dung (bắt đầu bằng 'Về việc...' hoặc 'Về...') đặt dưới Tên loại văn bản."
                })
            else:
                t_y = self._clean_text(p_trich_yeu_outside)
                if t_y == t_y.upper() and len(t_y.split()) > 3:
                    errors.append({"issue": "Trích yếu nội dung văn bản có tên loại phải viết chữ in thường (không viết hoa toàn bộ).", "fix": "Chuyển thành chữ thường in đậm."})
                font_y, size_y, bold_y, italic_y = self._get_dominant_font_and_size(p_trich_yeu_outside)
                if not bold_y:
                    errors.append({"issue": "Trích yếu nội dung văn bản có tên loại phải IN ĐẬM.", "fix": "Bôi đen trích yếu và nhấn Ctrl + B để in đậm."})
                if italic_y:
                    errors.append({"issue": "Trích yếu nội dung văn bản có tên loại là chữ ĐỨNG, không in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I)."})
                if size_y != expected_5a_size:
                    errors.append({
                        "issue": f"Cỡ chữ Trích yếu phải thống nhất là {int(expected_5a_size)}pt (Hiện tại: {size_y}pt).",
                        "fix": f"Chỉnh cỡ chữ về đúng {int(expected_5a_size)}pt."
                    })
                if p_trich_yeu_outside.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
                    errors.append({"issue": "Trích yếu nội dung chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

            return {
                "box_id": "5a",
                "name": "Ô 5a: Tên loại & Trích yếu nội dung văn bản",
                "passed": len(errors) == 0,
                "errors": errors
            }

    # =========================================================================
    # QUY CHUẨN VIẾT HOA THEO PHỤ LỤC II NGHỊ ĐỊNH 30/2020/NĐ-CP
    # =========================================================================
    def check_decree30_capitalization(self, text, context_name="Nội dung văn bản"):
        """
        Kiểm tra các quy chuẩn viết hoa theo Phụ lục II Nghị định 30/2020/NĐ-CP:
        1. Mục IV: Viết hoa tên cơ quan, tổ chức (loại hình, chức năng/lĩnh vực, từ nối 'và' không viết hoa).
        2. Mục III: Viết hoa tên địa lý (Thành phố Hồ Chí Minh, tỉnh Bến Tre...).
        3. Mục I: Viết hoa vì phép đặt câu.
        """
        errors = []
        if not text or len(text.strip()) < 3:
            return errors

        # 1. QUY TẮC TỪ NỐI 'VÀ' TRONG TÊN CƠ QUAN (Mục IV.1 Phụ lục II)
        # Các từ chỉ loại hình cơ quan/tổ chức viết hoa, nhưng từ nối 'và' viết thường
        va_matches = re.finditer(
            r'\b(Bộ|Sở|Ban|Phòng|Khoa|Trường|Hội đồng)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)\s+(Và)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)\b',
            text
        )
        for m in va_matches:
            full = m.group(0)
            fixed = full.replace(' Và ', ' và ')
            errors.append({
                "issue": f"{context_name}: Tên cơ quan '{full}' viết hoa sai từ nối 'Và'. Theo Mục IV.1 Phụ lục II Nghị định 30, từ nối 'và' trong tên cơ quan KHÔNG được viết hoa.",
                "fix": f"Sửa chữ 'Và' thành 'và': '{fixed}'."
            })

        # 2. CƠ QUAN CÔNG AN / CÔNG AN CÁC CẤP (Mục IV.1 Phụ lục II)
        ca_matches = re.finditer(
            r'\b(công\s+an(\s+phường|\s+xã|\s+thị\s+trấn|\s+quận|\s+huyện|\s+thành\s+phố|\s+tỉnh)?\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*))\b',
            text
        )
        for m in ca_matches:
            full = m.group(0)
            fixed = 'Công an' + full[len('công an'):]
            errors.append({
                "issue": f"{context_name}: Lỗi viết hoa tên cơ quan theo Mục IV.1 Phụ lục II NĐ 30: Bạn viết '{full}'. Từ chỉ loại hình cơ quan 'Công an' bắt buộc phải viết hoa chữ cái đầu.",
                "fix": f"Sửa lại đúng chuẩn: '{fixed}'."
            })

        # 3. ỦY BAN NHÂN DÂN / HỘI ĐỒNG NHÂN DÂN (Mục IV.1 Phụ lục II)
        ub_matches = re.finditer(
            r'\b((?:ủy|uỷ)\s+ban\s+nhân\s+dân(\s+phường|\s+xã|\s+thị\s+trấn|\s+quận|\s+huyện|\s+thành\s+phố|\s+tỉnh)?(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)\b',
            text
        )
        for m in ub_matches:
            full = m.group(0)
            if full.startswith('ủy ban') or full.startswith('uỷ ban'):
                errors.append({
                    "issue": f"{context_name}: Lỗi viết hoa tên cơ quan theo Mục IV.1 Phụ lục II NĐ 30: Từ chỉ loại hình 'Ủy ban nhân dân' phải viết hoa chữ cái đầu (Đang viết: '{full}').",
                    "fix": f"Sửa chữ thường thành: 'Ủy ban nhân dân'."
                })

        hd_matches = re.finditer(
            r'\b(hội\s+đồng\s+nhân\s+dân(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+)*)\b',
            text
        )
        for m in hd_matches:
            full = m.group(0)
            if full.startswith('hội đồng'):
                errors.append({
                    "issue": f"{context_name}: Lỗi viết hoa tên cơ quan theo Mục IV.1 Phụ lục II NĐ 30: Từ chỉ loại hình 'Hội đồng nhân dân' phải viết hoa chữ cái đầu.",
                    "fix": f"Sửa chữ thường thành: 'Hội đồng nhân dân'."
                })

        # 4. DANH SÁCH CÁC CƠ QUAN, TỔ CHỨC CỤ THỂ THƯỜNG GẶP (Mục IV.1 Phụ lục II)
        orgs = [
            (r'\b(bộ\s+giáo\s+dục\s+và\s+đào\s+tạo)\b', 'Bộ Giáo dục và Đào tạo'),
            (r'\b(bộ\s+khoa\s+học\s+và\s+công\s+nghệ)\b', 'Bộ Khoa học và Công nghệ'),
            (r'\b(bộ\s+tài\s+nguyên\s+và\s+môi\s+trường)\b', 'Bộ Tài nguyên và Môi trường'),
            (r'\b(bộ\s+giao\s+thông\s+vận\s+tải)\b', 'Bộ Giao thông Vận tải'),
            (r'\b(bộ\s+y\s+tế)\b', 'Bộ Y tế'),
            (r'\b(bộ\s+tài\s+chính)\b', 'Bộ Tài chính'),
            (r'\b(bộ\s+nội\s+vụ)\b', 'Bộ Nội vụ'),
            (r'\b(bộ\s+công\s+thương)\b', 'Bộ Công Thương'),
            (r'\b(sở\s+giao\s+thông\s+vận\s+tải)\b', 'Sở Giao thông Vận tải'),
            (r'\b(sở\s+giáo\s+dục\s+và\s+đào\s+tạo)\b', 'Sở Giáo dục và Đào tạo'),
            (r'\b(sở\s+tài\s+chính)\b', 'Sở Tài chính'),
            (r'\b(sở\s+y\s+tế)\b', 'Sở Y tế'),
            (r'\b(sở\s+tài\s+nguyên\s+và\s+môi\s+trường)\b', 'Sở Tài nguyên và Môi trường'),
            (r'\b(ban\s+giám\s+hiệu)\b', 'Ban Giám hiệu'),
            (r'\b(ban\s+giám\s+đốc)\b', 'Ban Giám đốc'),
            (r'\b(trường\s+đại\s+học\s+nguyễn\s+tất\s+thành)\b', 'Trường Đại học Nguyễn Tất Thành'),
            (r'\b(phòng\s+đào\s+tạo)\b', 'Phòng Đào tạo'),
            (r'\b(phòng\s+tài\s+chính\s*[-–—]\s*kế\s+toán)\b', 'Phòng Tài chính - Kế toán'),
            (r'\b(phòng\s+tổ\s+chức\s*[-–—]\s*nhân\s+sự)\b', 'Phòng Tổ chức - Nhân sự'),
            (r'\b(phòng\s+quản\s+trị\s+thiết\s+bị)\b', 'Phòng Quản trị thiết bị'),
            (r'\b(phòng\s+nhân\s+sự)\b', 'Phòng Nhân sự'),
            (r'\b(phòng\s+an\s+ninh)\b', 'Phòng An ninh'),
            (r'\b(khoa\s+công\s+nghệ\s+thông\s+tin)\b', 'Khoa Công nghệ thông tin'),
            (r'\b(đoàn\s+thanh\s+niên)\b', 'Đoàn Thanh niên'),
            (r'\b(ban\s+thường\s+vụ\s+đoàn\s+trường)\b', 'Ban Thường vụ Đoàn trường'),
            (r'\b(trung\s+tâm\s+đào\s+tạo\s+kỹ\s+năng\s+nghề)\b', 'Trung tâm Đào tạo Kỹ năng nghề'),
            (r'\b(bộ\s+môn\s+kỹ\s+thuật\s+phần\s+mềm)\b', 'Bộ môn Kỹ thuật phần mềm'),
            (r'\b(văn\s+phòng\s+hội\s+đồng\s+thi)\b', 'Văn phòng Hội đồng thi'),
            (r'\b(ban\s+thư\s+ký\s+hội\s+đồng)\b', 'Ban Thư ký Hội đồng'),
            (r'\b(ban\s+giám\s+khảo)\b', 'Ban Giám khảo'),
            (r'\b(đảng\s+ủy)\b', 'Đảng ủy'),
            (r'\b(thành\s+phố\s+hồ\s+chí\s+minh)\b', 'Thành phố Hồ Chí Minh'),
            (r'\b(thủ\s+đô\s+hà\s+nội)\b', 'Thủ đô Hà Nội')
        ]
        for pattern, canonical in orgs:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                full = m.group(0)
                if full != canonical:
                    # Bỏ qua nếu đã trùng lỗi từ nối 'Và' báo ở mục 1
                    if ' và ' in canonical and full == canonical.replace(' và ', ' Và '):
                        continue
                    errors.append({
                        "issue": f"{context_name}: Lỗi viết hoa tên cơ quan, tổ chức theo Mục IV.1 Phụ lục II NĐ 30: Bạn viết '{full}' là chưa đúng quy chuẩn.",
                        "fix": f"Sửa lại đúng chuẩn: '{canonical}'."
                    })

        return errors

    def check_decree30_sentence_capitalization(self, paragraphs, context_name="Ô 6: Nội dung văn bản"):
        """
        Kiểm tra quy tắc viết hoa vì phép đặt câu theo Mục I Phụ lục II NĐ 30:
        - Viết hoa chữ cái đầu khi xuống dòng (đầu đoạn, đầu gạch đầu dòng, đầu mục 1., 2., a), b)...).
        - Viết hoa chữ cái đầu sau dấu chấm câu (.), (!), (?).
        """
        errors = []
        for p in paragraphs:
            text = self._clean_text(p)
            if not text or len(text) < 5 or "[Nội dung văn bản:" in text:
                continue

            # 1. Tách tiền tố (đầu mục, gạch đầu dòng, số thứ tự, ngoặc kép)
            m_prefix = re.match(r'^((?:[-–—*•+]|\d+[\.\)]|[a-zA-Z][\.\)]|["“\'«])\s*)(.*)$', text)
            if m_prefix:
                prefix, body = m_prefix.groups()
            else:
                prefix, body = '', text

            # Kiểm tra chữ cái đầu câu / đầu dòng
            if body and body[0].islower():
                words = body.split()
                first_w = words[0] if words else body[:10]
                errors.append({
                    "issue": f"{context_name}: Lỗi viết hoa vì phép đặt câu (Mục I Phụ lục II NĐ 30): Chữ cái đầu câu khi xuống dòng phải viết hoa (Đang viết chữ thường: '{first_w}...').",
                    "fix": f"Viết hoa chữ cái đầu câu: '{first_w.capitalize()}'."
                })

            # 2. Kiểm tra sau dấu chấm câu (.), (!), (?) bên trong câu
            safe_body = re.sub(r'\b(Tp|TP|ThS|TS|PGS|GS|v\.v|NĐ|TT|TTr|CV|TB)\.', r'\1_DOT_', body)
            safe_body = re.sub(r'(\d+)\.(\d+)', r'\1_DEC_\2', safe_body)
            period_matches = re.finditer(r'(?<=[.!?])\s+([a-zàáảãạăắằẳẵặâấầẩẫậđèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵ][\w\d]*)', safe_body)
            for pm in period_matches:
                w = pm.group(1)
                errors.append({
                    "issue": f"{context_name}: Lỗi viết hoa vì phép đặt câu (Mục I Phụ lục II NĐ 30): Sau dấu chấm câu phải viết hoa chữ cái đầu của từ tiếp theo (Đang viết: '{w}').",
                    "fix": f"Viết hoa chữ cái đầu: '{w.capitalize()}'."
                })

        return errors

    # =========================================================================
    # KIỂM TRA QUY TẮC KHOẢNG CÁCH TRỐNG KHI SOẠN THẢO (PUNCTUATION SPACING)
    # Dựa trên bài giảng chính thức NTTU & Nghị định 30/2020/NĐ-CP
    # =========================================================================
    def check_decree30_punctuation_spacing(self, text, context_name):
        """
        Kiểm tra quy tắc khoảng cách trống:
        1. Dấu hai chấm (:), dấu phẩy (,), dấu chấm phẩy (;): không cách trước, 1 cách sau.
        2. Dấu chấm (.), dấu than (!), dấu hỏi (?): không cách trước, 1 cách sau.
        3. Dấu ngoặc đơn ( ): không cách bên trong, 1 cách bên ngoài.
        """
        errors = []
        if not text:
            return errors

        # Bỏ qua dòng thông báo hệ thống / placeholder
        if "[Nội dung văn bản:" in text or "tự nhập theo nội dung" in text:
            return errors

        # 1. DẤU HAI CHẤM (:)
        # 1.1. Thiếu khoảng trắng sau dấu hai chấm (ví dụ: 'Lưu:VT.', 'Số:01', 'Kính gửi:Ban')
        # Loại trừ URL 'http:', 'https:'
        m_col_no_space = re.search(r'(?<!https)(?<!http)\b([a-zA-ZÀ-ỹ]+):([^\s\.,;]{1,15})', text)
        if m_col_no_space:
            sample = m_col_no_space.group(0)
            word_before = m_col_no_space.group(1)
            word_after = m_col_no_space.group(2)
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu hai chấm): Sau dấu hai chấm (:) phải có 1 khoảng trắng (dấu cách) (Đang viết dính liền: '{sample}').",
                "fix": f"Thêm dấu cách sau dấu hai chấm (Sửa thành: '{word_before}: {word_after}')."
            })
        # 1.2. Thừa khoảng trắng trước dấu hai chấm (ví dụ: 'Lưu : VT', 'Số : 01')
        m_col_space_before = re.search(r'\b([a-zA-ZÀ-ỹ]+)\s+:', text)
        if m_col_space_before:
            word_before = m_col_space_before.group(1)
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu hai chấm): Không chừa khoảng trắng trước dấu hai chấm (:) (Đang viết: '{word_before} :').",
                "fix": f"Xóa khoảng trắng trước dấu hai chấm (Sửa thành: '{word_before}:')."
            })

        # 2. DẤU PHẨY (,)
        # 2.1. Thiếu khoảng trắng sau dấu phẩy (loại trừ số thập phân như 3,5 hoặc 15,5)
        m_comma_no_space = re.search(r',([a-zA-ZÀ-ỹ][\wÀ-ỹ]*)', text)
        if m_comma_no_space:
            sample = m_comma_no_space.group(0)
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu phẩy): Sau dấu phẩy (,) phải có 1 khoảng trắng (dấu cách) (Đang viết dính liền: '{sample}').",
                "fix": f"Thêm dấu cách sau dấu phẩy (Sửa thành: ', {m_comma_no_space.group(1)}')."
            })
        # 2.2. Thừa khoảng trắng trước dấu phẩy
        m_comma_space_before = re.search(r'([a-zA-ZÀ-ỹ0-9%])\s+,', text)
        if m_comma_space_before:
            sample = m_comma_space_before.group(0)
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu phẩy): Không chừa khoảng trắng trước dấu phẩy (,) (Đang viết: '{sample}').",
                "fix": "Đặt dấu phẩy sát ngay ký tự đứng trước, không chừa dấu cách phía trước."
            })

        # 3. DẤU CHẤM PHẨY (;)
        # 3.1. Thiếu khoảng trắng sau dấu chấm phẩy
        m_semi_no_space = re.search(r';([a-zA-ZÀ-ỹ][\wÀ-ỹ]*)', text)
        if m_semi_no_space:
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu chấm phẩy): Sau dấu chấm phẩy (;) phải có 1 khoảng trắng (dấu cách).",
                "fix": f"Thêm dấu cách sau dấu chấm phẩy (Sửa thành: '; {m_semi_no_space.group(1)}')."
            })
        # 3.2. Thừa khoảng trắng trước dấu chấm phẩy
        if re.search(r'([a-zA-ZÀ-ỹ0-9])\s+;', text):
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu chấm phẩy): Không chừa khoảng trắng trước dấu chấm phẩy (;).",
                "fix": "Đặt dấu chấm phẩy sát ngay chữ đứng trước, không chừa dấu cách phía trước."
            })

        # 4. DẤU CHẤM (.)
        # 4.1. Thừa khoảng trắng trước dấu chấm
        m_dot_space = re.search(r'([a-zA-ZÀ-ỹ0-9%])\s+\.', text)
        if m_dot_space:
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống (Dấu chấm): Không chừa khoảng trắng trước dấu chấm (.).",
                "fix": "Đặt dấu chấm sát ngay ký tự đứng trước, không chừa dấu cách phía trước."
            })

        # 5. DẤU CHẤM HỎI (?) VÀ CHẤM THAN (!)
        if re.search(r'\s+[!?]', text):
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống: Không chừa khoảng trắng trước dấu chấm hỏi (?) hoặc chấm than (!).",
                "fix": "Đặt dấu chấm hỏi/chấm than sát ngay ký tự đứng trước."
            })

        # 6. DẤU NGOẶC ĐƠN ( ... )
        if re.search(r'\(\s+[a-zA-ZÀ-ỹ0-9]', text):
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống: Không chừa khoảng trắng sát phía trong mở ngoặc đơn '('.",
                "fix": "Viết chữ liền sát sau dấu mở ngoặc '(' (Ví dụ: '(nếu có)' thay vì '( nếu có)')."
            })
        if re.search(r'[a-zA-ZÀ-ỹ0-9]\s+\)', text):
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống: Không chừa khoảng trắng sát phía trong đóng ngoặc đơn ')'.",
                "fix": "Viết chữ liền sát trước dấu đóng ngoặc ')' (Ví dụ: '(nếu có)' thay vì '(nếu có )')."
            })
        if re.search(r'[a-zA-ZÀ-ỹ0-9]\(', text):
            errors.append({
                "issue": f"{context_name}: Quy tắc khoảng cách trống: Phía trước dấu mở ngoặc đơn '(' phải có 1 khoảng trắng (dấu cách).",
                "fix": "Thêm dấu cách trước dấu mở ngoặc '('."
            })

        return errors

    # =========================================================================
    # Ô 6: NỘI DUNG VĂN BẢN
    # =========================================================================
    def get_box6_text(self) -> str:
        """Lấy toàn bộ nội dung văn bản Ô 6 đã được làm sạch ký tự vô hình"""
        if not hasattr(self, "body_paragraphs") or not self.body_paragraphs:
            return ""
        lines = []
        for p in self.body_paragraphs:
            t = self._clean_text(p)
            if t and "[Nội dung văn bản:" not in t and "tự nhập theo nội dung" not in t:
                lines.append(t)
        return "\n".join(lines)

    def check_box_6_noi_dung(self, body_paragraphs):
        errors = []
        if not body_paragraphs:
            return {
                "box_id": 6,
                "name": "Ô 6: Nội dung văn bản",
                "passed": False,
                "errors": [{"issue": "Không tìm thấy các đoạn văn nội dung chính.", "fix": "Đảm bảo đã gõ phần nội dung bài tập vào văn bản."}]
            }

        for p in body_paragraphs:
            t = self._clean_text(p)
            if "[Nội dung văn bản:" in t or "tự nhập theo nội dung" in t:
                errors.append({
                    "issue": "Bạn vẫn để nguyên dòng thông báo '[Nội dung văn bản...]' mà chưa gõ nội dung thực tế.",
                    "fix": "Xóa dòng thông báo mẫu và gõ nội dung bài tập theo đúng bài giảng của Giảng viên trên lớp."
                })
                break

        not_justified_count = 0
        no_indent_count = 0
        no_list_indent_count = 0
        wrong_font_count = 0
        wrong_size_count = 0
        wrong_spacing_count = 0
        wrong_line_spacing_count = 0

        expected_body_size = self.get_expected_size("noi_dung")

        for p in body_paragraphs:
            raw_text = p.text
            text = self._clean_text(p)
            if not text or "[Nội dung văn bản:" in text or "tự nhập theo nội dung" in text:
                continue

            # Nhận diện nếu là dòng danh sách liệt kê (Bullet / Numbered List / Gạch đầu dòng / Dấu cộng)
            is_list_item = (
                bool(p._p.xpath("./w:pPr/w:numPr")) or 
                bool(p.style and ("List" in p.style.name or "Bullet" in p.style.name or "Number" in p.style.name)) or
                bool(re.match(r"^\s*([0-9]+[\.\)]|[a-zA-Z][\.\)]|\([0-9a-zA-Z]+\)|[ivxIVX]+[\.\)]|[-+*•⁃‣○●■□▪▫–—])\s*", text))
            )

            if is_list_item:
                # KIỂM TRA QUY TẮC: Các dòng gạch đầu dòng / bullet / danh sách liệt kê phải lùi vào so với ý chính
                is_indented = False
                # 1. Định dạng Bullets / Numbering của Word (w:numPr tự động có lề thụt danh sách)
                if bool(p._p.xpath("./w:pPr/w:numPr")):
                    is_indented = True

                # 2. Thuộc tính thụt lề: left_indent hoặc first_line_indent >= 0.2 inch (~0.5 cm)
                pf = p.paragraph_format
                if not is_indented:
                    if pf.left_indent is not None and pf.left_indent.inches >= 0.2:
                        is_indented = True
                    elif pf.first_line_indent is not None and pf.first_line_indent.inches >= 0.2:
                        is_indented = True

                # 3. Thẻ OpenXML w:ind (w:left hoặc w:firstLine >= 280 dxa ~ 0.2 inch)
                if not is_indented:
                    ind_elems = p._p.xpath("./w:pPr/w:ind")
                    if ind_elems:
                        ind = ind_elems[0]
                        w_left = ind.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}left")
                        w_first = ind.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}firstLine")
                        if w_left and int(w_left) >= 280:
                            is_indented = True
                        elif w_first and int(w_first) >= 280:
                            is_indented = True

                # 4. Thụt dòng thủ công bằng phím Tab (\t) hoặc từ 2 khoảng trắng trở lên
                if not is_indented:
                    if raw_text.startswith("\t") or re.match(r"^[ ]{2,}", raw_text):
                        is_indented = True
                    elif p.runs and (p.runs[0].text.startswith("\t") or re.match(r"^[ ]{2,}", p.runs[0].text)):
                        is_indented = True

                if not is_indented:
                    no_list_indent_count += 1

                # Nếu là dòng danh sách dài (>= 40 ký tự), kiểm tra thêm căn đều hai lề (Justify)
                if len(text) >= 40 and p.alignment != WD_ALIGN_PARAGRAPH.JUSTIFY:
                    not_justified_count += 1

            else:
                # Đoạn văn xuôi thông thường (chỉ kiểm tra nếu độ dài >= 40 để tránh các dòng chào/kết ngắn)
                if len(text) >= 40:
                    # 1. Dàn đều cả hai lề (Justify: Ctrl + J)
                    if p.alignment != WD_ALIGN_PARAGRAPH.JUSTIFY:
                        not_justified_count += 1

                    # 2. Thụt đầu dòng 1 - 1.27 cm (First line indent)
                    indent = p.paragraph_format.first_line_indent
                    if indent is None or indent.inches < 0.35:
                        if not (raw_text.startswith("    ") or raw_text.startswith("\t")):
                            no_indent_count += 1

            # 3. Font Times New Roman & Cỡ chữ thống nhất
            if len(text) >= 40:
                font, size, bold, italic = self._get_dominant_font_and_size(p)
                if font and "Times New Roman" not in font and "times new roman" not in font.lower():
                    wrong_font_count += 1
                if size != expected_body_size:
                    wrong_size_count += 1

                # 4. Khoảng cách giữa các đoạn văn (tối thiểu 6pt)
                sp_after = getattr(p.paragraph_format.space_after, "pt", 0) or 0
                sp_before = getattr(p.paragraph_format.space_before, "pt", 0) or 0
                if sp_after < 5 and sp_before < 5:
                    wrong_spacing_count += 1

                # 5. Khoảng cách giữa các dòng chữ (tối thiểu đơn, tối đa 1.5 dòng)
                line_sp = p.paragraph_format.line_spacing
                if line_sp is not None and isinstance(line_sp, float):
                    if line_sp < 0.95 or line_sp > 1.55:
                        wrong_line_spacing_count += 1

        if not_justified_count > 0:
            errors.append({
                "issue": f"Có {not_justified_count} đoạn văn nội dung chưa được căn đều hai lề (Justify).",
                "fix": "Bôi đen toàn bộ các đoạn văn thân bài và nhấn phím Ctrl + J."
            })
        if no_indent_count > 0:
            errors.append({
                "issue": f"Có {no_indent_count} đoạn văn dòng đầu tiên chưa thụt vào 1 - 1.27 cm (First line indent).",
                "fix": "Vào hộp thoại Paragraph ➔ mục Indentation ➔ Special chọn First line: 1.27 cm (hoặc dùng 1 phím Tab)."
            })
        if no_list_indent_count > 0:
            errors.append({
                "issue": f"Có {no_list_indent_count} dòng gạch đầu dòng / bullet / danh sách liệt kê chưa lùi vào so với ý chính.",
                "fix": "Các dòng danh sách liệt kê, gạch đầu dòng phải lùi vào trong so với ý chính (ví dụ dùng phím Tab, nút 'Increase Indent' / Tăng thụt lề trên thanh công cụ Word, hoặc dùng tính năng Bullets / Numbering)."
            })
        if wrong_font_count > 0:
            errors.append({
                "issue": "Nội dung văn bản chưa chuyển về đúng phông chữ Times New Roman.",
                "fix": "Chọn toàn bộ văn bản và đổi Font thành Times New Roman."
            })
        if wrong_size_count > 0:
            errors.append({
                "issue": f"Tính thống nhất cỡ chữ: Bạn chọn quy ước '{'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}', do đó toàn bộ Nội dung văn bản phải có cỡ chữ thống nhất là {int(expected_body_size)}pt.",
                "fix": f"Đặt cỡ chữ toàn bộ phần thân bài thành đúng {int(expected_body_size)}pt."
            })
        if wrong_spacing_count > 0:
            errors.append({
                "issue": "Khoảng cách giữa các đoạn văn bản phải tối thiểu 6pt.",
                "fix": "Vào hộp thoại Paragraph ➔ mục Spacing After đặt là 6pt."
            })
        if wrong_line_spacing_count > 0:
            errors.append({
                "issue": "Khoảng cách giữa các dòng chữ phải chọn tối thiểu cách dòng đơn (Single line), tối đa 1.5 dòng.",
                "fix": "Vào Paragraph ➔ Line spacing chọn Single hoặc 1.15 - 1.5 lines."
            })

        # 6. KIỂM TRA QUY TẮC VIẾT HOA THEO PHỤ LỤC II NGHỊ ĐỊNH 30/2020/NĐ-CP
        # 6.1. Viết hoa vì phép đặt câu (Mục I)
        sent_errs = self.check_decree30_sentence_capitalization(body_paragraphs, "Ô 6: Nội dung văn bản")
        errors.extend(sent_errs)

        # 6.2. Viết hoa tên cơ quan, tổ chức, địa danh trong nội dung (Mục IV & Mục III)
        for p in body_paragraphs:
            text_p = self._clean_text(p)
            if len(text_p) < 10 or "[Nội dung văn bản:" in text_p:
                continue
            cap_errs = self.check_decree30_capitalization(text_p, "Ô 6: Nội dung văn bản")
            errors.extend(cap_errs)

        # 6.3. Kiểm tra quy tắc khoảng cách trống trong nội dung văn bản (Dấu hai chấm, phẩy, chấm phẩy, chấm, than, hỏi, ngoặc)
        for p in body_paragraphs:
            text_p = self._clean_text(p)
            if len(text_p) < 5 or "[Nội dung văn bản:" in text_p:
                continue
            punc_errs = self.check_decree30_punctuation_spacing(text_p, "Ô 6: Nội dung văn bản")
            errors.extend(punc_errs)

        return {
            "box_id": 6,
            "name": "Ô 6: Nội dung văn bản",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 7 & 8: THẨM QUYỀN, CHỨC VỤ, CHỮ KÝ VÀ HỌ TÊN NGƯỜI KÝ
    # =========================================================================
    def check_box_7_8_chuc_vu_nguoi_ky(self, p_chuc_vu, p_ho_ten, empty_lines_sign=0, p_cq_ban_hanh=None):
        errors = []
        if not p_chuc_vu or not p_ho_ten:
            return {
                "box_id": 7,
                "name": "Ô 7 & 8: Chức vụ, Chữ ký và Họ tên người ký",
                "passed": False,
                "errors": [{"issue": "Chưa tìm thấy phần Chức vụ (7a) và Họ tên người ký (7b) ở Bảng cuối trang (Dòng 1, Cột 2).", "fix": "Trình bày Chức vụ (dòng trên) và Họ tên người ký (dòng dưới) ở cột phải Bảng cuối trang."}]
            }

        chuc_vu_paras = p_chuc_vu if isinstance(p_chuc_vu, list) else [p_chuc_vu]
        t_ho_ten = self._clean_text(p_ho_ten)
        expected_sign_size = self.get_expected_size("chuc_vu")

        # 1. KIỂM TRA ĐỊNH DẠNG CỦA TỪNG DÒNG CHỨC VỤ (Ô 7a)
        chuc_vu_lines = []
        for p_cv in chuc_vu_paras:
            raw_text_val = p_cv.text if hasattr(p_cv, "text") else str(p_cv)
            # Tách nếu người dùng gõ Shift+Enter hoặc \n trong cùng 1 paragraph
            for sub_line in raw_text_val.splitlines():
                s = self._clean_text(sub_line)
                if s:
                    chuc_vu_lines.append(s)
                    if s != s.upper():
                        errors.append({"issue": f"Dòng chức vụ '{s}' phải viết IN HOA toàn bộ (ví dụ: GIÁM ĐỐC, TRƯỞNG PHÒNG).", "fix": "Chuyển thành chữ IN HOA (UPPERCASE)."})

            font_c, size_c, bold_c, italic_c = self._get_dominant_font_and_size(p_cv)
            txt_cv = self._clean_text(p_cv)
            if not bold_c:
                errors.append({"issue": f"Chức vụ người ký ('{txt_cv}') phải IN ĐẬM.", "fix": "Nhấn Ctrl + B để in đậm chức vụ người ký."})
            if italic_c:
                errors.append({"issue": f"Chức vụ người ký ('{txt_cv}') là chữ đứng, KHÔNG in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I)."})

            if size_c != expected_sign_size:
                errors.append({
                    "issue": f"Tính thống nhất cỡ chữ: Bạn chọn quy ước '{'Số trước' if self.font_profile=='SO_TRUOC' else 'Số sau'}', do đó Chức vụ người ký phải là cỡ {int(expected_sign_size)}pt (Hiện tại: {size_c}pt).",
                    "fix": f"Chỉnh cỡ chữ chức vụ về đúng {int(expected_sign_size)}pt."
                })
            if p_cv.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
                errors.append({"issue": f"Chức vụ người ký ('{txt_cv}') chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

        # 2. KIỂM TRA THỂ THỨC ĐỀ KÝ ĐI KÈM TẠI 7a (KT., TL. HOẶC KÝ TRỰC TIẾP)
        if chuc_vu_lines:
            first_line = chuc_vu_lines[0].upper()
            
            # THỂ THỨC 1: KÝ THAY (KT.) - Dành cho cấp phó ký thay cấp trưởng
            if first_line.startswith("KT"):
                if not re.match(r"^KT\.\s*", first_line):
                    errors.append({
                        "issue": "Chữ viết tắt Ký thay phải có dấu chấm: 'KT.' (viết 'KT' không có dấu chấm là sai quy định).",
                        "fix": "Sửa thành 'KT. <CHỨC VỤ NGƯỜI ĐỨNG ĐẦU>' (Ví dụ: 'KT. GIÁM ĐỐC' hoặc 'KT. HIỆU TRƯỞNG')."
                    })
                if len(chuc_vu_lines) < 2:
                    errors.append({
                        "issue": "Thể thức đề ký 'KT.' (Ký thay) bắt buộc phải có 2 dòng: Dòng 1 ghi 'KT. <CHỨC VỤ NGƯỜI ĐỨNG ĐẦU>', Dòng 2 ghi chức vụ cấp phó trực tiếp ký (Ví dụ: 'PHÓ GIÁM ĐỐC' hoặc 'PHÓ HIỆU TRƯỞNG').",
                        "fix": "Thêm dòng chức vụ cấp phó dưới dòng KT. (Ví dụ: Dòng 1 'KT. GIÁM ĐỐC', Dòng 2 'PHÓ GIÁM ĐỐC')."
                    })
                else:
                    second_line = chuc_vu_lines[1].upper()
                    if not any(kw in second_line for kw in ["PHÓ", "CẤP PHÓ"]):
                        errors.append({
                            "issue": f"Thể thức Ký thay (KT.) chỉ dành cho cấp phó, do đó Dòng 2 phải là chức vụ cấp phó (Hiện tại: '{chuc_vu_lines[1]}').",
                            "fix": "Ghi đúng chức vụ cấp phó (Ví dụ: 'PHÓ GIÁM ĐỐC', 'PHÓ HIỆU TRƯỞNG')."
                        })

            # THỂ THỨC 2: THỪA LỆNH (TL.) - Dành cho cấp trưởng phòng / trung gian
            elif first_line.startswith("TL"):
                if not re.match(r"^TL\.\s*", first_line):
                    errors.append({
                        "issue": "Chữ viết tắt Thừa lệnh phải có dấu chấm: 'TL.' (viết 'TL' không có dấu chấm là sai quy định).",
                        "fix": "Sửa thành 'TL. <CHỨC VỤ NGƯỜI ĐỨNG ĐẦU>' (Ví dụ: 'TL. HIỆU TRƯỞNG' hoặc 'TL. GIÁM ĐỐC')."
                    })
                if len(chuc_vu_lines) < 2:
                    errors.append({
                        "issue": "Thể thức đề ký 'TL.' (Thừa lệnh) bắt buộc phải có 2 dòng: Dòng 1 ghi 'TL. <CHỨC VỤ NGƯỜI ĐỨNG ĐẦU>', Dòng 2 ghi chức vụ cấp trưởng phòng/đơn vị trực tiếp ký (Ví dụ: 'TRƯỞNG PHÒNG ĐÀO TẠO' hoặc 'TP. HÀNH CHÍNH').",
                        "fix": "Thêm dòng chức vụ cấp trưởng phòng dưới dòng TL. (Ví dụ: Dòng 1 'TL. HIỆU TRƯỞNG', Dòng 2 'TRƯỞNG PHÒNG ĐÀO TẠO')."
                    })
                else:
                    second_line = chuc_vu_lines[1].upper()
                    if any(kw in second_line for kw in ["PHÓ GIÁM ĐỐC", "PHÓ HIỆU TRƯỞNG"]):
                        errors.append({
                            "issue": "Cấp phó ký thay người đứng đầu phải dùng thể thức Ký thay ('KT.'), không dùng Thừa lệnh ('TL.').",
                            "fix": "Sửa 'TL.' thành 'KT.' (Ví dụ: 'KT. GIÁM ĐỐC' / 'PHÓ GIÁM ĐỐC')."
                        })

            # THỂ THỨC 3: THỪA ỦY QUYỀN (TUQ.)
            elif first_line.startswith("TUQ"):
                if not re.match(r"^TUQ\.\s*", first_line):
                    errors.append({"issue": "Chữ viết tắt Thừa ủy quyền phải có dấu chấm: 'TUQ.'", "fix": "Sửa thành 'TUQ. <CHỨC VỤ>'."})
                if len(chuc_vu_lines) < 2:
                    errors.append({"issue": "Thể thức đề ký 'TUQ.' (Thừa ủy quyền) bắt buộc có 2 dòng.", "fix": "Thêm dòng chức vụ người được ủy quyền."})

            # Thể thức Thay mặt (TM.) không áp dụng trong hệ thống bài tập
            elif first_line.startswith("TM"):
                errors.append({
                    "issue": "Hệ thống bài tập không áp dụng thể thức Thay mặt ('TM.').",
                    "fix": "Sử dụng thể thức đề ký theo đúng bài tập: Ký trực tiếp (người đứng đầu), Ký thay ('KT.') hoặc Thừa lệnh ('TL.')."
                })

        # 2.2 ĐỐI CHIẾU THỂ THỨC ĐỀ KÝ VỚI YÊU CẦU CỦA BÀI TẬP (CÔNG VĂN, THÔNG BÁO, TỜ TRÌNH)
        if chuc_vu_lines:
            if self.doc_type_id == "thong_bao_nhiem_vu":
                is_sub_dept = bool(p_cq_ban_hanh and "PHÒNG" in self._clean_text(p_cq_ban_hanh).upper())
                if is_sub_dept and not any("TL." in l or "TL " in l for l in chuc_vu_lines):
                    errors.append({
                        "issue": "Sai thể thức đề ký của bài tập Thông báo nhiệm vụ: Cơ quan ban hành là Phòng Đào tạo, do đó bắt buộc ký Thừa lệnh (Dòng 1: 'TL. HIỆU TRƯỞNG', Dòng 2: 'TRƯỞNG PHÒNG ĐÀO TẠO').",
                        "fix": "Dòng 1 ghi 'TL. HIỆU TRƯỞNG', dòng 2 ghi 'TRƯỞNG PHÒNG ĐÀO TẠO' (in hoa, in đậm, canh giữa)."
                    })
            elif self.doc_type_id in ["cong_van_de_nghi", "bai_thu_hoach"]:
                # Đối với Công văn / Bài thu hoạch: Cho phép linh hoạt các thể thức đề ký chuẩn Nghị định 30:
                # 1. Ký thay (KT.): KT. GIÁM ĐỐC / PHÓ GIÁM ĐỐC (hoặc KT. HIỆU TRƯỞNG / PHÓ HIỆU TRƯỞNG, KT. TỔNG GIÁM ĐỐC...)
                # 2. Thừa lệnh (TL.): TL. HIỆU TRƯỞNG / TRƯỞNG PHÒNG... (hoặc TL. GIÁM ĐỐC...)
                # 3. Ký trực tiếp: GIÁM ĐỐC, TỔNG GIÁM ĐỐC, HIỆU TRƯỞNG, CHỦ TỊCH...
                # 4. Đối với Bài thu hoạch: Cho phép thêm NGƯỜI THU HOẠCH, SINH VIÊN THỰC HIỆN...
                has_kt = any(re.match(r"^KT[\.\s]", l, re.IGNORECASE) for l in chuc_vu_lines)
                has_tl = any(re.match(r"^TL[\.\s]", l, re.IGNORECASE) for l in chuc_vu_lines)
                
                if has_kt:
                    pass
                elif has_tl:
                    pass
                else:
                    first_l = chuc_vu_lines[0].upper()
                    # Trường hợp cấp phó ký trực tiếp 1 dòng mà thiếu dòng KT. người đứng đầu
                    if any(kw in first_l for kw in ["PHÓ GIÁM ĐỐC", "PHÓ HIỆU TRƯỞNG", "PHÓ TỔNG GIÁM ĐỐC", "PHÓ CHỦ TỊCH"]) or (first_l.startswith("PHÓ ") and len(chuc_vu_lines) == 1):
                        errors.append({
                            "issue": "Cấp phó ký thay người đứng đầu phải sử dụng thể thức Ký thay ('KT.') gồm 2 dòng: Dòng 1 ghi 'KT. <CHỨC VỤ NGƯỜI ĐỨNG ĐẦU>' (Ví dụ: 'KT. GIÁM ĐỐC' hoặc 'KT. HIỆU TRƯỞNG'), Dòng 2 ghi chức vụ cấp phó.",
                            "fix": "Dòng 1 ghi 'KT. GIÁM ĐỐC' (hoặc 'KT. HIỆU TRƯỞNG'), Dòng 2 ghi chức vụ cấp phó (in hoa, in đậm, canh giữa)."
                        })
                    else:
                        valid_signers = ["HIỆU TRƯỞNG", "GIÁM ĐỐC", "TỔNG GIÁM ĐỐC", "CHỦ TỊCH", "VIỆN TRƯỞNG", "TRƯỞNG BAN", "TRƯỞNG PHÒNG", "TRƯỞNG KHOA"]
                        if self.doc_type_id == "bai_thu_hoach":
                            valid_signers.extend(["NGƯỜI THU HOẠCH", "NGƯỜI LÀM BÀI", "HỌC VIÊN", "SINH VIÊN", "NGƯỜI THỰC HIỆN", "HỌC VIÊN THỰC HIỆN", "SINH VIÊN THỰC HIỆN", "NGƯỜI BÁO CÁO"])
                        if not any(kw in first_l for kw in valid_signers):
                            errors.append({
                                "issue": "Chức vụ người ký của Công văn phải là chức vụ người đứng đầu (Ví dụ: 'GIÁM ĐỐC', 'HIỆU TRƯỞNG') hoặc Ký thay ('KT. GIÁM ĐỐC' / 'PHÓ GIÁM ĐỐC').",
                                "fix": "Ghi đúng chức vụ người ký theo bài tập (Ví dụ: 'HIỆU TRƯỞNG', 'GIÁM ĐỐC' hoặc 'KT. GIÁM ĐỐC' / 'PHÓ GIÁM ĐỐC')."
                            })
            elif self.doc_type_id == "to_trinh_thiet_bi":
                if not any("KT." in l or "KT " in l for l in chuc_vu_lines):
                    errors.append({
                        "issue": "Sai thể thức đề ký của bài tập Tờ trình xin thiết bị: Bài tập yêu cầu Ký thay người đứng đầu (Dòng 1: 'KT. GIÁM ĐỐC', Dòng 2: 'PHÓ GIÁM ĐỐC').",
                        "fix": "Dòng 1 ghi 'KT. GIÁM ĐỐC', dòng 2 ghi 'PHÓ GIÁM ĐỐC' (in hoa, in đậm, canh giữa)."
                    })
            elif self.doc_type_id == "to_trinh_nhan_su":
                if not any("TRƯỞNG KHOA" in l for l in chuc_vu_lines):
                    errors.append({
                        "issue": "Chức vụ người ký của Tờ trình nhân sự Khoa CNTT phải là 'TRƯỞNG KHOA'.",
                        "fix": "Sửa chức vụ người ký thành 'TRƯỞNG KHOA'."
                    })
            elif self.doc_type_id == "to_trinh_xin_kinh_phi":
                if not any("BÍ THƯ" in l for l in chuc_vu_lines):
                    errors.append({
                        "issue": "Chức vụ người ký của Tờ trình xin kinh phí phải là 'BÍ THƯ ĐOÀN TRƯỜNG' (hoặc 'BÍ THƯ').",
                        "fix": "Sửa chức vụ người ký thành 'BÍ THƯ ĐOÀN TRƯỜNG'."
                    })
            elif self.doc_type_id == "bao_cao":
                has_kt = any(re.match(r"^KT[\.\s]", l, re.IGNORECASE) for l in chuc_vu_lines)
                has_tl = any(re.match(r"^TL[\.\s]", l, re.IGNORECASE) for l in chuc_vu_lines)
                if not (has_kt or has_tl):
                    first_l = chuc_vu_lines[0].upper()
                    if not any(kw in first_l for kw in ["TRƯỞNG KHOA", "HIỆU TRƯỞNG", "GIÁM ĐỐC", "TRƯỞNG PHÒNG", "TRƯỞNG BAN", "BÍ THƯ", "VIỆN TRƯỞNG", "CHỦ TỊCH"]):
                        errors.append({
                            "issue": "Chức vụ người ký của Báo cáo phải là chức vụ thủ trưởng/trưởng đơn vị (Ví dụ: 'TRƯỞNG KHOA', 'GIÁM ĐỐC', 'HIỆU TRƯỞNG') hoặc Ký thay ('KT. GIÁM ĐỐC' / 'PHÓ GIÁM ĐỐC').",
                            "fix": "Ghi đúng chức vụ người ký (Ví dụ: 'TRƯỞNG KHOA', 'GIÁM ĐỐC' hoặc 'KT. GIÁM ĐỐC')."
                        })


        # 3. KHOẢNG CÁCH DÀNH ĐỂ KÝ TÊN VÀ ĐÓNG DẤU (Ô 8)
        last_cv_p = chuc_vu_paras[-1]
        sp_sign = getattr(last_cv_p.paragraph_format.space_after, "pt", 0) or 0
        if empty_lines_sign < 2 and sp_sign < 25:
            errors.append({
                "issue": "Khoảng cách từ Chức vụ (7a) đến Họ tên (7b) phải từ 2 - 2.5 cm dành để ký tên và đóng dấu.",
                "fix": "Nhấn Enter để cách ra 3-4 dòng trống giữa Chức vụ và Họ tên người ký."
            })

        # 4. HỌ VÀ TÊN NGƯỜI KÝ (Ô 7b)
        font_h, size_h, bold_h, italic_h = self._get_dominant_font_and_size(p_ho_ten)
        if not bold_h:
            errors.append({"issue": "Họ và tên người ký phải IN ĐẬM.", "fix": "Nhấn Ctrl + B để in đậm họ tên người ký."})
        if italic_h:
            errors.append({"issue": "Họ và tên người ký là chữ đứng, KHÔNG in nghiêng.", "fix": "Tắt in nghiêng (Ctrl + I)."})
        if size_h != expected_sign_size:
            errors.append({
                "issue": f"Tính thống nhất cỡ chữ: Họ tên người ký phải thống nhất cỡ {int(expected_sign_size)}pt (Hiện tại: {size_h}pt).",
                "fix": f"Chỉnh cỡ chữ họ tên về {int(expected_sign_size)}pt."
            })
        if p_ho_ten.alignment in [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.RIGHT]:
            errors.append({"issue": "Họ và tên người ký chưa được canh giữa.", "fix": "Nhấn Ctrl + E để canh giữa."})

        words = t_ho_ten.split()
        if len(words) >= 2 and t_ho_ten == t_ho_ten.upper():
            errors.append({
                "issue": "Họ và tên người ký không được viết hoa toàn bộ (sai chuẩn NĐ 30).",
                "fix": "Chỉ viết hoa các chữ cái đầu của mỗi từ (Ví dụ: 'Nguyễn Thị Diệu' thay vì 'NGUYỄN THỊ DIỆU')."
            })

        return {
            "box_id": 7,
            "name": "Ô 7 & 8: Chức vụ, Chữ ký và Họ tên người ký",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 9a: NƠI NHẬN TRỰC TIẾP (KÍNH GỬI - CÔNG VĂN, TỜ TRÌNH, BÁO CÁO)
    # =========================================================================
    def check_box_9a_kinh_gui(self, p_kinh_gui, kinh_gui_items):
        is_cv = (self.doc_type_id in ["cong_van_de_nghi", "bai_thu_hoach"]) or getattr(self, "is_cong_van", False)
        is_required = is_cv or (self.doc_type_id in ["to_trinh_nhan_su", "to_trinh_thiet_bi", "to_trinh_xin_kinh_phi", "bao_cao"])
        if not is_required:
            if p_kinh_gui:
                return {
                    "box_id": "9a",
                    "name": "Ô 9a: Nơi nhận trực tiếp (Kính gửi)",
                    "passed": False,
                    "errors": [{
                        "issue": "Sai sơ đồ bố trí theo Nghị định 30 (Sơ đồ 3 - Hình 3): Thông báo KHÔNG CÓ mục Nơi nhận trực tiếp (Kính gửi / Ô 9a) trước phần Nội dung (Ô 6).",
                        "fix": "Xóa dòng 'Kính gửi' trong Thông báo. Nơi nhận của Thông báo chỉ trình bày tại Ô 9b ở góc dưới bên trái văn bản."
                    }]
                }
            return None

        errors = []
        if not p_kinh_gui:
            return {
                "box_id": "9a",
                "name": "Ô 9a: Nơi nhận trực tiếp (Kính gửi)",
                "passed": False,
                "errors": [{"issue": "Văn bản này bắt buộc phải có mục nơi nhận trực tiếp 'Kính gửi: ...' (Ô 9a).", "fix": "Thêm dòng 'Kính gửi: ...' trước khi bắt đầu phần nội dung chính."}]
            }

        t_kg = self._clean_text(p_kinh_gui)
        if not re.search(r"Kính\s+gửi", t_kg, re.IGNORECASE):
            errors.append({"issue": "Mục nơi nhận trực tiếp phải bắt đầu bằng từ 'Kính gửi:'.", "fix": "Ghi đúng: 'Kính gửi: ...'."})

        # Kiểm tra viết hoa chữ 'Kính gửi'
        if t_kg.startswith("kính gửi"):
            errors.append({"issue": "Ô 9a: Từ 'kính gửi' phải viết hoa chữ cái đầu (K) theo phép đặt câu.", "fix": "Sửa thành 'Kính gửi: ...'."})
        elif t_kg.startswith("KÍNH GỬI"):
            errors.append({"issue": "Ô 9a: Mục 'Kính gửi:' là chữ in thường đứng, chỉ viết hoa chữ cái đầu (K), KHÔNG in hoa toàn bộ.", "fix": "Sửa thành 'Kính gửi: ...'."})
        elif t_kg.startswith("Kính Gửi"):
            errors.append({"issue": "Ô 9a: Chữ 'gửi' trong 'Kính gửi:' là chữ in thường, không viết hoa.", "fix": "Sửa thành 'Kính gửi: ...'."})

        # Kiểm tra quy tắc khoảng cách trống ở dòng Kính gửi
        errors.extend(self.check_decree30_punctuation_spacing(t_kg, "Ô 9a: Nơi nhận trực tiếp (Kính gửi)"))

        expected_kg_size = self.get_expected_size("kinh_gui")

        # TH1: CHỈ CÓ 1 CƠ QUAN NHẬN
        if len(kinh_gui_items) == 0:
            if not re.search(r"Kính\s+gửi\s*:", t_kg, re.IGNORECASE):
                errors.append({"issue": "Từ 'Kính gửi' phải có dấu hai chấm ':' ngay sau.", "fix": "Sửa thành 'Kính gửi: ...'."})
            font_k, size_k, bold_k, italic_k = self._get_dominant_font_and_size(p_kinh_gui)
            if size_k != expected_kg_size:
                errors.append({
                    "issue": f"Tính thống nhất cỡ chữ: Dòng Kính gửi phải thống nhất cỡ {int(expected_kg_size)}pt (Hiện tại: {size_k}pt).",
                    "fix": f"Chỉnh cỡ chữ về {int(expected_kg_size)}pt."
                })
            if bold_k:
                errors.append({"issue": "Dòng Kính gửi là chữ in thường đứng, KHÔNG in đậm.", "fix": "Tắt in đậm (Ctrl + B)."})

            # Kiểm tra viết hoa tên cơ quan nhận sau Kính gửi
            org_after = re.sub(r"^Kính\s+gửi\s*:\s*", "", t_kg, flags=re.IGNORECASE).rstrip(".").strip()
            if org_after:
                cap_errs = self.check_decree30_capitalization(org_after, "Ô 9a: Nơi nhận trực tiếp (Kính gửi)")
                errors.extend(cap_errs)
        # TH2: CÓ NHIỀU CƠ QUAN NHẬN
        else:
            if not re.match(r"^Kính\s+gửi\s*:\s*$", t_kg, re.IGNORECASE) and len(t_kg.split()) > 3:
                errors.append({
                    "issue": "Khi có nhiều cơ quan nhận, từ 'Kính gửi:' phải được trình bày trên một dòng riêng.",
                    "fix": "Để riêng dòng 'Kính gửi:' và xuống dòng cho từng cơ quan nhận bên dưới."
                })
            if not re.search(r":\s*$", t_kg):
                errors.append({"issue": "Sau từ 'Kính gửi' phải có dấu hai chấm (:).", "fix": "Thêm dấu hai chấm thành 'Kính gửi:'."})

            left_indent = p_kinh_gui.paragraph_format.left_indent
            if left_indent is None or (hasattr(left_indent, 'cm') and left_indent.cm < 1.2):
                errors.append({
                    "issue": "Canh cho Ô 9a đi vào gần như giữa văn bản bằng công cụ Increase Indent.",
                    "fix": "Chọn các dòng Kính gửi và danh sách cơ quan nhận ➔ Nhấn nút Increase Indent để thụt lề vào trong khoảng 2.5 - 5cm."
                })

            for idx, item_p in enumerate(kinh_gui_items):
                t_item = self._clean_text(item_p)
                errors.extend(self.check_decree30_punctuation_spacing(t_item, "Ô 9a: Nơi nhận trực tiếp (Kính gửi)"))
                has_num_pr = item_p._element.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr') is not None
                starts_with_dash = t_item.startswith(("-", "–", "—"))
                if not (has_num_pr or starts_with_dash):
                    errors.append({
                        "issue": f"Dòng cơ quan nhận '{t_item[:25]}...' đầu dòng phải có dấu gạch ngang sử dụng Bullet list.",
                        "fix": "Chọn dòng và nhấn công cụ Bullet (chọn dấu gạch ngang) hoặc gõ dấu gạch ngang đầu dòng."
                    })

                is_last = (idx == len(kinh_gui_items) - 1)
                if is_last:
                    if not t_item.rstrip().endswith("."):
                        errors.append({
                            "issue": f"Dòng cơ quan nhận cuối cùng '{t_item[:25]}...' phải kết thúc bằng dấu chấm (.).",
                            "fix": "Thêm dấu chấm (.) vào cuối dòng cơ quan nhận cuối cùng."
                        })
                else:
                    if not t_item.rstrip().endswith(";"):
                        errors.append({
                            "issue": f"Dòng cơ quan nhận '{t_item[:25]}...' phải kết thúc bằng dấu chấm phẩy (;).",
                            "fix": "Thêm dấu chấm phẩy (;) vào cuối dòng."
                        })

                _, s_i, _, _ = self._get_dominant_font_and_size(item_p)
                if s_i != expected_kg_size:
                    errors.append({
                        "issue": f"Dòng cơ quan nhận '{t_item[:25]}...' chưa đúng cỡ chữ thống nhất {int(expected_kg_size)}pt (Hiện tại: {s_i}pt).",
                        "fix": f"Đặt cỡ chữ thành {int(expected_kg_size)}pt."
                    })

                # Kiểm tra viết hoa tên cơ quan nhận
                clean_org = t_item.lstrip("-–—*•+ ").rstrip(";.").strip()
                if clean_org:
                    cap_errs = self.check_decree30_capitalization(clean_org, "Ô 9a: Cơ quan nhận trực tiếp")
                    errors.extend(cap_errs)

        return {
            "box_id": "9a",
            "name": "Ô 9a: Nơi nhận trực tiếp (Kính gửi)",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # Ô 9b: NƠI NHẬN DÙNG CHUNG (GÓC DƯỚI BÊN TRÁI - DÒNG 1 CỘT 1 BẢNG CUỐI)
    # =========================================================================
    def check_box_9b_noi_nhan(self, p_noi_nhan_title, noi_nhan_items):
        errors = []
        if not p_noi_nhan_title:
            return {
                "box_id": "9b",
                "name": "Ô 9b: Nơi nhận cuối trang",
                "passed": False,
                "errors": [{"issue": "Chưa có mục 'Nơi nhận:' ở Bảng cuối trang (Dòng 1 Cột 1).", "fix": "Trình bày 'Nơi nhận:' ở cột trái Bảng cuối trang ngang hàng chức vụ."}]
            }

        t_nn = self._clean_text(p_noi_nhan_title)
        if not re.search(r"Nơi\s+nhận\s*:", t_nn, re.IGNORECASE):
            errors.append({"issue": "Dòng Nơi nhận phải có dấu hai chấm ':' ngay sau (Nơi nhận:).", "fix": "Ghi đúng: 'Nơi nhận:'."})

        # Kiểm tra khoảng cách trống ở tiêu đề 'Nơi nhận:'
        errors.extend(self.check_decree30_punctuation_spacing(t_nn, "Ô 9b: Nơi nhận"))

        # Dòng Nơi nhận cố định: 12pt, nghiêng, đậm
        font_n, size_n, bold_n, italic_n = self._get_dominant_font_and_size(p_noi_nhan_title)
        if not italic_n:
            errors.append({"issue": "Dòng chữ 'Nơi nhận:' phải IN NGHIÊNG.", "fix": "Bôi đen chữ 'Nơi nhận:' và nhấn Ctrl + I."})
        if not bold_n:
            errors.append({"issue": "Dòng chữ 'Nơi nhận:' phải IN ĐẬM.", "fix": "Bôi đen chữ 'Nơi nhận:' và nhấn Ctrl + B."})
        if size_n != 12.0:
            errors.append({"issue": f"Cỡ chữ 'Nơi nhận:' phải cố định là 12pt theo đúng chuẩn NĐ 30 (Hiện tại: {size_n}pt).", "fix": "Chỉnh cỡ chữ về đúng 12."})

        # Liệt kê con cố định: 11pt, in thường đứng
        wrong_item_size = 0
        has_luu_vt = False
        last_item_text = ""

        for item_p in noi_nhan_items:
            t_it = self._clean_text(item_p)
            last_item_text = t_it
            _, s_i, b_i, i_i = self._get_dominant_font_and_size(item_p)
            if s_i != 11.0:
                wrong_item_size += 1

            if "Lưu:" in t_it or "Lưu :" in t_it or "VT" in t_it:
                has_luu_vt = True

            # Kiểm tra quy tắc khoảng cách trống trong từng dòng nơi nhận (ví dụ: 'Lưu:VT.', 'VT,VP')
            errors.extend(self.check_decree30_punctuation_spacing(t_it, "Ô 9b: Nơi nhận"))

            # Kiểm tra viết hoa tên cơ quan trong nơi nhận (bỏ qua 'Như kính gửi' và 'Lưu: VT')
            clean_org = t_it.lstrip("-–—*•+ ").rstrip(";.").strip()
            if clean_org and not any(kw in clean_org.lower() for kw in ["như kính gửi", "lưu:", "lưu :"]):
                cap_errs = self.check_decree30_capitalization(clean_org, "Ô 9b: Nơi nhận")
                errors.extend(cap_errs)

        if wrong_item_size > 0:
            errors.append({
                "issue": f"Có {wrong_item_size} dòng trong danh sách nơi nhận chưa để cỡ chữ 11pt.",
                "fix": "Bôi đen toàn bộ danh sách nơi nhận (- Ban Giám đốc; - Lưu: VT...) và đặt cỡ chữ thành 11."
            })

        if self.doc_type_id == "bai_thu_hoach":
            if not ("Lưu" in last_item_text):
                errors.append({
                    "issue": "Dòng cuối cùng của Nơi nhận cần có phần lưu trữ (Ví dụ: '- Lưu: VT.' hoặc '- Lưu: Hồ sơ cá nhân.').",
                    "fix": "Thêm dòng '- Lưu: VT.' vào cuối danh sách nơi nhận."
                })
            elif not last_item_text.rstrip().endswith("."):
                errors.append({
                    "issue": "Cuối dòng lưu nơi nhận phải có dấu chấm (.).",
                    "fix": "Thêm dấu chấm (.) vào cuối dòng (Ví dụ: '- Lưu: VT.')."
                })
        else:
            if not has_luu_vt or "Lưu" not in last_item_text or "VT" not in last_item_text:
                errors.append({
                    "issue": "Dòng cuối cùng của Nơi nhận bắt buộc phải là 'Lưu: VT.' (Lưu Văn thư cơ quan).",
                    "fix": "Thêm dòng 'Lưu: VT.' vào cuối danh sách nơi nhận."
                })
            elif not last_item_text.rstrip().endswith("."):
                errors.append({
                    "issue": "Cuối dòng 'Lưu: VT.' phải có dấu chấm (.).",
                    "fix": "Thêm dấu chấm (.) vào cuối dòng: 'Lưu: VT.'."
                })

        return {
            "box_id": "9b",
            "name": "Ô 9b: Nơi nhận cuối trang",
            "passed": len(errors) == 0,
            "errors": errors
        }

    # =========================================================================
    # QUÉT VÀ THẨM ĐỊNH TOÀN DIỆN VĂN BẢN
    # =========================================================================
    def validate_document(self):
        all_paragraphs = self.doc.paragraphs
        tables = self.doc.tables

        header_table = tables[0] if len(tables) >= 1 else None
        footer_table = tables[-1] if len(tables) >= 2 else (tables[0] if len(tables) == 1 and len(tables[0].rows) == 1 else None)

        p_quoc_hieu = None
        p_tieu_ngu = None
        p_cq_quan_ly = None
        p_cq_ban_hanh = None
        p_so = None
        p_dia_danh = None
        p_type = None
        p_trich_yeu = None
        p_trich_yeu_outside_extra = None
        is_5b_in_table = False
        p_kinh_gui = None
        kinh_gui_items = []
        p_chuc_vu = None
        p_ho_ten = None
        empty_lines_sign = 0
        p_noi_nhan_title = None
        noi_nhan_items = []
        body_paragraphs = []

        same_row_so_dia_danh = False

        # TẦNG 1: BẢNG ĐẦU TRANG (2 CỘT x 2 DÒNG)
        if header_table:
            # Hàng 1, Cột 1: Ô 2 (Cơ quan)
            if len(header_table.rows) >= 1 and len(header_table.rows[0].cells) >= 1:
                cell_00 = header_table.cell(0, 0)
                paras_00 = [p for p in cell_00.paragraphs if self._clean_text(p)]
                if len(paras_00) == 1:
                    p_cq_ban_hanh = paras_00[0]
                elif len(paras_00) >= 2:
                    p_cq_quan_ly = paras_00[0]
                    p_cq_ban_hanh = paras_00[1]

            # Hàng 1, Cột 2: Ô 1 (Quốc hiệu & Tiêu ngữ)
            if len(header_table.rows) >= 1 and len(header_table.rows[0].cells) >= 2:
                cell_01 = header_table.cell(0, 1)
                for p in cell_01.paragraphs:
                    t = self._clean_text(p)
                    if not t: continue
                    if not p_quoc_hieu and self._is_quoc_hieu(t):
                        p_quoc_hieu = p
                    elif not p_tieu_ngu and self._is_tieu_ngu(t):
                        p_tieu_ngu = p

            # Hàng 2, Cột 1: Ô 3 (Số ký hiệu) + Ô 5b (Trích yếu V/v nếu là Công văn)
            if len(header_table.rows) >= 2 and len(header_table.rows[1].cells) >= 1:
                cell_10 = header_table.cell(1, 0)
                for p in cell_10.paragraphs:
                    t = self._clean_text(p)
                    if not t: continue
                    if not p_so and (re.match(r"^Số\s*:", t, re.IGNORECASE) or t.startswith("SỐ")):
                        p_so = p
                    elif not p_trich_yeu and (t.startswith("V/v") or t.lower().startswith("v/v") or t.startswith("Về việc") or t.lower().startswith("về việc")):
                        p_trich_yeu = p
                        is_5b_in_table = True

            # Hàng 2, Cột 2: Ô 4 (Địa danh ngày tháng)
            if len(header_table.rows) >= 2 and len(header_table.rows[1].cells) >= 2:
                cell_11 = header_table.cell(1, 1)
                for p in cell_11.paragraphs:
                    t = self._clean_text(p)
                    if not t: continue
                    if not p_dia_danh and ("ngày" in t.lower() and "tháng" in t.lower() and "năm" in t.lower()):
                        p_dia_danh = p

            if p_so and p_dia_danh:
                same_row_so_dia_danh = True

        # TẦNG 2: BẢNG CUỐI TRANG (2 CỘT x 1 DÒNG)
        if footer_table and footer_table != header_table:
            row_f = footer_table.rows[0]
            # Cột 1: Ô 9b (Nơi nhận)
            cell_left = row_f.cells[0]
            for p in cell_left.paragraphs:
                t = self._clean_text(p)
                if not t: continue
                if "Nơi nhận" in t:
                    p_noi_nhan_title = p
                elif t.startswith("-") or t.startswith("–") or t.startswith("—") or "Lưu:" in t or "Như kính gửi" in t or "Ban Giám" in t or "Phòng" in t:
                    noi_nhan_items.append(p)

            # Cột 2: Ô 7a, 8, 7b
            if len(row_f.cells) > 1:
                cell_right = row_f.cells[1]
                non_empty_right = [p for p in cell_right.paragraphs if self._clean_text(p)]
                empty_paras = [p for p in cell_right.paragraphs if not self._clean_text(p)]
                empty_lines_sign = len(empty_paras)

                if len(non_empty_right) == 1:
                    p_chuc_vu = non_empty_right[0]
                elif len(non_empty_right) == 2:
                    t1 = self._clean_text(non_empty_right[1])
                    if t1 == t1.upper() and any(kw in t1 for kw in ["PHÓ", "TRƯỞNG", "TP.", "CHỦ TỊCH", "BÍ THƯ"]):
                        p_chuc_vu = non_empty_right
                        p_ho_ten = None
                    else:
                        p_chuc_vu = non_empty_right[0]
                        p_ho_ten = non_empty_right[1]
                elif len(non_empty_right) >= 3:
                    p_chuc_vu = non_empty_right[:-1]
                    p_ho_ten = non_empty_right[-1]

        # TẦNG 3: NGOÀI BẢNG (KÍNH GỬI Ô 9a, THÂN BÀI Ô 6, VĂN BẢN CÓ TÊN LOẠI Ô 5a)
        collecting_kinh_gui = False
        outside_header_paras = []
        for p in all_paragraphs:
            t = self._clean_text(p)
            if not t:
                if collecting_kinh_gui:
                    collecting_kinh_gui = False
                continue

            # Ô 9a Kính gửi
            if "Kính gửi:" in t or "Kính gửi :" in t or t.startswith("Kính gửi"):
                p_kinh_gui = p
                # Nếu chỉ có từ "Kính gửi:" trên 1 dòng riêng thì mới tiếp tục thu thập các cơ quan bên dưới
                # Nếu đã có tên cơ quan ngay sau dấu hai chấm (ví dụ: "Kính gửi: Bộ Khoa học và Công nghệ.") thì là trường hợp 1 cơ quan
                after_kg = re.sub(r"^Kính\s+gửi\s*:\s*", "", t, flags=re.IGNORECASE).strip()
                if not after_kg or t.endswith(";"):
                    collecting_kinh_gui = True
                else:
                    collecting_kinh_gui = False
                continue

            if collecting_kinh_gui:
                has_bullet = p._element.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pPr/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}numPr') is not None
                is_bullet_line = has_bullet or t.startswith(("-", "–", "—"))
                is_body_like = any(t.startswith(kw) for kw in ["Căn cứ", "Thực hiện", "Nhằm", "Để ", "Hiện nay"]) or (len(t) > 80 and not is_bullet_line)
                if not is_body_like and (is_bullet_line or t.endswith(";") or t.endswith(".")):
                    kinh_gui_items.append(p)
                    if t.endswith("."):
                        collecting_kinh_gui = False
                    continue
                else:
                    collecting_kinh_gui = False

            # Nhận diện nếu không nằm trong bảng
            if not p_quoc_hieu and self._is_quoc_hieu(t):
                p_quoc_hieu = p
            elif not p_tieu_ngu and self._is_tieu_ngu(t):
                p_tieu_ngu = p
            elif not p_so and (re.match(r"^Số\s*:", t, re.IGNORECASE) or t.startswith("SỐ")):
                p_so = p
            elif not p_dia_danh and ("ngày" in t.lower() and "tháng" in t.lower() and "năm" in t.lower()):
                p_dia_danh = p
            # Ô 5a: TÊN LOẠI VĂN BẢN (CHỈ XUẤT HIỆN Ở ĐẦU TRANG, TRƯỚC KÍNH GỬI VÀ TRƯỚC NỘI DUNG THÂN BÀI)
            elif (not p_type and not p_kinh_gui and len(body_paragraphs) == 0 and 
                  len(t) <= 45 and not t.endswith(".") and
                  (t.upper().strip() in ["CÔNG VĂN", "THÔNG BÁO", "TỜ TRÌNH", "BÁO CÁO", "BÀI THU HOẠCH", "QUYẾT ĐỊNH"] or 
                   re.match(r"^(CÔNG VĂN|THÔNG BÁO|TỜ TRÌNH|BÁO CÁO|BÀI THU HOẠCH|QUYẾT ĐỊNH)\b", t.upper().strip()))):
                p_type = p
                outside_header_paras.append(p)
            # Ô 5b: TRÍCH YẾU NGOÀI BẢNG (CHỈ XUẤT HIỆN Ở ĐẦU TRANG, TRƯỚC KÍNH GỬI VÀ TRƯỚC NỘI DUNG THÂN BÀI)
            elif (not p_kinh_gui and len(body_paragraphs) == 0 and
                  (t.startswith("Về việc") or t.startswith("về việc") or t.startswith("V/v") or 
                   (p_type is not None and (t.startswith("Về ") or t.startswith("về ") or t.startswith("Khóa ") or t.startswith("Chuyên đề ") or t.startswith("Học phần "))))):
                if not p_trich_yeu:
                    p_trich_yeu = p
                    is_5b_in_table = False
                else:
                    p_trich_yeu_outside_extra = p
                outside_header_paras.append(p)
            elif not p_noi_nhan_title and "Nơi nhận" in t:
                p_noi_nhan_title = p
            elif not footer_table and p_noi_nhan_title and (t.startswith("-") or "Lưu:" in t):
                noi_nhan_items.append(p)
            elif not p_chuc_vu and any(kw in t.upper() for kw in ["HIỆU TRƯỞNG", "GIÁM ĐỐC", "TRƯỞNG PHÒNG", "TRƯỞNG KHOA", "BÍ THƯ", "NGƯỜI THU HOẠCH", "NGƯỜI LÀM BÀI", "HỌC VIÊN", "SINH VIÊN", "NGƯỜI THỰC HIỆN"]):
                p_chuc_vu = p
            elif p_chuc_vu and not p_ho_ten and len(t.split()) in [2, 3, 4] and not t.startswith("Căn cứ"):
                p_ho_ten = p
            else:
                is_list_line = (
                    bool(p._p.xpath("./w:pPr/w:numPr")) or 
                    bool(p.style and ("List" in p.style.name or "Bullet" in p.style.name or "Number" in p.style.name)) or
                    bool(re.match(r"^\s*([0-9]+[\.\)]|[a-zA-Z][\.\)]|\([0-9a-zA-Z]+\)|[ivxIVX]+[\.\)]|[-+*•⁃‣○●■□▪▫–—])\s*", t))
                )
                if (len(t) > 20 or (is_list_line and len(t) >= 3)) and not t.lower().startswith("cơ quan ban hành") and not t.lower().startswith("cơ quan chủ quản"):
                    body_paragraphs.append(p)
                elif not p_kinh_gui and len(body_paragraphs) == 0 and len(t) > 2:
                    outside_header_paras.append(p)

        # TỰ ĐỘNG NHẬN DIỆN VĂN BẢN CÔNG VĂN (SƠ ĐỒ 2 - HÌNH 2)
        is_cong_van = (self.doc_type_id in ["cong_van_de_nghi", "bai_thu_hoach"])
        if not is_cong_van:
            p_type_text = self._clean_text(p_type).upper() if p_type else ""
            outside_texts = [self._clean_text(p).upper() for p in outside_header_paras]
            doc_path_str = getattr(self, "doc_path", "") or ""
            if "CÔNG VĂN" in p_type_text or any("CÔNG VĂN" in ot for ot in outside_texts):
                is_cong_van = True
            elif doc_path_str and re.search(r"cong_?van", os.path.basename(doc_path_str), re.IGNORECASE):
                is_cong_van = True
            elif is_5b_in_table and p_kinh_gui is not None:
                has_named_type = any(
                    any(kw in ot for kw in ["THÔNG BÁO", "TỜ TRÌNH", "BÁO CÁO"])
                    for ot in outside_texts
                )
                if not has_named_type:
                    is_cong_van = True

        self.is_cong_van = is_cong_van

        # THỰC THI KIỂM ĐỊNH THỂ THỨC & THẨM MỸ
        checklist = []
        checklist.append(self.check_page_margins())
        checklist.append(self.check_table_structures(header_table, footer_table))
        checklist.append(self.check_box_1_quoc_hieu(p_quoc_hieu, p_tieu_ngu))
        checklist.append(self.check_box_2_co_quan(p_cq_quan_ly, p_cq_ban_hanh))
        checklist.append(self.check_box_3_so_ky_hieu(p_so))
        checklist.append(self.check_box_4_dia_danh(p_dia_danh, same_row=same_row_so_dia_danh))
        checklist.append(self.check_box_5_trich_yeu(
            p_type=p_type,
            p_trich_yeu=p_trich_yeu,
            p_so=p_so,
            is_5b_in_table=is_5b_in_table,
            p_trich_yeu_outside_extra=p_trich_yeu_outside_extra,
            p_5b_table=(p_trich_yeu if is_5b_in_table else None),
            p_trich_yeu_outside=(p_trich_yeu if not is_5b_in_table else p_trich_yeu_outside_extra),
            outside_header_paras=outside_header_paras
        ))
        self.body_paragraphs = body_paragraphs
        checklist.append(self.check_box_6_noi_dung(body_paragraphs))
        checklist.append(self.check_box_7_8_chuc_vu_nguoi_ky(p_chuc_vu, p_ho_ten, empty_lines_sign, p_cq_ban_hanh=p_cq_ban_hanh))

        box_9a = self.check_box_9a_kinh_gui(p_kinh_gui, kinh_gui_items)
        if box_9a:
            checklist.append(box_9a)

        checklist.append(self.check_box_9b_noi_nhan(p_noi_nhan_title, noi_nhan_items))

        passed_count = sum(1 for item in checklist if item["passed"])
        total_count = len(checklist)

        return {
            "checklist": checklist,
            "passed_count": passed_count,
            "total_count": total_count,
            "percentage": round((passed_count / total_count) * 100, 1),
            "font_profile": self.font_profile,
            "can_submit": (passed_count == total_count)
        }
