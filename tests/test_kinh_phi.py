from engine.security import create_student_raw_template, check_anti_cheat
from engine.validator import Decree30Validator
import json, os

with open('data/document_templates.json', encoding='utf-8') as f:
    tpls = json.load(f)

tpl = tpls['to_trinh_xin_kinh_phi']
print("✔ Template 'to_trinh_xin_kinh_phi' loaded:", tpl['name'])

out_raw = os.path.join("storage", "templates", "05_2100005555_NGUYENVANAN_ToTrinhXinKinhPhi.docx")
create_student_raw_template(
    sbd="05",
    mssv="2100005555",
    student_name="NGUYỄN VĂN AN",
    doc_type_id="to_trinh_xin_kinh_phi",
    raw_text=tpl['raw_text'],
    output_path=out_raw
)
print("✔ Raw template generated:", out_raw)

fraud = check_anti_cheat(out_raw, "05", "2100005555", "NGUYỄN VĂN AN")
print("✔ Anti-cheat check on self:", fraud.get('is_fraud'))
assert fraud.get('is_fraud') == False

with open('data/questions.json', encoding='utf-8') as f:
    qs = json.load(f)
assert 'to_trinh_xin_kinh_phi' in qs
assert len(qs['to_trinh_xin_kinh_phi']) == 5
print(f"✔ Questions check: {len(qs['to_trinh_xin_kinh_phi'])} questions loaded!")

v = Decree30Validator(out_raw, "to_trinh_xin_kinh_phi", tpl)
res = v.validate_document()
item_5a = next((it for it in res['checklist'] if it['box_id'] == '5a'), None)
assert item_5a is not None, "Phải có Ô 5a"
print(f"✔ Ô 5a recognized correctly: '{item_5a['name']}'")

print("\n🎉 THÀNH CÔNG: Loại văn bản '6. Tờ trình: Xin kinh phí' đã hoạt động 100%!")
