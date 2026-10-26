import json
from engine.validator import Decree30Validator

v = Decree30Validator('storage/uploads/temp_2100001234_01_2100001234_NGUYỄNVĂNA_CongVanDeNghi.docx', 'cong_van_de_nghi')
res = v.validate_document()

for i, item in enumerate(res.get('checklist', [])):
    print(f"Item {i}:", json.dumps(item, ensure_ascii=False))
