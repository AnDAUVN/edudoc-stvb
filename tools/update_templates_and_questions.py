# -*- coding: utf-8 -*-
import json
import os

BASE_DIR = r"C:\Users\maith\.gemini\antigravity\scratch\edudoc-stvb"
DATA_DIR = os.path.join(BASE_DIR, "data")

templates = {
    "bai_thu_hoach": {
        "id": "bai_thu_hoach",
        "name": "1. Bài thu hoạch",
        "category": "Bài thu hoạch",
        "filename_suffix": "BaiThuHoach",
        "expected_data": {
            "has_type_name": True,
            "type_name": "BÀI THU HOẠCH",
            "so_ky_hieu_pattern": "BTH",
            "has_kinh_gui": False,
            "sign_type": "TRUC_TIEP"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: KHOA CÔNG NGHỆ THÔNG TIN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 01/BTH-ĐT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 25 tháng 10 năm 2026\ntên loại văn bản: BÀI THU HOẠCH\ntrích yếu: Về kết quả học tập chuyên đề kỹ năng soạn thảo văn bản hành chính",
        "body_part": "Kính gửi: Ban Giảng huấn và Bộ môn Kỹ năng mềm.\n\nSau quá trình tham gia khóa bồi dưỡng học phần Kỹ năng soạn thảo văn bản hành chính theo quy chuẩn Nghị định số 30/2020/NĐ-CP của Chính phủ, tôi xin trình bày bài thu hoạch tổng kết các nội dung trọng tâm như sau:\n1. Phần lý thuyết thể thức và kỹ thuật trình bày:\n- Nắm vững 9 thành phần thể thức bắt buộc của văn bản hành chính (từ Ô 1 đến Ô 9), đặc biệt là kỹ thuật căn chỉnh bảng 2x2 ở đầu trang và bảng 1x2 ở chân trang văn bản.\n- Hiểu rõ quy định thống nhất font chữ Times New Roman, quy ước cỡ chữ 'Số trước - Số sau' và quy tắc viết hoa tên cơ quan, tổ chức theo Phụ lục II.\n2. Vận dụng thực tiễn soạn thảo văn bản:\n- Rèn luyện kỹ năng soạn thảo đúng chuẩn các thể loại văn bản thông dụng: Công văn đề nghị, Thông báo, Tờ trình và Báo cáo tổng kết.\n- Nhận diện và khắc phục triệt để các lỗi thường gặp như: sai cỡ chữ Ô 3, sai thể thức đề ký KT./TL., khoảng cách dãn đoạn và lùi đầu dòng chưa đúng chuẩn.\n3. Đề xuất và cam kết rèn luyện:\n- Tiếp tục trau dồi tác phong làm việc khoa học, chuẩn hóa quy trình xử lý văn thư và văn bản điện tử trong môi trường học tập và công tác tương lai.",
        "footer_part": "Nơi nhận:\n- Ban Giảng huấn (để báo cáo);\n- Lưu: Hồ sơ cá nhân.\n\nNGƯỜI THU HOẠCH\n\n\n\nNguyễn Văn A",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: KHOA CÔNG NGHỆ THÔNG TIN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 01/BTH-ĐT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 25 tháng 10 năm 2026\ntên loại văn bản: BÀI THU HOẠCH\ntrích yếu: Về kết quả học tập chuyên đề kỹ năng soạn thảo văn bản hành chính\n\nKính gửi: Ban Giảng huấn và Bộ môn Kỹ năng mềm.\n\nSau quá trình tham gia khóa bồi dưỡng học phần Kỹ năng soạn thảo văn bản hành chính theo quy chuẩn Nghị định số 30/2020/NĐ-CP của Chính phủ, tôi xin trình bày bài thu hoạch tổng kết các nội dung trọng tâm như sau:\n1. Phần lý thuyết thể thức và kỹ thuật trình bày:\n- Nắm vững 9 thành phần thể thức bắt buộc của văn bản hành chính (từ Ô 1 đến Ô 9), đặc biệt là kỹ thuật căn chỉnh bảng 2x2 ở đầu trang và bảng 1x2 ở chân trang văn bản.\n- Hiểu rõ quy định thống nhất font chữ Times New Roman, quy ước cỡ chữ 'Số trước - Số sau' và quy tắc viết hoa tên cơ quan, tổ chức theo Phụ lục II.\n2. Vận dụng thực tiễn soạn thảo văn bản:\n- Rèn luyện kỹ năng soạn thảo đúng chuẩn các thể loại văn bản thông dụng: Công văn đề nghị, Thông báo, Tờ trình và Báo cáo tổng kết.\n- Nhận diện và khắc phục triệt để các lỗi thường gặp như: sai cỡ chữ Ô 3, sai thể thức đề ký KT./TL., khoảng cách dãn đoạn và lùi đầu dòng chưa đúng chuẩn.\n3. Đề xuất và cam kết rèn luyện:\n- Tiếp tục trau dồi tác phong làm việc khoa học, chuẩn hóa quy trình xử lý văn thư và văn bản điện tử trong môi trường học tập và công tác tương lai.\n\nNơi nhận:\n- Ban Giảng huấn (để báo cáo);\n- Lưu: Hồ sơ cá nhân.\n\nNGƯỜI THU HOẠCH\n\n\n\nNguyễn Văn A"
    },
    "cong_van_de_nghi": {
        "id": "cong_van_de_nghi",
        "name": "2. Công văn đề nghị",
        "category": "Công văn hành chính",
        "filename_suffix": "CongVanDeNghi",
        "expected_data": {
            "has_type_name": False,
            "so_ky_hieu_pattern": "CV-DNTT",
            "trich_yeu_prefix": "V/v",
            "has_kinh_gui": True,
            "sign_type": "TRUC_TIEP"
        },
        "is_body_blank": True,
        "header_part": "cơ quan chủ quản: BỘ GIÁO DỤC VÀ ĐÀO TẠO\ncơ quan ban hành: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 12/CV-DNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 15 tháng 01 năm 2026\ntrích yếu công văn: V/v đề nghị hỗ trợ kinh phí\n\nKính gửi: Bộ Khoa học và Công nghệ.",
        "body_part": "",
        "footer_part": "Nơi nhận:\n- Như kính gửi;\n- Lưu: VT.\n\nHIỆU TRƯỞNG\n\n\n\nTrần Ái Cầm",
        "raw_text": "cơ quan chủ quản: BỘ GIÁO DỤC VÀ ĐÀO TẠO\ncơ quan ban hành: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 12/CV-DNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 15 tháng 01 năm 2026\ntrích yếu công văn: V/v đề nghị hỗ trợ kinh phí\n\nKính gửi: Bộ Khoa học và Công nghệ.\n\n[Nội dung văn bản: Sinh viên tự nhập theo nội dung Giảng viên hướng dẫn trực tiếp tại lớp]\n\nNơi nhận:\n- Như kính gửi;\n- Lưu: VT.\n\nHIỆU TRƯỞNG\n\n\n\nTrần Ái Cầm"
    },
    "thong_bao_nhiem_vu": {
        "id": "thong_bao_nhiem_vu",
        "name": "3. Thông báo nhiệm vụ được giao",
        "category": "Thông báo",
        "filename_suffix": "ThongBaoNhiemVu",
        "expected_data": {
            "has_type_name": True,
            "type_name": "THÔNG BÁO",
            "so_ky_hieu_pattern": "TB-ĐT",
            "has_kinh_gui": False,
            "sign_type": "THUA_LENH"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: PHÒNG ĐÀO TẠO\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 45/TB-ĐT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 02 tháng 02 năm 2026\ntên loại văn bản: THÔNG BÁO\ntrích yếu: Về việc phân công nhiệm vụ cán bộ coi thi kết thúc học phần học kỳ 1 năm học 2025 - 2026",
        "body_part": "Thực hiện Kế hoạch tổ chức kỳ thi kết thúc học phần học kỳ 1 năm học 2025 - 2026 đã được Ban Giám hiệu phê duyệt;\nPhòng Đào tạo thông báo đến toàn thể giảng viên, cán bộ quản lý và nhân viên trong Nhà trường về việc thực hiện nhiệm vụ coi thi học kỳ cụ thể như sau:\n1. Toàn bộ cán bộ, giảng viên có tên trong danh sách điều động phải có mặt tại Văn phòng Hội đồng thi trước giờ thi 30 phút để nhận đề và thẻ phân công nhiệm vụ.\n2. Nghiêm túc chấp hành quy chế thi hành chính, tuyệt đối không sử dụng điện thoại di động và các thiết bị thu phát sóng trong suốt thời gian làm nhiệm vụ tại phòng thi.\n3. Bàn giao bài thi, danh sách ký nộp bài và biên bản phòng thi đầy đủ về Ban Thư ký Hội đồng ngay sau khi kết thúc ca thi.\nĐề nghị các đơn vị và cá nhân có liên quan nghiêm túc triển khai thực hiện thông báo này.",
        "footer_part": "Nơi nhận:\n- Ban Giám hiệu (để báo cáo);\n- Các Khoa, Viện đào tạo (để phối hợp);\n- Cán bộ coi thi (để thực hiện);\n- Lưu: VT, ĐT.\n\nTL. HIỆU TRƯỞNG\nTRƯỞNG PHÒNG ĐÀO TẠO\n\n\n\nNguyễn Văn An",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: PHÒNG ĐÀO TẠO\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 45/TB-ĐT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 02 tháng 02 năm 2026\ntên loại văn bản: THÔNG BÁO\ntrích yếu: Về việc phân công nhiệm vụ cán bộ coi thi kết thúc học phần học kỳ 1 năm học 2025 - 2026\n\nThực hiện Kế hoạch tổ chức kỳ thi kết thúc học phần học kỳ 1 năm học 2025 - 2026 đã được Ban Giám hiệu phê duyệt;\nPhòng Đào tạo thông báo đến toàn thể giảng viên, cán bộ quản lý và nhân viên trong Nhà trường về việc thực hiện nhiệm vụ coi thi học kỳ cụ thể như sau:\n1. Toàn bộ cán bộ, giảng viên có tên trong danh sách điều động phải có mặt tại Văn phòng Hội đồng thi trước giờ thi 30 phút để nhận đề và thẻ phân công nhiệm vụ.\n2. Nghiêm túc chấp hành quy chế thi hành chính, tuyệt đối không sử dụng điện thoại di động và các thiết bị thu phát sóng trong suốt thời gian làm nhiệm vụ tại phòng thi.\n3. Bàn giao bài thi, danh sách ký nộp bài và biên bản phòng thi đầy đủ về Ban Thư ký Hội đồng ngay sau khi kết thúc ca thi.\nĐề nghị các đơn vị và cá nhân có liên quan nghiêm túc triển khai thực hiện thông báo này.\n\nNơi nhận:\n- Ban Giám hiệu (để báo cáo);\n- Các Khoa, Viện đào tạo (để phối hợp);\n- Cán bộ coi thi (để thực hiện);\n- Lưu: VT, ĐT.\n\nTL. HIỆU TRƯỞNG\nTRƯỞNG PHÒNG ĐÀO TẠO\n\n\n\nNguyễn Văn An"
    },
    "thong_bao_hoat_dong": {
        "id": "thong_bao_hoat_dong",
        "name": "4. Thông báo thông tin hoạt động",
        "category": "Thông báo",
        "filename_suffix": "ThongBaoHoatDong",
        "expected_data": {
            "has_type_name": True,
            "type_name": "THÔNG BÁO",
            "so_ky_hieu_pattern": "TB-ĐTN",
            "has_kinh_gui": False,
            "sign_type": "TRUC_TIEP"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: ĐOÀN THANH NIÊN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 08/TB-ĐTN\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 08 tháng 03 năm 2026\ntên loại văn bản: THÔNG BÁO\ntrích yếu: Về việc tổ chức chiến dịch tình nguyện Mùa hè xanh năm 2026",
        "body_part": "Nhằm phát huy tinh thần xung kích, tình nguyện của tuổi trẻ sinh viên Nhà trường vì sự phát triển của cộng đồng xã hội;\nĐoàn Thanh niên Trường Đại học Nguyễn Tất Thành thông báo về việc phát động và tuyển quân Chiến dịch tình nguyện Mùa hè xanh năm 2026 với các nội dung sau:\n1. Thời gian đăng ký: Từ ngày 10 tháng 4 năm 2026 đến hết ngày 30 tháng 4 năm 2026 tại Văn phòng Đoàn Thanh niên.\n2. Địa bàn hoạt động tình nguyện: Tỉnh Bến Tre và các xã nông thôn mới ngoại thành Thành phố Hồ Chí Minh.\n3. Đối tượng tham gia: Toàn thể đoàn viên, thanh niên, sinh viên hệ chính quy đang theo học tại các khoa, viện trong toàn trường.\nThông tin chi tiết về hồ sơ và thủ tục đăng ký xem tại bảng tin Đoàn trường hoặc cổng thông tin điện tử sinh viên.",
        "footer_part": "Nơi nhận:\n- Đảng ủy, Ban Giám hiệu (để báo cáo);\n- Các Liên chi đoàn, Chi đoàn sinh viên;\n- Lưu: VT, ĐTN.\n\nBÍ THƯ ĐOÀN TRƯỜNG\n\n\n\nLê Văn Bình",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: ĐOÀN THANH NIÊN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 08/TB-ĐTN\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 08 tháng 03 năm 2026\ntên loại văn bản: THÔNG BÁO\ntrích yếu: Về việc tổ chức chiến dịch tình nguyện Mùa hè xanh năm 2026\n\nNhằm phát huy tinh thần xung kích, tình nguyện của tuổi trẻ sinh viên Nhà trường vì sự phát triển của cộng đồng xã hội;\nĐoàn Thanh niên Trường Đại học Nguyễn Tất Thành thông báo về việc phát động và tuyển quân Chiến dịch tình nguyện Mùa hè xanh năm 2026 với các nội dung sau:\n1. Thời gian đăng ký: Từ ngày 10 tháng 4 năm 2026 đến hết ngày 30 tháng 4 năm 2026 tại Văn phòng Đoàn Thanh niên.\n2. Địa bàn hoạt động tình nguyện: Tỉnh Bến Tre và các xã nông thôn mới ngoại thành Thành phố Hồ Chí Minh.\n3. Đối tượng tham gia: Toàn thể đoàn viên, thanh niên, sinh viên hệ chính quy đang theo học tại các khoa, viện trong toàn trường.\nThông tin chi tiết về hồ sơ và thủ tục đăng ký xem tại bảng tin Đoàn trường hoặc cổng thông tin điện tử sinh viên.\n\nNơi nhận:\n- Đảng ủy, Ban Giám hiệu (để báo cáo);\n- Các Liên chi đoàn, Chi đoàn sinh viên;\n- Lưu: VT, ĐTN.\n\nBÍ THƯ ĐOÀN TRƯỜNG\n\n\n\nLê Văn Bình"
    },
    "to_trinh_xin_kinh_phi": {
        "id": "to_trinh_xin_kinh_phi",
        "name": "5. Tờ trình xin kinh phí",
        "category": "Tờ trình",
        "filename_suffix": "ToTrinhXinKinhPhi",
        "expected_data": {
            "has_type_name": True,
            "type_name": "TỜ TRÌNH",
            "so_ky_hieu_pattern": "TTr-ĐTN",
            "has_kinh_gui": True,
            "sign_type": "KY_TRUC_TIEP"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: ĐOÀN THANH NIÊN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 35/TTr-ĐTN\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 10 tháng 11 năm 2026\ntên loại văn bản: TỜ TRÌNH\ntrích yếu: Về việc xin cấp kinh phí tổ chức Hội thi Sáng tạo sinh viên NTTU năm 2026\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.",
        "body_part": "Căn cứ Kế hoạch công tác Đoàn và phong trào thanh niên năm học 2025 - 2026 của Ban Thường vụ Đoàn trường đã được phê duyệt;\nNhằm thúc đẩy phong trào nghiên cứu khoa học, đổi mới sáng tạo và khởi nghiệp trong đoàn viên, sinh viên toàn trường, Ban Thường vụ Đoàn trường xây dựng kế hoạch tổ chức \"Hội thi Sáng tạo sinh viên NTTU năm 2026\";\nĐể công tác chuẩn bị và tổ chức hội thi diễn ra thành công tốt đẹp, Ban Thường vụ Đoàn trường kính trình Ban Giám hiệu xem xét, phê duyệt hỗ trợ kinh phí tổ chức, chi tiết như sau:\n- Chi phí truyền thông, in ấn băng rôn, phướn, tài liệu hội thi: 15.000.000 đồng;\n- Chi phí bồi dưỡng Ban Giám khảo chấm thi vòng sơ khảo và chung kết: 20.000.000 đồng;\n- Chi phí giải thưởng cho các đội thi đạt giải (01 giải Nhất, 02 giải Nhì, 03 giải Ba, 05 giải Khuyến khích): 45.000.000 đồng;\n- Chi phí tổ chức lễ trao giải và tổng kết hội thi: 10.000.000 đồng.\nTổng kinh phí đề nghị cấp: 90.000.000 đồng (Chín mươi triệu đồng chẵn).\nKính trình Ban Giám hiệu xem xét, phê duyệt để Đoàn trường triển khai thực hiện đúng tiến độ.",
        "footer_part": "Nơi nhận:\n- Như kính gửi;\n- Phòng Tài chính - Kế toán;\n- Lưu: VT, ĐTN.\n\nBÍ THƯ ĐOÀN TRƯỜNG\n\n\n\nNguyễn Hoàng Long",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: ĐOÀN THANH NIÊN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 35/TTr-ĐTN\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 10 tháng 11 năm 2026\ntên loại văn bản: TỜ TRÌNH\ntrích yếu: Về việc xin cấp kinh phí tổ chức Hội thi Sáng tạo sinh viên NTTU năm 2026\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.\n\nCăn cứ Kế hoạch công tác Đoàn và phong trào thanh niên năm học 2025 - 2026 của Ban Thường vụ Đoàn trường đã được phê duyệt;\nNhằm thúc đẩy phong trào nghiên cứu khoa học, đổi mới sáng tạo và khởi nghiệp trong đoàn viên, sinh viên toàn trường, Ban Thường vụ Đoàn trường xây dựng kế hoạch tổ chức \"Hội thi Sáng tạo sinh viên NTTU năm 2026\";\nĐể công tác chuẩn bị và tổ chức hội thi diễn ra thành công tốt đẹp, Ban Thường vụ Đoàn trường kính trình Ban Giám hiệu xem xét, phê duyệt hỗ trợ kinh phí tổ chức, chi tiết như sau:\n- Chi phí truyền thông, in ấn băng rôn, phướn, tài liệu hội thi: 15.000.000 đồng;\n- Chi phí bồi dưỡng Ban Giám khảo chấm thi vòng sơ khảo và chung kết: 20.000.000 đồng;\n- Chi phí giải thưởng cho các đội thi đạt giải (01 giải Nhất, 02 giải Nhì, 03 giải Ba, 05 giải Khuyến khích): 45.000.000 đồng;\n- Chi phí tổ chức lễ trao giải và tổng kết hội thi: 10.000.000 đồng.\nTổng kinh phí đề nghị cấp: 90.000.000 đồng (Chín mươi triệu đồng chẵn).\nKính trình Ban Giám hiệu xem xét, phê duyệt để Đoàn trường triển khai thực hiện đúng tiến độ.\n\nNơi nhận:\n- Như kính gửi;\n- Phòng Tài chính - Kế toán;\n- Lưu: VT, ĐTN.\n\nBÍ THƯ ĐOÀN TRƯỜNG\n\n\n\nNguyễn Hoàng Long"
    },
    "to_trinh_nhan_su": {
        "id": "to_trinh_nhan_su",
        "name": "6. Tờ trình xin bổ sung nhân sự",
        "category": "Tờ trình",
        "filename_suffix": "ToTrinhNhanSu",
        "expected_data": {
            "has_type_name": True,
            "type_name": "TỜ TRÌNH",
            "so_ky_hieu_pattern": "TTr-CNTT",
            "has_kinh_gui": True,
            "sign_type": "TRUC_TIEP"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: KHOA CÔNG NGHỆ THÔNG TIN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 15/TTr-CNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 18 tháng 09 năm 2026\ntên loại văn bản: TỜ TRÌNH\ntrích yếu: Về việc xin bổ sung nhân sự giảng viên cơ hữu Bộ môn Kỹ thuật phần mềm\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.",
        "body_part": "Căn cứ quy mô phát triển số lượng sinh viên ngành Công nghệ thông tin trong năm học 2026 - 2027;\nCăn cứ vào khối lượng giờ giảng thực tế và định mức giảng dạy quy định của giảng viên cơ hữu thuộc Bộ môn Kỹ thuật phần mềm;\nHiện nay, số lượng giảng viên cơ hữu của Bộ môn chưa đáp ứng đủ tỷ lệ giảng dạy theo yêu cầu chuẩn kiểm định chất lượng giáo dục đại học.\nĐể đảm bảo tiến độ và chất lượng giảng dạy, Khoa Công nghệ thông tin kính trình Ban Giám hiệu xem xét, phê duyệt chủ trương tuyển dụng bổ sung nhân sự như sau:\n1. Số lượng cần tuyển: 03 giảng viên cơ hữu.\n2. Yêu cầu trình độ: Thạc sĩ trở lên chuyên ngành Công nghệ thông tin, Khoa học máy tính hoặc Kỹ thuật phần mềm; ưu tiên ứng viên có chứng chỉ bồi dưỡng nghiệp vụ sư phạm và khả năng giảng dạy chuyên ngành bằng tiếng Anh.\nKính trình Ban Giám hiệu xem xét và quyết định.",
        "footer_part": "Nơi nhận:\n- Như kính gửi;\n- Phòng Tổ chức - Nhân sự;\n- Lưu: VT, Khoa CNTT.\n\nTRƯỞNG KHOA\n\n\n\nHoàng Minh Trí",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: KHOA CÔNG NGHỆ THÔNG TIN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 15/TTr-CNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 18 tháng 09 năm 2026\ntên loại văn bản: TỜ TRÌNH\ntrích yếu: Về việc xin bổ sung nhân sự giảng viên cơ hữu Bộ môn Kỹ thuật phần mềm\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.\n\nCăn cứ quy mô phát triển số lượng sinh viên ngành Công nghệ thông tin trong năm học 2026 - 2027;\nCăn cứ vào khối lượng giờ giảng thực tế và định mức giảng dạy quy định của giảng viên cơ hữu thuộc Bộ môn Kỹ thuật phần mềm;\nHiện nay, số lượng giảng viên cơ hữu của Bộ môn chưa đáp ứng đủ tỷ lệ giảng dạy theo yêu cầu chuẩn kiểm định chất lượng giáo dục đại học.\nĐể đảm bảo tiến độ và chất lượng giảng dạy, Khoa Công nghệ thông tin kính trình Ban Giám hiệu xem xét, phê duyệt chủ trương tuyển dụng bổ sung nhân sự như sau:\n1. Số lượng cần tuyển: 03 giảng viên cơ hữu.\n2. Yêu cầu trình độ: Thạc sĩ trở lên chuyên ngành Công nghệ thông tin, Khoa học máy tính hoặc Kỹ thuật phần mềm; ưu tiên ứng viên có chứng chỉ bồi dưỡng nghiệp vụ sư phạm và khả năng giảng dạy chuyên ngành bằng tiếng Anh.\nKính trình Ban Giám hiệu xem xét và quyết định.\n\nNơi nhận:\n- Như kính gửi;\n- Phòng Tổ chức - Nhân sự;\n- Lưu: VT, Khoa CNTT.\n\nTRƯỞNG KHOA\n\n\n\nHoàng Minh Trí"
    },
    "to_trinh_thiet_bi": {
        "id": "to_trinh_thiet_bi",
        "name": "7. Tờ trình xin máy móc thiết bị",
        "category": "Tờ trình",
        "filename_suffix": "ToTrinhThietBi",
        "expected_data": {
            "has_type_name": True,
            "type_name": "TỜ TRÌNH",
            "so_ky_hieu_pattern": "TTr-KNN",
            "has_kinh_gui": True,
            "sign_type": "KY_THAY"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: TRUNG TÂM ĐÀO TẠO KỸ NĂNG NGHỀ\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 22/TTr-KNN\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 24 tháng 10 năm 2026\ntên loại văn bản: TỜ TRÌNH\ntrích yếu: Về việc xin trang bị bổ sung máy chiếu và dàn máy vi tính phòng thực hành\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.",
        "body_part": "Căn cứ vào nhu cầu thực tế phục vụ kỳ thi đánh giá kỹ năng nghề bậc 3 cho sinh viên khóa tốt nghiệp năm 2026;\nQua rà soát hiện trạng cơ sở vật chất tại Khu thực hành công nghệ cơ sở An Phú Đông, hiện có 05 máy chiếu đã mờ bóng đèn và 20 bộ máy vi tính cấu hình cũ không còn đáp ứng việc chạy các phần mềm đồ họa và giả lập chuyên ngành;\nĐể phục vụ tốt công tác giảng dạy và thi cử cho sinh viên, Trung tâm kính đề nghị Ban Giám hiệu xem xét, phê duyệt kinh phí mua sắm trang thiết bị bổ sung:\n- 05 máy chiếu đa năng công suất lớn phục vụ các phòng học lý thuyết;\n- 20 bộ máy vi tính để bàn cấu hình Core i5, RAM 16GB phục vụ phòng thi thực hành.\nDự toán tổng kinh phí dự kiến: 350.000.000 đồng (Ba trăm năm mươi triệu đồng chẵn).\nKính trình Ban Giám hiệu xem xét, phê duyệt để đơn vị kịp thời triển khai mua sắm.",
        "footer_part": "Nơi nhận:\n- Như kính gửi;\n- Phòng Quản trị thiết bị;\n- Phòng Tài chính - Kế toán;\n- Lưu: VT, TT KNN.\n\nKT. GIÁM ĐỐC\nPHÓ GIÁM ĐỐC\n\n\n\nVõ Thị Kim Anh",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: TRUNG TÂM ĐÀO TẠO KỸ NĂNG NGHỀ\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 22/TTr-KNN\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 24 tháng 10 năm 2026\ntên loại văn bản: TỜ TRÌNH\ntrích yếu: Về việc xin trang bị bổ sung máy chiếu và dàn máy vi tính phòng thực hành\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.\n\nCăn cứ vào nhu cầu thực tế phục vụ kỳ thi đánh giá kỹ năng nghề bậc 3 cho sinh viên khóa tốt nghiệp năm 2026;\nQua rà soát hiện trạng cơ sở vật chất tại Khu thực hành công nghệ cơ sở An Phú Đông, hiện có 05 máy chiếu đã mờ bóng đèn và 20 bộ máy vi tính cấu hình cũ không còn đáp ứng việc chạy các phần mềm đồ họa và giả lập chuyên ngành;\nĐể phục vụ tốt công tác giảng dạy và thi cử cho sinh viên, Trung tâm kính đề nghị Ban Giám hiệu xem xét, phê duyệt kinh phí mua sắm trang thiết bị bổ sung:\n- 05 máy chiếu đa năng công suất lớn phục vụ các phòng học lý thuyết;\n- 20 bộ máy vi tính để bàn cấu hình Core i5, RAM 16GB phục vụ phòng thi thực hành.\nDự toán tổng kinh phí dự kiến: 350.000.000 đồng (Ba trăm năm mươi triệu đồng chẵn).\nKính trình Ban Giám hiệu xem xét, phê duyệt để đơn vị kịp thời triển khai mua sắm.\n\nNơi nhận:\n- Như kính gửi;\n- Phòng Quản trị thiết bị;\n- Phòng Tài chính - Kế toán;\n- Lưu: VT, TT KNN.\n\nKT. GIÁM ĐỐC\nPHÓ GIÁM ĐỐC\n\n\n\nVõ Thị Kim Anh"
    },
    "bao_cao": {
        "id": "bao_cao",
        "name": "8. Báo cáo",
        "category": "Báo cáo",
        "filename_suffix": "BaoCao",
        "expected_data": {
            "has_type_name": True,
            "type_name": "BÁO CÁO",
            "so_ky_hieu_pattern": "BC-CNTT",
            "has_kinh_gui": True,
            "sign_type": "TRUC_TIEP"
        },
        "is_body_blank": False,
        "header_part": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: KHOA CÔNG NGHỆ THÔNG TIN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 18/BC-CNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 25 tháng 10 năm 2026\ntên loại văn bản: BÁO CÁO\ntrích yếu: Về tình hình thực hiện công tác đào tạo và nghiên cứu khoa học học kỳ 1 năm học 2025 - 2026\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.",
        "body_part": "Thực hiện Kế hoạch năm học 2025 - 2026 của Nhà trường, Khoa Công nghệ thông tin kính báo cáo tình hình thực hiện nhiệm vụ công tác đào tạo và nghiên cứu khoa học học kỳ 1 với các kết quả cụ thể như sau:\n1. Về công tác đào tạo và quản lý sinh viên: Hoàn thành 100% khối lượng giờ giảng đúng tiến độ đề ra; tổ chức kỳ thi kết thúc học phần nghiêm túc, đúng quy chế; tỷ lệ sinh viên đạt kết quả học tập loại Khá, Giỏi đạt trên 75%.\n2. Về hoạt động nghiên cứu khoa học: Đơn vị đã tổ chức thành công 02 hội thảo học thuật chuyên ngành, nghiệm thu đúng hạn 05 đề tài nghiên cứu khoa học cấp cơ sở và triển khai chương trình liên kết thực tập với 10 doanh nghiệp công nghệ đối tác.\n3. Phương hướng nhiệm vụ trọng tâm học kỳ 2: Tiếp tục chuẩn hóa học liệu số, đổi mới phương pháp giảng dạy lấy người học làm trung tâm và hoàn thiện hồ sơ phục vụ công tác kiểm định chất lượng chương trình đào tạo.\nKhoa Công nghệ thông tin kính báo cáo Ban Giám hiệu xem xét và chỉ đạo.",
        "footer_part": "Nơi nhận:\n- Như kính gửi;\n- Phòng Đào tạo;\n- Phòng Khoa học Công nghệ;\n- Lưu: VT, Khoa CNTT.\n\nTRƯỞNG KHOA\n\n\n\nHoàng Minh Trí",
        "raw_text": "cơ quan chủ quản: TRƯỜNG ĐẠI HỌC NGUYỄN TẤT THÀNH\ncơ quan ban hành: KHOA CÔNG NGHỆ THÔNG TIN\nquốc hiệu: CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\ntiêu ngữ: Độc lập - Tự do - Hạnh phúc\nsố ký hiệu: Số: 18/BC-CNTT\nđịa danh ngày tháng: Thành phố Hồ Chí Minh, ngày 25 tháng 10 năm 2026\ntên loại văn bản: BÁO CÁO\ntrích yếu: Về tình hình thực hiện công tác đào tạo và nghiên cứu khoa học học kỳ 1 năm học 2025 - 2026\n\nKính gửi: Ban Giám hiệu Trường Đại học Nguyễn Tất Thành.\n\nThực hiện Kế hoạch năm học 2025 - 2026 của Nhà trường, Khoa Công nghệ thông tin kính báo cáo tình hình thực hiện nhiệm vụ công tác đào tạo và nghiên cứu khoa học học kỳ 1 với các kết quả cụ thể như sau:\n1. Về công tác đào tạo và quản lý sinh viên: Hoàn thành 100% khối lượng giờ giảng đúng tiến độ đề ra; tổ chức kỳ thi kết thúc học phần nghiêm túc, đúng quy chế; tỷ lệ sinh viên đạt kết quả học tập loại Khá, Giỏi đạt trên 75%.\n2. Về hoạt động nghiên cứu khoa học: Đơn vị đã tổ chức thành công 02 hội thảo học thuật chuyên ngành, nghiệm thu đúng hạn 05 đề tài nghiên cứu khoa học cấp cơ sở và triển khai chương trình liên kết thực tập với 10 doanh nghiệp công nghệ đối tác.\n3. Phương hướng nhiệm vụ trọng tâm học kỳ 2: Tiếp tục chuẩn hóa học liệu số, đổi mới phương pháp giảng dạy lấy người học làm trung tâm và hoàn thiện hồ sơ phục vụ công tác kiểm định chất lượng chương trình đào tạo.\nKhoa Công nghệ thông tin kính báo cáo Ban Giám hiệu xem xét và chỉ đạo.\n\nNơi nhận:\n- Như kính gửi;\n- Phòng Đào tạo;\n- Phòng Khoa học Công nghệ;\n- Lưu: VT, Khoa CNTT.\n\nTRƯỞNG KHOA\n\n\n\nHoàng Minh Trí"
    }
}

# 1. Update templates file
templates_path = os.path.join(DATA_DIR, "document_templates.json")
with open(templates_path, "w", encoding="utf-8") as f:
    json.dump(templates, f, ensure_ascii=False, indent=2)

print(f"[OK] Saved {len(templates)} templates to {templates_path}")

# 2. Update questions file
questions_path = os.path.join(DATA_DIR, "questions.json")
with open(questions_path, "r", encoding="utf-8") as f:
    questions_data = json.load(f)

# Bài thu hoạch questions
bai_thu_hoach_questions = [
    {
        "id": 1,
        "question": "Trong văn bản Bài thu hoạch, phần Tên loại văn bản (Ô 5a) được trình bày theo quy chuẩn nào?",
        "options": [
            "Chữ in hoa, đứng, in đậm, cỡ chữ 13-14, đặt canh giữa trang giấy",
            "Chữ in thường, nghiêng, cỡ chữ 12, đặt sát lề trái",
            "Chữ in hoa, in nghiêng, cỡ chữ 15, đặt trong bảng đầu trang",
            "Chữ in thường, đứng, cỡ chữ 11, đặt dưới nơi nhận"
        ],
        "correct": 0,
        "explanation": "Theo quy chuẩn thể thức văn bản hành chính và tài liệu bồi dưỡng, Tên loại 'BÀI THU HOẠCH' được trình bày bằng chữ in hoa, kiểu chữ đứng, in đậm, cỡ chữ từ 13 đến 14, đặt canh giữa trang giấy."
    },
    {
        "id": 2,
        "question": "Tại góc ký tên (Ô 7a và Ô 7b) của Bài thu hoạch, phần chức danh/tư cách người làm bài được trình bày như thế nào?",
        "options": [
            "Ghi 'NGƯỜI THU HOẠCH' (hoặc 'NGƯỜI LÀM BÀI', 'HỌC VIÊN'), chữ in hoa, in đậm, đứng, cỡ chữ 13-14, canh giữa",
            "Ghi 'Người thu hoạch', chữ in thường, in nghiêng, cỡ chữ 12, canh lề trái",
            "Ghi viết tắt 'KT.' kèm chức vụ cấp phó",
            "Không cần ghi chức danh, chỉ cần ký và ghi họ tên"
        ],
        "correct": 0,
        "explanation": "Phần chức danh người làm bài (Ô 7a) trong Bài thu hoạch trình bày bằng chữ in hoa, in đậm, đứng, cỡ chữ 13-14 (ví dụ: 'NGƯỜI THU HOẠCH' hoặc 'NGƯỜI LÀM BÀI')."
    },
    {
        "id": 3,
        "question": "Khoảng cách từ dòng Chức danh/Tư cách người làm bài đến Họ và tên người thực hiện (Ô 8) trong Bài thu hoạch cần cách bao nhiêu để ký tên?",
        "options": [
            "Cách từ 2.0 đến 2.5 cm (tương đương 3-4 dòng trống)",
            "Không cần cách dòng, viết liền sát nhau",
            "Cách 5 đến 7 cm",
            "Cách 0.5 cm"
        ],
        "correct": 0,
        "explanation": "Khoảng cách giữa chức danh (Ô 7a) và họ tên (Ô 7b) là khoảng trống Ô 8 từ 2.0 - 2.5 cm (khoảng 3 - 4 dòng trống) dành để ký tên."
    },
    {
        "id": 4,
        "question": "Định dạng các đoạn văn phần Thân bài (Ô 6) của Bài thu hoạch cần tuân thủ quy chuẩn nào?",
        "options": [
            "Font chữ Times New Roman, cỡ 13-14, dàn đều 2 bên (Justify), lùi đầu dòng 1 - 1.27 cm, giãn đoạn tối thiểu 6pt",
            "Font Arial, cỡ chữ 11, căn lề trái, không thụt đầu dòng",
            "Font Calibri, cỡ 15, căn giữa toàn bộ bài",
            "Font Tahoma, cỡ 12, giãn dòng 2.0 lines, căn lề phải"
        ],
        "correct": 0,
        "explanation": "Toàn bộ nội dung văn bản sử dụng font Times New Roman, cỡ chữ 13 hoặc 14 thống nhất, căn lề hai bên (Justify), dòng đầu tiên của mỗi đoạn lùi 1 - 1.27 cm, giãn đoạn tối thiểu 6pt."
    },
    {
        "id": 5,
        "question": "Quy chuẩn căn lề trang giấy (Page Margins) khi trình bày Bài thu hoạch theo Nghị định 30 là gì?",
        "options": [
            "Lề trên: 20-25mm, Lề dưới: 20-25mm, Lề trái: 30-35mm, Lề phải: 15-20mm",
            "Lề trên: 10mm, Lề dưới: 10mm, Lề trái: 20mm, Lề phải: 10mm",
            "Cả 4 lề đều bằng 20mm",
            "Lề trên: 30mm, Lề dưới: 30mm, Lề trái: 20mm, Lề phải: 20mm"
        ],
        "correct": 0,
        "explanation": "Theo Phụ lục I Nghị định 30/2020/NĐ-CP: Lề trên: 20-25mm, Lề dưới: 20-25mm, Lề trái: 30-35mm (để đóng gáy), Lề phải: 15-20mm."
    }
]

# Báo cáo questions
bao_cao_questions = [
    {
        "id": 1,
        "question": "Trong văn bản Báo cáo hành chính, ký hiệu văn bản tại Ô 3 được cấu thành theo công thức nào sau đây là ĐÚNG?",
        "options": [
            "Số: .../BC-<Chữ viết tắt tên cơ quan, tổ chức ban hành>",
            "Số: .../BCAO-<Tên cơ quan>",
            "Số: .../CV-BC",
            "Số: .../TTr-BC"
        ],
        "correct": 0,
        "explanation": "Theo Nghị định 30/2020/NĐ-CP, Báo cáo là văn bản có tên loại, chữ viết tắt tên loại là 'BC'. Ký hiệu văn bản có dạng: Số: .../BC-<Tên cơ quan/đơn vị ban hành> (Ví dụ: Số: 18/BC-CNTT hoặc Số: 25/BC-ĐHNTT)."
    },
    {
        "id": 2,
        "question": "Tại Ô 5a của Báo cáo hành chính, phần Tên loại và Trích yếu nội dung văn bản được trình bày như thế nào?",
        "options": [
            "Dòng 1: 'BÁO CÁO' (in hoa, đậm, giữa); Dòng 2: Trích yếu 'Về...' (in thường, đứng, đậm, giữa, có gạch ngang 1/3-1/2)",
            "Cả Tên loại và Trích yếu đều in hoa, nghiêng, đặt sát lề trái",
            "Tên loại in thường, trích yếu in hoa trong bảng đầu trang",
            "Chỉ ghi trích yếu 'V/v...', không có dòng chữ BÁO CÁO"
        ],
        "correct": 0,
        "explanation": "Ô 5a gồm 2 dòng: Dòng trên là tên loại văn bản 'BÁO CÁO' (in hoa, đứng, đậm, 13-14pt); Dòng dưới là trích yếu nội dung (in thường, đứng, đậm, 13-14pt, bên dưới có đường kẻ nét liền dài bằng 1/3 đến 1/2 độ dài dòng chữ)."
    },
    {
        "id": 3,
        "question": "Báo cáo gửi cơ quan cấp trên hoặc cơ quan quản lý thì mục Nơi nhận trực tiếp 'Kính gửi:' (Ô 9a) được trình bày ở vị trí nào?",
        "options": [
            "Đặt sau phần Trích yếu nội dung (Ô 5a) và trước khi bắt đầu phần nội dung báo cáo",
            "Đặt ở góc dưới cùng bên trái của trang giấy, cạnh phần người ký",
            "Đặt trong Bảng đầu trang, ngay dưới số ký hiệu văn bản",
            "Đặt ở cuối báo cáo, sau chữ ký của thủ trưởng cơ quan"
        ],
        "correct": 0,
        "explanation": "Mục Kính gửi (Ô 9a) của Báo cáo được trình bày sau Trích yếu văn bản (Ô 5a) và trước khi bắt đầu nội dung báo cáo (Ô 6)."
    },
    {
        "id": 4,
        "question": "Tại góc ký tên (Ô 7a, Ô 8, Ô 7b) của Báo cáo, trường hợp cấp phó ký thay người đứng đầu thì thể thức đề ký nào là ĐÚNG?",
        "options": [
            "Dòng 1: 'KT. GIÁM ĐỐC' (hoặc KT. HIỆU TRƯỞNG), Dòng 2: 'PHÓ GIÁM ĐỐC' (hoặc PHÓ HIỆU TRƯỞNG), in hoa, đậm, giữa",
            "Chỉ ghi một dòng duy nhất: 'PHÓ GIÁM ĐỐC'",
            "Ghi 'TL. GIÁM ĐỐC / PHÓ GIÁM ĐỐC'",
            "Ghi 'TM. BAN GIÁM ĐỐC / PHÓ GIÁM ĐỐC'"
        ],
        "correct": 0,
        "explanation": "Theo Nghị định 30/2020/NĐ-CP, cấp phó ký thay người đứng đầu sử dụng thể thức 'KT.' gồm 2 dòng: Dòng 1 ghi 'KT. <CHỨC VỤ NGƯỜI ĐỨNG ĐẦU>', Dòng 2 ghi chức vụ cấp phó trực tiếp ký (đều in hoa, in đậm, căn giữa)."
    },
    {
        "id": 5,
        "question": "Tại Ô 9b (Nơi nhận ở chân trang) của Báo cáo gửi cấp trên, dòng đầu tiên trong danh sách nơi nhận thường là gì?",
        "options": [
            "- Như kính gửi;",
            "- Kính gửi cơ quan cấp trên;",
            "- Ban Giám đốc;",
            "- Lưu: VT."
        ],
        "correct": 0,
        "explanation": "Khi văn bản có mục 'Kính gửi:' ở Ô 9a, tại phần nơi nhận Ô 9b dòng đầu tiên của danh sách nơi nhận sẽ ghi '- Như kính gửi;'."
    }
]

# Preserve question order matching templates
ordered_questions = {
    "bai_thu_hoach": bai_thu_hoach_questions,
    "cong_van_de_nghi": questions_data.get("cong_van_de_nghi", []),
    "thong_bao_nhiem_vu": questions_data.get("thong_bao_nhiem_vu", []),
    "thong_bao_hoat_dong": questions_data.get("thong_bao_hoat_dong", []),
    "to_trinh_xin_kinh_phi": questions_data.get("to_trinh_xin_kinh_phi", []),
    "to_trinh_nhan_su": questions_data.get("to_trinh_nhan_su", []),
    "to_trinh_thiet_bi": questions_data.get("to_trinh_thiet_bi", []),
    "bao_cao": bao_cao_questions
}

with open(questions_path, "w", encoding="utf-8") as f:
    json.dump(ordered_questions, f, ensure_ascii=False, indent=2)

print(f"[OK] Saved questions bank for {len(ordered_questions)} documents to {questions_path}")
for k, qs in ordered_questions.items():
    print(f" - {k}: {len(qs)} câu hỏi")
