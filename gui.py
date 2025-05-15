#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FilmFreeway自动投递工具 - GUI界面
"""

import os
import sys
import time
import threading
from datetime import datetime
from dotenv import load_dotenv, set_key
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QLineEdit, QPushButton, QTextEdit, QSpinBox, QDoubleSpinBox,
                            QCheckBox, QGroupBox, QTabWidget, QFileDialog, QMessageBox, QComboBox,
                            QProgressBar, QTimeEdit, QRadioButton, QButtonGroup, QListWidget,
                            QListWidgetItem, QSplashScreen)
from PyQt6.QtCore import Qt, QTime, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QFont, QTextCursor

from filmfreeway_auto_submit import FilmFreewaySubmitter, run_daily_submission

# 自定义日志处理器，将日志输出到GUI
class GUILogHandler(QObject):
    log_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
    def write(self, message):
        self.log_signal.emit(message)
        
    def flush(self):
        pass

class FilmFreewayGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        # 设置窗口标题和大小
        self.setWindowTitle("FilmFreeway 自动投递工具")
        self.setMinimumSize(900, 700)
        
        # 创建中央部件
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # 创建主布局
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # 创建选项卡窗口
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # 创建各选项卡
        self.setup_tab = QWidget()
        self.projects_tab = QWidget()
        self.log_tab = QWidget()
        
        self.tabs.addTab(self.setup_tab, "设置")
        self.tabs.addTab(self.projects_tab, "项目选择")
        self.tabs.addTab(self.log_tab, "日志")
        
        # 初始化各选项卡界面
        self.init_setup_tab()
        self.init_projects_tab()
        self.init_log_tab()
        
        # 初始化数据
        self.load_settings()
        
        # 设置日志处理器
        self.log_handler = GUILogHandler()
        self.log_handler.log_signal.connect(self.append_log)
        
        # 初始化线程变量
        self.submission_thread = None
        self.projects_thread = None
        self.is_running = False
        
        # 存储项目列表
        self.projects = []
        
    def init_setup_tab(self):
        """初始化设置选项卡"""
        layout = QVBoxLayout(self.setup_tab)
        
        # 账号设置组
        account_group = QGroupBox("FilmFreeway 账号设置")
        account_layout = QVBoxLayout()
        
        # 登录方式选择
        login_method_layout = QHBoxLayout()
        login_method_label = QLabel("登录方式:")
        self.login_method_group = QButtonGroup()
        
        self.email_login_radio = QRadioButton("邮箱密码登录")
        self.google_login_radio = QRadioButton("Google账号登录")
        
        self.login_method_group.addButton(self.email_login_radio)
        self.login_method_group.addButton(self.google_login_radio)
        
        login_method_layout.addWidget(login_method_label)
        login_method_layout.addWidget(self.email_login_radio)
        login_method_layout.addWidget(self.google_login_radio)
        account_layout.addLayout(login_method_layout)
        
        # 连接信号
        self.email_login_radio.toggled.connect(self.toggle_login_method)
        self.google_login_radio.toggled.connect(self.toggle_login_method)
        
        # 邮箱设置
        email_layout = QHBoxLayout()
        self.email_label = QLabel("邮箱:")
        self.email_input = QLineEdit()
        email_layout.addWidget(self.email_label)
        email_layout.addWidget(self.email_input)
        account_layout.addLayout(email_layout)
        
        # 密码设置
        password_layout = QHBoxLayout()
        self.password_label = QLabel("密码:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        password_layout.addWidget(self.password_label)
        password_layout.addWidget(self.password_input)
        account_layout.addLayout(password_layout)
        
        # 获取项目列表按钮
        fetch_projects_layout = QHBoxLayout()
        self.fetch_projects_btn = QPushButton("获取账户中的项目列表")
        self.fetch_projects_btn.clicked.connect(self.fetch_projects)
        fetch_projects_layout.addWidget(self.fetch_projects_btn)
        account_layout.addLayout(fetch_projects_layout)
        
        # 项目ID设置
        project_layout = QHBoxLayout()
        project_label = QLabel("项目ID:")
        self.project_input = QLineEdit()
        project_layout.addWidget(project_label)
        project_layout.addWidget(self.project_input)
        account_layout.addLayout(project_layout)
        
        account_group.setLayout(account_layout)
        layout.addWidget(account_group)
        
        # 投递设置组
        submit_group = QGroupBox("投递设置")
        submit_layout = QVBoxLayout()
        
        # 每日投递数设置
        daily_layout = QHBoxLayout()
        daily_label = QLabel("每日最大投递数:")
        self.daily_input = QSpinBox()
        self.daily_input.setRange(1, 50)
        daily_layout.addWidget(daily_label)
        daily_layout.addWidget(self.daily_input)
        submit_layout.addLayout(daily_layout)
        
        # 最大费用设置
        fee_layout = QHBoxLayout()
        fee_label = QLabel("最大入场费($):")
        self.fee_input = QDoubleSpinBox()
        self.fee_input.setRange(0, 1000)
        self.fee_input.setDecimals(2)
        fee_layout.addWidget(fee_label)
        fee_layout.addWidget(self.fee_input)
        submit_layout.addLayout(fee_layout)
        
        # 类别设置
        category_layout = QHBoxLayout()
        category_label = QLabel("投递类别(逗号分隔):")
        self.category_input = QLineEdit()
        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_input)
        submit_layout.addLayout(category_layout)
        
        # 自动运行设置
        autorun_layout = QHBoxLayout()
        autorun_label = QLabel("定时运行时间:")
        self.time_input = QTimeEdit()
        self.time_input.setTime(QTime(10, 0))  # 默认10:00
        self.time_input.setDisplayFormat("HH:mm")
        autorun_layout.addWidget(autorun_label)
        autorun_layout.addWidget(self.time_input)
        submit_layout.addLayout(autorun_layout)
        
        # 无头模式选项
        headless_layout = QHBoxLayout()
        self.headless_checkbox = QCheckBox("以无头模式运行 (不显示浏览器)")
        headless_layout.addWidget(self.headless_checkbox)
        submit_layout.addLayout(headless_layout)
        
        submit_group.setLayout(submit_layout)
        layout.addWidget(submit_group)
        
        # 操作按钮
        buttons_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存设置")
        self.save_btn.clicked.connect(self.save_settings)
        
        self.run_once_btn = QPushButton("立即运行一次")
        self.run_once_btn.clicked.connect(self.run_once)
        
        self.run_auto_btn = QPushButton("开始定时任务")
        self.run_auto_btn.clicked.connect(self.toggle_auto_run)
        
        buttons_layout.addWidget(self.save_btn)
        buttons_layout.addWidget(self.run_once_btn)
        buttons_layout.addWidget(self.run_auto_btn)
        
        layout.addLayout(buttons_layout)
        
        # 状态指示器
        status_layout = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.progress_bar)
        
        layout.addLayout(status_layout)
    
    def init_projects_tab(self):
        """初始化项目选择选项卡"""
        layout = QVBoxLayout(self.projects_tab)
        
        # 说明标签
        info_label = QLabel("您可以从下面的列表中选择要自动投递的项目")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info_label)
        
        # 项目列表
        self.projects_list = QListWidget()
        self.projects_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.projects_list.itemClicked.connect(self.select_project)
        layout.addWidget(self.projects_list)
        
        # 项目操作按钮
        buttons_layout = QHBoxLayout()
        
        self.refresh_projects_btn = QPushButton("刷新项目列表")
        self.refresh_projects_btn.clicked.connect(self.fetch_projects)
        
        self.use_selected_btn = QPushButton("使用选中的项目")
        self.use_selected_btn.clicked.connect(self.use_selected_project)
        self.use_selected_btn.setEnabled(False)  # 默认禁用，直到选择了项目
        
        buttons_layout.addWidget(self.refresh_projects_btn)
        buttons_layout.addWidget(self.use_selected_btn)
        layout.addLayout(buttons_layout)
        
        # 项目详情区域
        project_details_group = QGroupBox("项目详情")
        details_layout = QVBoxLayout()
        
        self.project_details_text = QTextEdit()
        self.project_details_text.setReadOnly(True)
        details_layout.addWidget(self.project_details_text)
        
        project_details_group.setLayout(details_layout)
        layout.addWidget(project_details_group)
    
    def toggle_login_method(self):
        """切换登录方式时的界面调整"""
        if self.google_login_radio.isChecked():
            # Google登录方式下，密码可选填（如果没有保存浏览器登录状态则需要）
            self.password_label.setText("密码(可选):")
            self.email_label.setText("Google邮箱:")
        else:
            # 邮箱登录方式下，密码为必填
            self.password_label.setText("密码:")
            self.email_label.setText("邮箱:")
    
    def init_log_tab(self):
        """初始化日志选项卡"""
        layout = QVBoxLayout(self.log_tab)
        
        # 日志显示区域
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)
        
        # 日志控制按钮
        log_buttons_layout = QHBoxLayout()
        
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self.clear_log)
        
        self.save_log_btn = QPushButton("保存日志")
        self.save_log_btn.clicked.connect(self.save_log)
        
        log_buttons_layout.addWidget(self.clear_log_btn)
        log_buttons_layout.addWidget(self.save_log_btn)
        
        layout.addLayout(log_buttons_layout)
    
    def load_settings(self):
        """从.env文件加载设置"""
        try:
            load_dotenv()
            
            # 加载登录方式
            login_method = os.getenv("LOGIN_METHOD", "email")
            if login_method == "google":
                self.google_login_radio.setChecked(True)
            else:
                self.email_login_radio.setChecked(True)
            
            self.email_input.setText(os.getenv("FF_EMAIL", ""))
            self.password_input.setText(os.getenv("FF_PASSWORD", ""))
            self.project_input.setText(os.getenv("PROJECT_ID", ""))
            
            self.daily_input.setValue(int(os.getenv("MAX_SUBMISSION_PER_DAY", "5")))
            self.fee_input.setValue(float(os.getenv("MAX_ENTRY_FEE", "0")))
            self.category_input.setText(os.getenv("CATEGORIES", "Short,Documentary"))
            
            # 加载运行时间
            run_time = os.getenv("RUN_TIME", "10:00")
            hour, minute = run_time.split(":")
            self.time_input.setTime(QTime(int(hour), int(minute)))
            
            # 加载无头模式设置
            headless = os.getenv("HEADLESS", "False") == "True"
            self.headless_checkbox.setChecked(headless)
            
            self.append_log("设置已加载")
        except Exception as e:
            self.append_log(f"加载设置时出错: {str(e)}")
    
    def save_settings(self):
        """保存设置到.env文件"""
        try:
            if not os.path.exists(".env"):
                with open(".env", "w") as f:
                    f.write("# FilmFreeway自动投递工具配置\n")
            
            with open(".env", "r+") as f:
                env_data = {}
                
                # 保存登录方式
                login_method = "google" if self.google_login_radio.isChecked() else "email"
                env_data["LOGIN_METHOD"] = login_method
                
                # 保存账号设置
                env_data["FF_EMAIL"] = self.email_input.text()
                env_data["FF_PASSWORD"] = self.password_input.text()
                env_data["PROJECT_ID"] = self.project_input.text()
                
                # 保存投递设置
                env_data["MAX_SUBMISSION_PER_DAY"] = str(self.daily_input.value())
                env_data["MAX_ENTRY_FEE"] = str(self.fee_input.value())
                env_data["CATEGORIES"] = self.category_input.text()
                
                # 保存运行时间
                time_str = self.time_input.time().toString("HH:mm")
                env_data["RUN_TIME"] = time_str
                
                # 保存无头模式设置
                env_data["HEADLESS"] = str(self.headless_checkbox.isChecked())
                
                # 写入.env文件
                for key, value in env_data.items():
                    set_key(".env", key, value)
            
            self.append_log("设置已保存")
            QMessageBox.information(self, "保存成功", "设置已成功保存")
        except Exception as e:
            self.append_log(f"保存设置时出错: {str(e)}")
            QMessageBox.critical(self, "保存失败", f"保存设置时出错:\n{str(e)}")
    
    def fetch_projects(self):
        """获取账户中的项目列表"""
        # 检查账号设置
        if self.email_login_radio.isChecked() and (not self.email_input.text() or not self.password_input.text()):
            QMessageBox.critical(self, "错误", "邮箱登录方式下，邮箱和密码不能为空！")
            return
        
        if self.google_login_radio.isChecked() and not self.email_input.text():
            reply = QMessageBox.question(self, "确认", 
                                         "您选择了Google登录但未填写邮箱，程序将使用浏览器中已保存的Google账号。确定继续吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                return
        
        # 保存当前设置
        self.save_settings()
        
        # 禁用按钮，避免重复操作
        self.fetch_projects_btn.setEnabled(False)
        self.refresh_projects_btn.setEnabled(False)
        self.status_label.setText("正在获取项目列表...")
        self.append_log("开始获取账户中的项目列表...")
        
        # 清空项目列表
        self.projects_list.clear()
        self.project_details_text.clear()
        self.use_selected_btn.setEnabled(False)
        
        # 启动线程获取项目列表
        self.projects_thread = threading.Thread(target=self.fetch_projects_thread)
        self.projects_thread.daemon = True
        self.projects_thread.start()
    
    def fetch_projects_thread(self):
        """在线程中获取项目列表"""
        try:
            # 创建提交器实例
            submitter = FilmFreewaySubmitter()
            
            # 设置无头模式
            submitter.headless = False  # 获取项目列表时最好不要使用无头模式，以便于处理可能的验证
            
            # 获取项目列表
            projects = submitter.get_projects()
            
            # 在UI线程中更新界面
            self.update_projects_list(projects)
            
        except Exception as e:
            self.append_log(f"获取项目列表过程中出错: {str(e)}")
        finally:
            # 恢复按钮状态
            self.fetch_projects_btn.setEnabled(True)
            self.refresh_projects_btn.setEnabled(True)
            self.status_label.setText("就绪")
    
    def update_projects_list(self, projects):
        """更新项目列表界面"""
        self.projects = projects
        
        # 清空列表
        self.projects_list.clear()
        
        if not projects:
            self.append_log("未找到任何项目")
            QMessageBox.warning(self, "提示", "未从您的账户中获取到任何项目。")
            return
        
        # 添加项目到列表
        for project in projects:
            item = QListWidgetItem(f"{project['name']} (ID: {project['id']})")
            item.setData(Qt.ItemDataRole.UserRole, project)
            self.projects_list.addItem(item)
        
        self.append_log(f"成功获取到 {len(projects)} 个项目")
        
        # 切换到项目选择选项卡
        self.tabs.setCurrentWidget(self.projects_tab)
    
    def select_project(self, item):
        """选择项目时的操作"""
        project_data = item.data(Qt.ItemDataRole.UserRole)
        
        if project_data:
            # 显示项目详情
            details = f"项目名称: {project_data['name']}\n"
            details += f"项目ID: {project_data['id']}\n"
            details += f"项目URL: {project_data['url']}\n"
            
            self.project_details_text.setText(details)
            
            # 启用选择按钮
            self.use_selected_btn.setEnabled(True)
    
    def use_selected_project(self):
        """使用选中的项目"""
        selected_items = self.projects_list.selectedItems()
        
        if not selected_items:
            QMessageBox.warning(self, "提示", "请先选择一个项目")
            return
        
        project_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        
        if project_data:
            # 设置项目ID
            self.project_input.setText(project_data['id'])
            
            # 保存设置
            self.save_settings()
            
            # 显示提示
            QMessageBox.information(self, "设置成功", f"已设置当前项目为: {project_data['name']}")
            
            # 切换回设置选项卡
            self.tabs.setCurrentWidget(self.setup_tab)
    
    def run_once(self):
        """运行一次投递任务"""
        if self.is_running:
            QMessageBox.warning(self, "警告", "任务已在运行中")
            return
        
        # 保存当前设置
        self.save_settings()
        
        # 如果是Google登录但没有填写邮箱，给出提示
        if self.google_login_radio.isChecked() and not self.email_input.text():
            reply = QMessageBox.question(self, "确认", 
                                         "您选择了Google登录但未填写邮箱，程序将使用浏览器中已保存的Google账号。确定继续吗？",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                return
        
        # 如果是邮箱登录但没有填写邮箱或密码，给出错误提示
        if self.email_login_radio.isChecked() and (not self.email_input.text() or not self.password_input.text()):
            QMessageBox.critical(self, "错误", "邮箱登录方式下，邮箱和密码不能为空！")
            return
        
        # 如果没有填写项目ID，给出错误提示
        if not self.project_input.text():
            QMessageBox.critical(self, "错误", "项目ID不能为空！请填写您要投递的项目ID")
            return
        
        self.is_running = True
        self.status_label.setText("正在运行...")
        self.run_once_btn.setEnabled(False)
        self.run_auto_btn.setEnabled(False)
        
        self.append_log(f"开始执行投递任务: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 在新线程中运行任务
        self.submission_thread = threading.Thread(target=self.run_submission_task)
        self.submission_thread.daemon = True
        self.submission_thread.start()
    
    def run_submission_task(self):
        """在线程中执行投递任务"""
        try:
            # 创建提交器并运行
            submitter = FilmFreewaySubmitter()
            
            # 设置无头模式
            submitter.headless = self.headless_checkbox.isChecked()
            
            # 运行
            submitter.start()
            
            self.append_log("投递任务完成")
        except Exception as e:
            self.append_log(f"投递过程出错: {str(e)}")
        finally:
            # 恢复界面状态
            self.is_running = False
            self.run_once_btn.setEnabled(True)
            self.run_auto_btn.setEnabled(True)
            self.status_label.setText("就绪")
    
    def toggle_auto_run(self):
        """切换定时任务的开启/关闭状态"""
        if not self.is_running:
            # 开启定时任务
            self.save_settings()
            
            # 检查必要设置
            if self.email_login_radio.isChecked() and (not self.email_input.text() or not self.password_input.text()):
                QMessageBox.critical(self, "错误", "邮箱登录方式下，邮箱和密码不能为空！")
                return
            
            if not self.project_input.text():
                QMessageBox.critical(self, "错误", "项目ID不能为空！请填写您要投递的项目ID")
                return
            
            self.run_auto_btn.setText("停止定时任务")
            
            # 获取定时运行时间
            time_str = self.time_input.time().toString("HH:mm")
            hour, minute = time_str.split(":")
            
            self.append_log(f"已设置定时任务，将在每天 {time_str} 自动运行")
            self.status_label.setText(f"定时任务已启动，将在每天 {time_str} 运行")
            
            # 启动定时任务线程
            self.is_running = True
            self.submission_thread = threading.Thread(target=self.run_scheduled_task)
            self.submission_thread.daemon = True
            self.submission_thread.start()
        else:
            # 关闭定时任务
            self.is_running = False
            self.run_auto_btn.setText("开始定时任务")
            self.status_label.setText("就绪")
            self.append_log("定时任务已停止")
    
    def run_scheduled_task(self):
        """运行定时任务"""
        import schedule
        
        # 清除之前的所有定时任务
        schedule.clear()
        
        # 获取定时运行时间
        time_str = self.time_input.time().toString("HH:mm")
        
        # 设置定时任务
        schedule.every().day.at(time_str).do(self.run_submission_task)
        
        # 保持线程运行并检查定时任务
        while self.is_running:
            schedule.run_pending()
            time.sleep(10)  # 每10秒检查一次
    
    def append_log(self, message):
        """添加日志到显示区域"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        
        # 在UI线程中更新日志
        self.log_display.append(formatted_message)
        # 滚动到底部
        self.log_display.moveCursor(QTextCursor.MoveOperation.End)
    
    def clear_log(self):
        """清空日志显示"""
        self.log_display.clear()
    
    def save_log(self):
        """保存日志到文件"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "保存日志", "", "文本文件 (*.txt);;所有文件 (*)")
            
            if file_path:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_display.toPlainText())
                
                self.append_log(f"日志已保存到: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存日志时出错:\n{str(e)}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.is_running:
            reply = QMessageBox.question(self, "确认退出", 
                                        "定时任务正在运行中，关闭窗口将停止任务。确定要退出吗？",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                        QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.is_running = False
                event.accept()
            else:
                event.ignore()

def main():
    app = QApplication(sys.argv)
    window = FilmFreewayGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 