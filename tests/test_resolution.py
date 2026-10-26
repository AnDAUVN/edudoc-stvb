from engine.validator import Decree30Validator

v = Decree30Validator('storage/uploads/temp_2100001234_01_2100001234_NGUYỄNVĂNA_CongVanDeNghi.docx', 'cong_van_de_nghi')
cell = v.doc.tables[1].cell(0, 0)
for i, p in enumerate(cell.paragraphs):
    # Check if runs have text
    runs_with_text = [r for r in p.runs if r.text.strip()]
    print(f"P{i}: text='{p.text}'")
    # If run has explicit sz
    run_sz = None
    for r in p.runs:
        if r.font and r.font.size:
            run_sz = round(r.font.size.pt, 1)
            break
        rPr = getattr(r._element, 'rPr', None)
        if rPr is not None:
            sz_el = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
            if sz_el is not None and sz_el.attrib.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'):
                run_sz = float(sz_el.attrib['{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val']) / 2.0
                break
    print(f"   run_sz: {run_sz}")
    if run_sz is None:
        # Check style
        st = getattr(p, 'style', None)
        style_sz = None
        while st is not None:
            if st.font and st.font.size:
                style_sz = round(st.font.size.pt, 1)
                break
            st = getattr(st, 'base_style', None)
        print(f"   style_sz: {style_sz}")
        print(f"   docDefaults sz: {v.doc_default_size}")
        final_sz = style_sz if style_sz is not None else v.doc_default_size
    else:
        final_sz = run_sz
    print(f"   => FINAL RESOLVED SIZE: {final_sz} pt\n")
