@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ================================================
echo   微机教室考试系统 - Windows 打包脚本
echo ================================================
echo.

cd /d "%~dp0\.."
set ROOT=%CD%

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    echo 下载: https://nodejs.org/
    pause
    exit /b 1
)

echo [1/5] 安装后端依赖...
pip install -r backend\requirements.txt -q
if errorlevel 1 (
    echo [错误] 后端依赖安装失败
    pause
    exit /b 1
)

echo [2/5] 安装打包工具...
pip install pyinstaller==6.11.1 -q

echo [3/5] 构建前端...
cd frontend
call npm install
if errorlevel 1 (
    echo [错误] npm install 失败
    pause
    exit /b 1
)
call npm run build
if errorlevel 1 (
    echo [错误] 前端构建失败
    pause
    exit /b 1
)
cd ..

if not exist "frontend\dist\index.html" (
    echo [错误] 前端构建产物不存在
    pause
    exit /b 1
)

echo [4/5] PyInstaller 打包...
pyinstaller packaging\exam_system.spec --noconfirm --clean
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)

echo [5/5] 生成发布包...
if not exist "release" mkdir release

copy /Y packaging\启动考试系统.bat "dist\ExamSystem\启动考试系统.bat" >nul

:: 压缩为 zip
powershell -Command "New-Item -ItemType Directory -Force -Path release | Out-Null; Compress-Archive -Path 'dist\ExamSystem\*' -DestinationPath 'release\ExamSystem.zip' -Force"

echo.
echo ================================================
echo   打包完成！
echo ================================================
echo.
echo 程序目录: dist\ExamSystem\
echo 启动程序: dist\ExamSystem\ExamSystem.exe
echo 压缩包:   release\ExamSystem.zip
echo.
echo 使用方法:
echo   1. 将 dist\微机教室考试系统 文件夹复制到教师机
echo   2. 双击 ExamSystem.exe 启动
echo   3. 学生机浏览器访问显示的 IP 地址
echo.
echo 如需制作安装程序，请安装 Inno Setup 后运行:
echo   packaging\build_installer.bat
echo ================================================
pause
