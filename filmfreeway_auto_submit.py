#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FilmFreeway自动投递工具
自动在FilmFreeway网站上投递影片作品到电影节
"""

import os
import time
import random
import schedule
import re
import subprocess
import platform
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# 设置日志
logger.add("filmfreeway_auto.log", rotation="10 MB", level="INFO")

class FilmFreewaySubmitter:
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        self.email = os.getenv("FF_EMAIL")
        self.password = os.getenv("FF_PASSWORD")
        self.project_id = os.getenv("PROJECT_ID")
        self.max_submissions = int(os.getenv("MAX_SUBMISSION_PER_DAY", "5"))
        self.max_fee = float(os.getenv("MAX_ENTRY_FEE", "0"))
        self.categories = os.getenv("CATEGORIES", "").split(",")
        
        # 无头模式设置，默认为False（可见浏览器）
        self.headless = os.getenv("HEADLESS", "False") == "True"
        
        # 登录方式设置，默认为邮箱密码
        self.login_method = os.getenv("LOGIN_METHOD", "email")
        
        # 使用已安装的Chrome浏览器
        self.use_installed_browser = os.getenv("USE_INSTALLED_BROWSER", "True") == "True"
        
        # Chrome用户配置目录
        self.chrome_user_data_dir = os.getenv("CHROME_USER_DATA_DIR", "")
        if not self.chrome_user_data_dir and self.use_installed_browser:
            # 尝试使用默认路径
            if platform.system() == "Windows":
                self.chrome_user_data_dir = os.path.join(os.environ["USERPROFILE"], "AppData", "Local", "Google", "Chrome", "User Data")
            elif platform.system() == "Darwin":  # macOS
                self.chrome_user_data_dir = os.path.join(os.environ["HOME"], "Library", "Application Support", "Google", "Chrome")
            else:  # Linux
                self.chrome_user_data_dir = os.path.join(os.environ["HOME"], ".config", "google-chrome")
        
        # 验证必要的环境变量
        if self.login_method == "email" and not all([self.email, self.password]) and not self.use_installed_browser:
            logger.error("请检查.env文件，确保设置了FF_EMAIL, FF_PASSWORD")
            exit(1)
            
        if not self.project_id:
            logger.error("请检查.env文件，确保设置了PROJECT_ID")
            exit(1)
            
        logger.info(f"初始化完成: 将为项目ID {self.project_id} 进行投递")
        logger.info(f"每日最大投递数: {self.max_submissions}, 最大入场费: {self.max_fee}")
        logger.info(f"无头模式: {'开启' if self.headless else '关闭'}")
        logger.info(f"登录方式: {self.login_method}")
        logger.info(f"使用已安装的Chrome浏览器: {'是' if self.use_installed_browser else '否'}")
        if self.use_installed_browser:
            logger.info(f"Chrome用户数据目录: {self.chrome_user_data_dir}")
        
        # 存储项目列表
        self.projects = []
        
    def start(self):
        """启动浏览器并开始投递流程"""
        with sync_playwright() as p:
            browser = self._launch_browser(p)
            try:
                context = browser.new_context() if not self.use_installed_browser else browser.contexts[0]
                
                page = context.new_page()
                
                # 如果使用已安装的浏览器，假设用户已登录
                if not self.use_installed_browser:
                    # 登录
                    self._login(page)
                
                # 搜索并投递电影节
                submitted_count = self._submit_to_festivals(page)
                
                logger.info(f"完成任务，本次成功投递 {submitted_count} 个电影节")
                
            except Exception as e:
                logger.error(f"执行过程中出错: {str(e)}")
            finally:
                browser.close()
    
    def _launch_browser(self, playwright):
        """启动浏览器，根据设置决定是否使用已安装的Chrome"""
        if self.use_installed_browser:
            logger.info("使用已安装的Chrome浏览器及其用户配置文件...")
            try:
                return playwright.chromium.launch_persistent_context(
                    user_data_dir=self.chrome_user_data_dir,
                    headless=self.headless,
                    viewport={"width": 1280, "height": 800},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ],
                )
            except Exception as e:
                logger.error(f"启动已安装的Chrome失败: {str(e)}")
                logger.info("尝试使用内置浏览器...")
                return playwright.chromium.launch(headless=self.headless)
        else:
            return playwright.chromium.launch(headless=self.headless)
    
    def get_projects(self):
        """获取用户账户中的项目列表"""
        logger.info("开始获取账户中的项目列表...")
        
        projects = []
        
        with sync_playwright() as p:
            browser = self._launch_browser(p)
            
            try:
                context = browser.new_context() if not self.use_installed_browser else browser.contexts[0]
                
                page = context.new_page()
                
                # 如果使用已安装的浏览器，假设用户已登录
                if not self.use_installed_browser:
                    # 登录
                    self._login(page)
                
                # 前往项目页面
                logger.info("正在前往项目页面...")
                page.goto("https://filmfreeway.com/projects")
                page.wait_for_load_state("networkidle")
                
                # 检查是否需要登录（即使使用已安装浏览器，有时也可能需要再次登录）
                if page.url.find("login") > -1:
                    logger.info("检测到需要登录...")
                    if self.use_installed_browser:
                        # 如果使用已安装浏览器但需要登录，让用户手动登录
                        logger.info("请在打开的浏览器窗口中手动登录，然后程序将继续...")
                        # 等待用户登录完成
                        page.wait_for_selector('a[href="/dashboard"]', timeout=120000)  # 等待2分钟
                    else:
                        # 使用程序自动登录
                        self._login(page)
                    
                    # 登录后再次前往项目页面
                    page.goto("https://filmfreeway.com/projects")
                    page.wait_for_load_state("networkidle")
                
                # 等待项目列表加载
                page.wait_for_selector('.project-item', timeout=10000)
                
                # 获取项目列表
                project_items = page.query_selector_all('.project-item')
                logger.info(f"找到 {len(project_items)} 个项目")
                
                for item in project_items:
                    try:
                        # 获取项目名称
                        title_element = item.query_selector('.project-title')
                        if not title_element:
                            continue
                        
                        title = title_element.inner_text().strip()
                        
                        # 获取项目链接（包含ID）
                        link_element = item.query_selector('a[href*="/projects/"]')
                        if not link_element:
                            continue
                        
                        project_url = link_element.get_attribute('href')
                        # 从URL中提取项目ID
                        project_id_match = re.search(r'/projects/(\d+)', project_url)
                        project_id = project_id_match.group(1) if project_id_match else None
                        
                        if project_id:
                            projects.append({
                                'id': project_id,
                                'name': title,
                                'url': project_url
                            })
                            logger.info(f"获取到项目: {title} (ID: {project_id})")
                    except Exception as e:
                        logger.error(f"解析项目时出错: {str(e)}")
                
                logger.info(f"共获取到 {len(projects)} 个项目")
                self.projects = projects
                
            except Exception as e:
                logger.error(f"获取项目列表过程中出错: {str(e)}")
            finally:
                browser.close()
            
        return projects
    
    def _login(self, page):
        """登录到FilmFreeway"""
        logger.info("开始登录FilmFreeway...")
        
        page.goto("https://filmfreeway.com/login")
        
        # 根据登录方式选择不同的登录流程
        if self.login_method == "google":
            self._login_with_google(page)
        else:
            self._login_with_email(page)
    
    def _login_with_email(self, page):
        """使用邮箱和密码登录"""
        logger.info("使用邮箱和密码登录...")
        
        # 等待加载
        page.wait_for_selector('input[name="email"]')
        
        # 输入登录信息
        page.fill('input[name="email"]', self.email)
        page.fill('input[name="password"]', self.password)
        
        # 点击登录按钮
        page.click('button[type="submit"]')
        
        # 等待登录完成
        try:
            page.wait_for_selector('a[href="/dashboard"]', timeout=30000)
            logger.info("登录成功")
        except PlaywrightTimeoutError:
            raise Exception("登录失败，请检查账号密码或者网站可能有验证码阻止登录")
    
    def _login_with_google(self, page):
        """使用Google账号登录"""
        logger.info("使用Google账号登录...")
        
        try:
            # 寻找Google登录按钮并点击
            google_btn = page.locator('text="Sign in with Google"').first
            if not google_btn:
                google_btn = page.locator('.google-login-button').first
            
            if not google_btn:
                # 尝试其他可能的选择器
                google_btn = page.locator('a:has-text("Google")').first
            
            if not google_btn:
                raise Exception("无法找到Google登录按钮")
            
            google_btn.click()
            
            # 等待Google登录页面加载
            page.wait_for_load_state("networkidle")
            
            # 检查是否需要选择账户
            if page.query_selector('div[data-identifier]'):
                logger.info("检测到Google账户选择页面")
                # 点击第一个账户（或者可以根据邮箱指定）
                accounts = page.query_selector_all('div[data-identifier]')
                if len(accounts) > 0:
                    accounts[0].click()
                    page.wait_for_load_state("networkidle")
            else:
                # 可能需要输入Google账号密码
                logger.info("需要输入Google账号")
                
                # 输入邮箱
                email_input = page.query_selector('input[type="email"]')
                if email_input:
                    email_input.fill(self.email)
                    page.click('div[id="identifierNext"]')
                    page.wait_for_load_state("networkidle")
                
                # 输入密码
                password_input = page.query_selector('input[type="password"]')
                if password_input:
                    password_input.fill(self.password)
                    page.click('div[id="passwordNext"]')
                    page.wait_for_load_state("networkidle")
            
            # 等待FilmFreeway页面加载完成
            logger.info("等待重定向回FilmFreeway...")
            page.wait_for_url("**/filmfreeway.com/**", timeout=30000)
            
            # 检查是否登录成功
            page.wait_for_selector('a[href="/dashboard"]', timeout=30000)
            logger.info("Google登录成功")
            
        except Exception as e:
            logger.error(f"Google登录过程出错: {str(e)}")
            # 如果Google登录失败，尝试使用邮箱登录作为备选方案
            logger.info("尝试使用邮箱密码登录作为备选...")
            page.goto("https://filmfreeway.com/login")
            self._login_with_email(page)
    
    def _submit_to_festivals(self, page):
        """搜索并投递到电影节"""
        logger.info("开始搜索可投递的电影节...")
        
        # 前往电影节页面
        page.goto("https://filmfreeway.com/festivals")
        page.wait_for_load_state("networkidle")
        
        # 等待过滤器加载
        page.wait_for_selector('.filters-container')
        
        # 点击"Free"过滤选项（如果只需要免费的）
        if self.max_fee == 0:
            try:
                page.click('text="Free"')
                page.wait_for_load_state("networkidle")
                logger.info("已筛选免费电影节")
            except:
                logger.warning("无法筛选免费电影节，继续进行...")
        
        # 获取电影节列表
        festivals = page.query_selector_all('.festival-item')
        logger.info(f"找到 {len(festivals)} 个潜在的电影节")
        
        submitted_count = 0
        
        # 循环处理每个电影节
        for idx, festival in enumerate(festivals):
            if submitted_count >= self.max_submissions:
                logger.info(f"已达到每日最大投递数 {self.max_submissions}")
                break
                
            try:
                # 获取电影节名称
                name_el = festival.query_selector('.title')
                if not name_el:
                    continue
                    
                festival_name = name_el.inner_text().strip()
                
                # 检查是否有entry fee信息
                fee_el = festival.query_selector('.fee')
                if fee_el:
                    fee_text = fee_el.inner_text().strip()
                    if 'Free' not in fee_text and self.max_fee == 0:
                        logger.info(f"跳过付费电影节: {festival_name}")
                        continue
                        
                    # 尝试解析费用
                    if 'Free' not in fee_text:
                        try:
                            fee_value = float(fee_text.replace('$', '').strip())
                            if fee_value > self.max_fee:
                                logger.info(f"跳过费用({fee_value})超出限制的电影节: {festival_name}")
                                continue
                        except:
                            logger.warning(f"无法解析电影节费用: {fee_text}, 跳过: {festival_name}")
                            continue
                
                # 获取详情链接并访问
                detail_link = festival.query_selector('a.title')
                if not detail_link:
                    continue
                
                # 在新标签页中打开详情页
                with page.context.new_page() as detail_page:
                    detail_url = detail_link.get_attribute('href')
                    detail_page.goto(f"https://filmfreeway.com{detail_url}")
                    detail_page.wait_for_load_state("networkidle")
                    
                    # 检查是否已经提交过
                    if detail_page.query_selector('text="Already Submitted"'):
                        logger.info(f"已经提交过: {festival_name}")
                        continue
                    
                    # 寻找提交按钮
                    submit_button = detail_page.query_selector('a:text("Submit Now")')
                    if not submit_button:
                        logger.info(f"无法找到提交按钮: {festival_name}")
                        continue
                    
                    # 点击提交按钮
                    submit_button.click()
                    detail_page.wait_for_load_state("networkidle")
                    
                    # 选择项目
                    try:
                        # 等待项目选择页面加载
                        detail_page.wait_for_selector(f'a[href*="{self.project_id}"]', timeout=10000)
                        detail_page.click(f'a[href*="{self.project_id}"]')
                        detail_page.wait_for_load_state("networkidle")
                        
                        # 选择类别（如果有）
                        if len(self.categories) > 0:
                            for category in self.categories:
                                category_checkbox = detail_page.query_selector(f'label:text-is("{category.strip()}")')
                                if category_checkbox:
                                    category_checkbox.click()
                        
                        # 点击继续
                        continue_button = detail_page.query_selector('button:text("Continue")')
                        if continue_button:
                            continue_button.click()
                            detail_page.wait_for_load_state("networkidle")
                            
                            # 最终提交
                            submit_final = detail_page.query_selector('button:text("Submit")')
                            if submit_final:
                                submit_final.click()
                                detail_page.wait_for_load_state("networkidle")
                                
                                # 检查是否成功提交
                                if detail_page.url.find("thank-you") > -1 or detail_page.query_selector('text="Thank you"'):
                                    submitted_count += 1
                                    logger.info(f"成功投递 [{submitted_count}]: {festival_name}")
                                else:
                                    logger.warning(f"可能未成功投递: {festival_name}")
                            else:
                                logger.warning(f"未找到最终提交按钮: {festival_name}")
                        else:
                            logger.warning(f"未找到继续按钮: {festival_name}")
                    except Exception as e:
                        logger.error(f"投递过程出错 - {festival_name}: {str(e)}")
                
                # 随机延迟，避免被检测为机器人
                time.sleep(random.uniform(2, 5))
                
            except Exception as e:
                logger.error(f"处理电影节时出错: {str(e)}")
        
        return submitted_count

def run_daily_submission():
    """每日定时执行的投递任务"""
    logger.info(f"开始每日投递任务: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    submitter = FilmFreewaySubmitter()
    submitter.start()

def main():
    """主函数"""
    logger.info("FilmFreeway自动投递工具已启动")
    
    # 加载环境变量
    load_dotenv()
    
    # 首次运行
    run_daily_submission()
    
    # 设置每日定时任务 - 从环境变量获取时间，默认为上午10点
    run_time = os.getenv("RUN_TIME", "10:00")
    schedule.every().day.at(run_time).do(run_daily_submission)
    logger.info(f"已设置定时任务，将在每天 {run_time} 自动运行")
    
    # 保持程序运行并执行定时任务
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main() 