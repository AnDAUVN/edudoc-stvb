# -*- coding: utf-8 -*-
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\Git\bin;" + $env:Path
Set-Location $PSScriptRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   HE THONG EDUDOC - SOAN THAO VAN BAN (NGHI DINH 30/2020/ND-CP)" -ForegroundColor Cyan
Write-Host "   CONG CU DONG BO & CAP NHAT LEN WEB RENDER / GITHUB (1-CLICK)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Kiem tra kho git
if (-not (Test-Path ".git")) {
    Write-Host "[!] Thu muc chua duoc khoi tao Git. Dang khoi tao git init..." -ForegroundColor Yellow
    git init
    git branch -M main
}

Write-Host "[1/3] Dang kiem tra ma nguon thay doi..." -ForegroundColor Yellow
git add -A

$diff = git status --porcelain
if ([string]::IsNullOrWhiteSpace($diff)) {
    Write-Host "[*] Khong co file nao thay doi so voi phien ban tren GitHub." -ForegroundColor Gray
} else {
    Write-Host "[*] Dang luu cac thay doi moi vao ban commit..." -ForegroundColor Yellow
    $timestamp = Get-Date -Format "dd/MM/yyyy HH:mm:ss"
    git commit -m "Cap nhat phan mem EDUDOC: $timestamp"
}

Write-Host ""
Write-Host "[2/3] Dang day du lieu len GitHub (Render se tu dong build & cap nhat)..." -ForegroundColor Yellow
Write-Host "(Luu y: Neu trinh duyet mo cua so GitHub, ban chi can bam Authorize / Sign in)" -ForegroundColor DarkGray
Write-Host ""

# 2. Kiem tra remote
$remotes = git remote
if (-not $remotes) {
    Write-Host "======================================================================" -ForegroundColor Yellow
    Write-Host " [!] CHUA KET NOI VOI KHO CODE GITHUB (REMOTE ORIGIN)." -ForegroundColor Yellow
    Write-Host " Huong dan ket noi nhanh:" -ForegroundColor White
    Write-Host " 1. Vao https://github.com -> Tao New Repository (vi du: edudoc-stvb)" -ForegroundColor White
    Write-Host " 2. Copy dia chi URL cua kho (vi du: https://github.com/AnDAUVN/edudoc-stvb.git)" -ForegroundColor White
    Write-Host " 3. Chay lenh sau trong PowerShell:" -ForegroundColor Cyan
    Write-Host "    git remote add origin <URL_GITHUB_CUA_BAN>" -ForegroundColor Cyan
    Write-Host "    git push -u origin main" -ForegroundColor Cyan
    Write-Host " 4. Sau do, moi lan sua code chi can nhap dup chuot vao file Cap_Nhat_Len_Web.bat!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Yellow
    exit 0
}

git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "   CAP NHAT THANH CONG LEN GITHUB & RENDER!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host " - Kho GitHub: https://github.com/cttrung1010/edudoc-stvb" -ForegroundColor Cyan
    Write-Host " - Render dang tu dong build va deploy ban moi (mat khoang 1 - 2 phut)." -ForegroundColor White
    Write-Host " - He thong se tu dong cap nhat tat ca tinh nang moi nhat tren website." -ForegroundColor White
    Write-Host "======================================================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host " [!] Can xac thuc quyen day code len GitHub." -ForegroundColor Red
    Write-Host " Neu co cua so/tab trinh duyet Chrome mo ra, Thầy/Cô chi can bam 'Authorize' de xac nhan." -ForegroundColor Yellow
    Write-Host "======================================================================" -ForegroundColor Red
}
