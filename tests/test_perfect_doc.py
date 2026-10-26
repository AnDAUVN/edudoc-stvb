import os
import sys
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engine.security import create_student_raw_template
from engine.validator import Decree30Validator

def create_perfect_decree30_doc(output_path):
    doc = Document()
    
    # 1. Page Margins chuẩn NĐ 30: Top 2cm, Bottom 2cm, Left 3cm, Right 1.5cm
    section = doc.sections[0]
    section.top_margin = Inches(2.0 / 2.54)
    section.bottom_margin = Inches(2.0 / 2.54)
    section.left_margin = Inches(3.0 / 2.54)
    section.right_margin = Inches(1.5 / 2.54)

    # 2. Table Header 2 cột (Ô 2 & Ô 1, Ô 3 & Ô 4)
    table_header = doc.add_table(rows=2, cols=2)
    table_header.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_header.autofit = False
    
    # Ô 2: Dòng 1: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH (12pt, đứng, regular)
    #      Dòng 2: PHÒNG ĐÀO TẠO (12pt, đứng, bold)
    cell_cq = table_header.cell(0, 0)
    p_cq1 = cell_cq.paragraphs[0]
    p_cq1.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p_cq1.add_run("TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH")
    r1.font.name = "Times New Roman"
    r1.font.size = Pt(12)
    r1.bold = False
    
    p_cq2 = cell_cq.add_paragraph()
    p_cq2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = p_cq2.add_run("PHÒNG ĐÀO TẠO")
    r2.font.name = "Times New Roman"
    r2.font.size = Pt(12)
    r2.bold = True

    # Ô 1: Dòng 1: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM (12pt, đứng, bold)
    #      Dòng 2: Độc lập - Tự do - Hạnh phúc (13pt, đứng, bold)
    cell_qh = table_header.cell(0, 1)
    p_qh = cell_qh.paragraphs[0]
    p_qh.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_qh = p_qh.add_run("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM")
    r_qh.font.name = "Times New Roman"
    r_qh.font.size = Pt(12)
    r_qh.bold = True

    p_tn = cell_qh.add_paragraph()
    p_tn.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_tn = p_tn.add_run("Độc lập - Tự do - Hạnh phúc")
    r_tn.font.name = "Times New Roman"
    r_tn.font.size = Pt(13)
    r_tn.bold = True

    # Ô 3: Số: 45/TB-ĐT (13pt, đứng, regular)
    cell_so = table_header.cell(1, 0)
    p_so = cell_so.paragraphs[0]
    p_so.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_so = p_so.add_run("Số: 45/TB-ĐT")
    r_so.font.name = "Times New Roman"
    r_so.font.size = Pt(13)
    r_so.bold = False

    # Ô 4: Thành phố Hồ Chí Minh, ngày 02 tháng 02 năm 2026 (13pt, nghiêng, regular)
    cell_dia = table_header.cell(1, 1)
    p_dia = cell_dia.paragraphs[0]
    p_dia.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_dia = p_dia.add_run("Thành phố Hồ Chí Minh, ngày 02 tháng 02 năm 2026")
    r_dia.font.name = "Times New Roman"
    r_dia.font.size = Pt(13)
    r_dia.italic = True
    r_dia.bold = False

    # Dòng trống cách
    p_sp = doc.add_paragraph()
    p_sp.paragraph_format.space_after = Pt(12)

    # Ô 5a: Tên loại: THÔNG BÁO (14pt, đứng, bold, center)
    #       Trích yếu: Về việc phân công nhiệm vụ... (13pt, đứng, bold, center)
    p_type = doc.add_paragraph()
    p_type.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_type = p_type.add_run("THÔNG BÁO")
    r_type.font.name = "Times New Roman"
    r_type.font.size = Pt(13) # Đồng bộ 'Số trước' theo Ô 1
    r_type.bold = True

    p_ty = doc.add_paragraph()
    p_ty.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ty = p_ty.add_run("Về việc phân công nhiệm vụ cán bộ coi thi kết thúc học phần")
    r_ty.font.name = "Times New Roman"
    r_ty.font.size = Pt(13)
    r_ty.bold = True

    # Ô 6: Thân bài (Justify, First line indent 1.27cm, size 13, Times New Roman)
    body_texts = [
        "Thực hiện Kế hoạch tổ chức kỳ thi kết thúc học phần học kỳ 1 năm học 2025 - 2026 đã được Ban Giám hiệu phê duyệt, Phòng Đào tạo xin thông báo đến toàn thể cán bộ, giảng viên và nhân viên trong Nhà trường về việc thực hiện nhiệm vụ coi thi học kỳ.",
        "Toàn thể cán bộ và giảng viên có tên trong danh sách điều động phải có mặt tại Văn phòng Hội đồng thi trước giờ thi 30 phút để nhận đề và thẻ phân công nhiệm vụ, đồng thời nghiêm túc chấp hành quy chế thi hành chính của Trường Đại học Nguyễn Tất Thành.",
        "Đề nghị các đơn vị và cá nhân có liên quan nghiêm túc triển khai thực hiện thông báo này nhằm đảm bảo kỳ thi diễn ra an toàn, nghiêm túc và đúng quy định."
    ]
    for b in body_texts:
        p_b = doc.add_paragraph()
        p_b.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p_b.paragraph_format.first_line_indent = Inches(1.27 / 2.54)
        p_b.paragraph_format.space_after = Pt(6)
        p_b.paragraph_format.line_spacing = 1.2
        r_b = p_b.add_run(b)
        r_b.font.name = "Times New Roman"
        r_b.font.size = Pt(13)

    # Dòng trống cách
    doc.add_paragraph()

    # Footer Table: Ô 9b (Nơi nhận) & Ô 7a, 8, 7b (Ký tên)
    table_footer = doc.add_table(rows=1, cols=2)
    table_footer.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    # Cột trái: Ô 9b
    cell_nn = table_footer.cell(0, 0)
    p_nn_t = cell_nn.paragraphs[0]
    r_nn_t = p_nn_t.add_run("Nơi nhận:")
    r_nn_t.font.name = "Times New Roman"
    r_nn_t.font.size = Pt(12)
    r_nn_t.bold = True
    r_nn_t.italic = True
    
    items = ["- Ban Giám hiệu (để b/c);", "- Các Khoa, Viện;", "- Lưu: VT, ĐT."]
    for it in items:
        p_it = cell_nn.add_paragraph()
        p_it.paragraph_format.space_after = Pt(0)
        p_it.paragraph_format.line_spacing = 1.0
        r_it = p_it.add_run(it)
        r_it.font.name = "Times New Roman"
        r_it.font.size = Pt(11)

    # Cột phải: Ô 7a, 8, 7b
    cell_sign = table_footer.cell(0, 1)
    p_cv = cell_sign.paragraphs[0]
    p_cv.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_cv1 = p_cv.add_run("TL. HIỆU TRƯỞNG\nTRƯỞNG PHÒNG ĐÀO TẠO")
    r_cv1.font.name = "Times New Roman"
    r_cv1.font.size = Pt(13)
    r_cv1.bold = True

    # Ô 8: Khoảng trống ký tên
    for _ in range(3):
        p_empty = cell_sign.add_paragraph()
        p_empty.paragraph_format.space_after = Pt(4)

    # Ô 7b: Họ và tên
    p_ten = cell_sign.add_paragraph()
    p_ten.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_ten = p_ten.add_run("Nguyễn Văn An")
    r_ten.font.name = "Times New Roman"
    r_ten.font.size = Pt(13)
    r_ten.bold = True

    doc.save(output_path)
    print(f"✔ Đã tạo file chuẩn Nghị định 30: {output_path}")

def test_perfect():
    out_file = "storage/templates/test_perfect_doc.docx"
    create_perfect_decree30_doc(out_file)

    val = Decree30Validator(out_file, "thong_bao_nhiem_vu")
    res = val.validate_document()
    print("\n--- KẾT QUẢ KIỂM THỬ FILE CHUẨN NGHỊ ĐỊNH 30 ---")
    print(f"Tiêu chí đạt: {res['passed_count']} / {res['total_count']} ({res['percentage']}%)")
    print(f"Đủ điều kiện nộp bài: {res['can_submit']}")
    for b in res["checklist"]:
        status = "✔ ĐẠT" if b["passed"] else "✖ LỖI"
        print(f"  [{status}] {b['name']}")
        if not b["passed"]:
            for e in b["errors"]:
                print(f"       - Lỗi: {e['issue']}")
    
    assert res["can_submit"] == True
    print("\n🎉 XÁC NHẬN: BÀI LÀM ĐẠT CHUẨN 100% NGHỊ ĐỊNH 30 VÀ MỞ NÚT NỘP BÀI THÀNH CÔNG!")

if __name__ == "__main__":
    test_perfect()
