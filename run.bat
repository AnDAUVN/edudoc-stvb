@echo off
chcp 65001 > nul
title EDUDOC - He thong Huan luyen va Cham bai STVB Nghi dinh 30
cd /d "%~dp0"
echo ======================================================================
echo    DANG KHOI DONG PHAN MEM EDUDOC - STVB (NGHI DINH 30/2020/ND-CP)
echo ======================================================================
python run_app.py
pause
