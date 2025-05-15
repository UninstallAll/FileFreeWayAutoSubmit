#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FilmFreeway简易投递工具 - 命令行版本
自动使用已安装的Chrome浏览器进行投递
"""

import os
import time
import tempfile
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from playwright.sync_api import sync_playwright

# 设置日志
logger.add("filmfreeway_auto.log", rotation="10 MB", level="INFO")

def main():
    """主函数 - 简易版本，直接使用用户的Chrome浏览器"""
    print("FilmFreeway简易投递工具 - 启动中...")
    logger.info("FilmFreeway简易投递工具启动")
    
    # 加载环境变量
    load_dotenv()
    
    # 获取项目ID
    project_id = os.getenv("PROJECT_ID", "")
    if not project_id or project_id == "your_project_id":
        project_id = input("请输入您的项目ID: ")
    
    # 获取最大费用
    max_fee_str = os.getenv("MAX_ENTRY_FEE", "0")
    try:
        max_fee = float(max_fee_str)
    except:
        max_fee = 0
        print("入场费设置错误，将使用默认值0")
    
    # 获取每日最大投递数
    max_submissions_str = os.getenv("MAX_SUBMISSION_PER_DAY", "5")
    try:
        max_submissions = int(max_submissions_str)
    except:
        max_submissions = 5
        print("每日最大投递数设置错误，将使用默认值5")
    
    # 获取类别
    categories_str = os.getenv("CATEGORIES", "Short,Documentary")
    categories = [c.strip() for c in categories_str.split(",") if c.strip()]
    
    # 确认设置
    print("\n当前设置:")
    print(f"项目ID: {project_id}")
    print(f"最大入场费: ${max_fee}")
    print(f"每日最大投递数: {max_submissions}")
    print(f"投递类别: {', '.join(categories)}")
    
    confirm = input("\n确认以上设置并开始投递? (y/n): ")
    if confirm.lower() != 'y':
        print("已取消投递")
        return
    
    print("\n开始投递过程...")
    
    # 使用临时用户数据目录，避免干扰用户的Chrome配置
    with tempfile.TemporaryDirectory() as temp_dir:
        with sync_playwright() as p:
            # 启动Chrome浏览器
            browser = p.chromium.launch(
                headless=False,
                channel="chrome",  # 使用已安装的Chrome
                args=[
                    "--disable-blink-features=AutomationControlled",  # 减少被检测为自动化的可能性
                ]
            )
            
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
            page = context.new_page()
            
            try:
                # 访问FilmFreeway登录页面
                print("正在打开FilmFreeway登录页面...")
                page.goto("https://filmfreeway.com/login")
                
                # 等待用户手动登录
                print("\n请在打开的浏览器窗口中手动登录您的FilmFreeway账号")
                print("登录成功后程序将自动继续...\n")
                
                # 等待登录成功
                page.wait_for_selector('a[href="/dashboard"]', timeout=120000)  # 等待2分钟
                print("登录成功！")
                
                # 前往电影节页面
                print("正在搜索可投递的电影节...")
                page.goto("https://filmfreeway.com/festivals")
                page.wait_for_load_state("networkidle")
                
                # 等待过滤器加载
                page.wait_for_selector('.filters-container')
                
                # 点击"Free"过滤选项（如果只需要免费的）
                if max_fee == 0:
                    try:
                        page.click('text="Free"')
                        page.wait_for_load_state("networkidle")
                        print("已筛选免费电影节")
                    except:
                        print("无法筛选免费电影节，继续进行...")
                
                # 获取电影节列表
                festivals = page.query_selector_all('.festival-item')
                festival_count = len(festivals)
                print(f"找到 {festival_count} 个潜在的电影节")
                
                submitted_count = 0
                
                # 循环处理每个电影节
                for idx, festival in enumerate(festivals):
                    if submitted_count >= max_submissions:
                        print(f"已达到每日最大投递数 {max_submissions}")
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
                            if 'Free' not in fee_text and max_fee == 0:
                                print(f"跳过付费电影节: {festival_name}")
                                continue
                            
                            # 尝试解析费用
                            if 'Free' not in fee_text:
                                try:
                                    fee_value = float(fee_text.replace('$', '').strip())
                                    if fee_value > max_fee:
                                        print(f"跳过费用(${fee_value})超出限制的电影节: {festival_name}")
                                        continue
                                except:
                                    print(f"无法解析电影节费用: {fee_text}, 跳过: {festival_name}")
                                    continue
                        
                        # 获取详情链接并访问
                        detail_link = festival.query_selector('a.title')
                        if not detail_link:
                            continue
                        
                        print(f"\n正在处理电影节 ({idx+1}/{festival_count}): {festival_name}")
                        
                        # 在新标签页中打开详情页
                        with page.context.new_page() as detail_page:
                            detail_url = detail_link.get_attribute('href')
                            detail_page.goto(f"https://filmfreeway.com{detail_url}")
                            detail_page.wait_for_load_state("networkidle")
                            
                            # 检查是否已经提交过
                            if detail_page.query_selector('text="Already Submitted"'):
                                print(f"已经提交过: {festival_name}")
                                continue
                            
                            # 寻找提交按钮
                            submit_button = detail_page.query_selector('a:text("Submit Now")')
                            if not submit_button:
                                print(f"无法找到提交按钮: {festival_name}")
                                continue
                            
                            # 点击提交按钮
                            submit_button.click()
                            detail_page.wait_for_load_state("networkidle")
                            
                            # 选择项目
                            try:
                                # 等待项目选择页面加载
                                detail_page.wait_for_selector(f'a[href*="{project_id}"]', timeout=10000)
                                detail_page.click(f'a[href*="{project_id}"]')
                                detail_page.wait_for_load_state("networkidle")
                                
                                # 选择类别（如果有）
                                if len(categories) > 0:
                                    for category in categories:
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
                                            print(f"✅ 成功投递 [{submitted_count}]: {festival_name}")
                                        else:
                                            print(f"❓ 可能未成功投递: {festival_name}")
                                    else:
                                        print(f"未找到最终提交按钮: {festival_name}")
                                else:
                                    print(f"未找到继续按钮: {festival_name}")
                            except Exception as e:
                                print(f"投递过程出错 - {festival_name}: {str(e)}")
                        
                        # 随机延迟2-5秒，避免被检测为机器人
                        delay = 2 + (idx % 3)
                        print(f"等待 {delay} 秒后继续下一个电影节...")
                        time.sleep(delay)
                        
                    except Exception as e:
                        print(f"处理电影节时出错: {str(e)}")
                
                print(f"\n投递过程完成！成功投递 {submitted_count} 个电影节")
                
            except Exception as e:
                print(f"执行过程中出错: {str(e)}")
            
            # 等待用户手动关闭
            input("\n按Enter键关闭浏览器并退出程序...")

if __name__ == "__main__":
    main() 