@echo off
chcp 65001 > nul
title Hệ thống Huấn luyện & Chấm bài STVB Nghị định 30
cd /d "%~dp0"
echo ======================================================================
echo    ĐANG KHỞI ĐỘNG PHẦN MỀM EDUDOC - STVB (NGHỊ ĐỊNH 30/2020/NĐ-CP)
echo ======================================================================
python run_app.py
pause
