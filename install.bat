@echo off
echo FilmFreeway自动投递工具 - 安装程序
echo ==================================

echo 检查Python安装...
python --version 2>NUL
if errorlevel 1 (
    echo 未检测到Python，请安装Python 3.7或更高版本
    echo 您可以从 https://www.python.org/downloads/ 下载Python
    pause
    exit /b
)

echo 安装依赖包...
pip install -r requirements.txt

echo 安装Playwright浏览器...
playwright install

echo 创建环境配置文件...
if not exist .env (
    copy .env-example .env
    echo 已创建.env文件，请编辑此文件填入您的信息
)

echo 创建图形界面启动脚本...
echo @echo off > run_gui.bat
echo echo 启动FilmFreeway自动投递工具 - 图形界面 >> run_gui.bat
echo python gui.py >> run_gui.bat
echo pause >> run_gui.bat

echo ==================================
echo 安装完成！
echo 1. 请编辑.env文件设置您的账号信息
echo 2. 运行 run.bat 启动命令行版程序
echo 3. 运行 run_gui.bat 启动图形界面版程序
echo ==================================
pause 