from engine.validator import Decree30Validator

v = Decree30Validator('storage/uploads/temp_2100001234_01_2100001234_NGUYỄNVĂNA_CongVanDeNghi.docx', 'cong_van_de_nghi')
cell = v.doc.tables[1].cell(0, 0)
for i, p in enumerate(cell.paragraphs):
    f, sz, b, it = v._get_dominant_font_and_size(p)
    print(f"P{i}: text='{p.text}', size={sz}, font={f}")
