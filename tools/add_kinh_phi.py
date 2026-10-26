import json

with open('data/document_templates.json', encoding='utf-8') as f:
    d = json.load(f)

header_part = """cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH
cơ quan ban hành: ĐOÀN THANH NIÊN
quốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
tiêu ngữ: Độc lập - Tự do - Hạnh phúc
số ký hiệu: Số: 35/TTr-ĐTN
địa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 10 tháng 11 năm 2026
tên loại văn bản: TỜ TRÌNH
trích yếu: Về việc xin cấp kinh phí tổ chức Hội thi Sáng tạo sinh viên NTTU năm 2026

Kính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành."""

body_part = """Căn cứ Kế hoạch công tác Đoàn và phong trào thanh niên năm học 2025 - 2026 của Ban Thường vụ Đoàn trường đã được phê duyệt;
Nhằm thúc đẩy phong trào nghiên cứu khoa học, đổi mới sáng tạo và khởi nghiệp trong đoàn viên, sinh viên toàn trường, Ban Thường vụ Đoàn trường xây dựng kế hoạch tổ chức "Hội thi Sáng tạo sinh viên NTTU năm 2026";
Để công tác chuẩn bị và tổ chức hội thi diễn ra thành công tốt đẹp, Ban Thường vụ Đoàn trường kính trình Ban Giám hiệu xem xét, phê duyệt hỗ trợ kinh phí tổ chức, chi tiết như sau:
- Chi phí truyền thông, in ấn băng rôn, phướn, tài liệu hội thi: 15.000.000 đồng;
- Chi phí bồi dưỡng Ban Giám khảo chấm thi vòng sơ khảo và chung kết: 20.000.000 đồng;
- Chi phí giải thưởng cho các đội thi đạt giải (01 giải Nhất, 02 giải Nhì, 03 giải Ba, 05 giải Khuyến khích): 45.000.000 đồng;
- Chi phí tổ chức lễ trao giải và tổng kết hội thi: 10.000.000 đồng.
Tổng kinh phí đề nghị cấp: 90.000.000 đồng (Chín mươi triệu đồng chẵn).
Kính trình Ban Giám hiệu xem xét, phê duyệt để Đoàn trường triển khai thực hiện đúng tiến độ."""

footer_part = """Nơi nhận:
- Như kính gửi;
- Phòng Tài chính - Kế toán;
- Lưu: VT, ĐTN.

BÍ THƯ ĐOÀN TRƯỜNG



Nguyễn Hoàng Long"""

raw_text = f"{header_part}\n\n{body_part}\n\n{footer_part}"

d['to_trinh_xin_kinh_phi'] = {
    'id': 'to_trinh_xin_kinh_phi',
    'name': 'Tờ trình: Xin kinh phí',
    'category': 'Tờ trình',
    'filename_suffix': 'ToTrinhXinKinhPhi',
    'expected_data': {
        'has_type_name': True,
        'type_name': 'TỜ TRÌNH',
        'so_ky_hieu_pattern': 'TTr-ĐTN',
        'has_kinh_gui': True,
        'sign_type': 'KY_TRUC_TIEP'
    },
    'is_body_blank': False,
    'header_part': header_part,
    'body_part': body_part,
    'footer_part': footer_part,
    'raw_text': raw_text
}

with open('data/document_templates.json', 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)

print('Added to_trinh_xin_kinh_phi successfully to document_templates.json!')
