import os, docx

files = sorted(os.listdir('storage/uploads'), key=lambda x: os.path.getmtime(os.path.join('storage/uploads', x)), reverse=True)
latest_file = os.path.join('storage/uploads', files[0])
print('Latest file:', latest_file)

doc = docx.Document(latest_file)
cell = doc.tables[1].cell(0, 0)
for i, p in enumerate(cell.paragraphs):
    print(f"P{i}: text='{p.text}'")
    for r in p.runs:
        rPr = getattr(r._element, 'rPr', None)
        sz = None
        if rPr is not None:
            sz_el = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
            if sz_el is not None:
                sz = float(sz_el.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val')) / 2.0
        print(f"   run: text='{r.text}', sz={r.font.size.pt if r.font.size else None}, rPr_sz={sz}")
