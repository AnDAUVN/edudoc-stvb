import docx

doc = docx.Document('storage/uploads/temp_2100001234_01_2100001234_NGUYỄNVĂNA_CongVanDeNghi.docx')

print("Styles in doc:")
for s in doc.styles:
    if s.name in ['Normal', 'List Paragraph', 'Default Paragraph Font']:
        f_sz = s.font.size.pt if s.font.size else None
        print(f"Style '{s.name}': font.name={s.font.name}, font.size={f_sz}")

# Let's inspect styles.xml directly:
import zipfile, xml.etree.ElementTree as ET
with zipfile.ZipFile('storage/uploads/temp_2100001234_01_2100001234_NGUYỄNVĂNA_CongVanDeNghi.docx') as z:
    styles_xml = z.read('word/styles.xml')
    root = ET.fromstring(styles_xml)
    docDefaults = root.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}docDefaults')
    if docDefaults is not None:
        rPrDefault = docDefaults.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPrDefault')
        if rPrDefault is not None:
            rPr = rPrDefault.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
            if rPr is not None:
                sz = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
                szCs = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}szCs')
                rFonts = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts')
                print("docDefaults rPr:")
                print("  sz:", float(sz.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'))/2.0 if sz is not None else None)
                print("  szCs:", float(szCs.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'))/2.0 if szCs is not None else None)
                if rFonts is not None:
                    print("  rFonts:", rFonts.attrib)
                    
    # Also check style id="ListParagraph"
    for style in root.findall('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}style'):
        s_id = style.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}styleId')
        if s_id in ['ListParagraph', 'Normal']:
            rPr = style.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr')
            if rPr is not None:
                sz = rPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sz')
                print(f"Style {s_id} sz:", float(sz.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val'))/2.0 if sz is not None else None)
            else:
                print(f"Style {s_id} has no rPr")
