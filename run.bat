@echo off
echo FilmFreeway自动投递工具 - 启动程序
echo ==================================

echo 检查环境配置...
if not exist .env (
    echo 未找到.env文件，请先运行install.bat安装程序
    pause
    exit /b
)

echo 启动自动投递工具...
python filmfreeway_auto_submit.py

pause 