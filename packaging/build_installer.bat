@echo off
chcp 65001 >nul
echo 正在编译安装程序...

where iscc >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Inno Setup 编译器 iscc
    echo 请安装 Inno Setup 6: https://jrsoftware.org/isinfo.php
    echo 安装后将 ISCC.exe 所在目录加入 PATH
    pause
    exit /b 1
)

cd /d "%~dp0"
iscc installer.iss
if errorlevel 1 (
    echo [错误] 安装程序编译失败
    pause
    exit /b 1
)

echo.
echo 安装程序已生成: release\微机教室考试系统_Setup.exe
pause
