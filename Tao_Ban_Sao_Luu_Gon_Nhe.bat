@echo off
chcp 65001 > nul
title Đóng gói Mã nguồn Sạch & Siêu Nhẹ (EduDoc STVB)
cd /d "%~dp0"
echo ======================================================================
echo    ĐANG TẠO BẢN SAO LƯU MÃ NGUỒN SẠCH (LOẠI BỎ .GIT, PYCACHE, RÁC)
echo ======================================================================
python tools\create_clean_package.py
echo.
echo Nhấn phím bất kỳ để mở thư mục chứa tệp nén...
pause > nul
explorer.exe /select,edudoc_stvb_clean_code_latest.zip
