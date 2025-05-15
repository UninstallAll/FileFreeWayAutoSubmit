@echo off
echo FilmFreeway简易投递工具 - 启动中...

rem 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python 3.8或更高版本！
    pause
    exit /b
)

rem 检查是否已安装依赖
pip show playwright >nul 2>&1
if %errorlevel% neq 0 (
    echo 正在安装必要的依赖...
    pip install python-dotenv loguru playwright
    playwright install chromium
)

rem 运行简易提交脚本
python simple_submit.py

pause 