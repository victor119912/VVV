#!/usr/bin/env python3
"""
Tixcraft 網站結構調試工具
用於診斷和查看實際的網頁元素結構
"""

import json
from time import sleep
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


def setup_driver():
    """簡化版瀏覽器設定"""
    print("🔧 設定瀏覽器...")
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    print("✅ 瀏覽器啟動成功")
    return driver


def debug_page_structure():
    """調試頁面結構"""
    driver = setup_driver()
    
    try:
        print("\n🌐 載入頁面...")
        driver.get("https://tixcraft.com/activity")
        sleep(5)
        
        print("📊 分析頁面結構...")
        
        # 嘗試各種可能的選擇器
        selectors_to_try = [
            "div.activity-item",
            "div.event-item", 
            "div.show-item",
            ".activity-card",
            ".event-card",
            "div[class*='activity']",
            "div[class*='event']",
            "div[class*='show']",
            "a[href*='activity/detail']",
            ".col-xs-12",
            ".col-md-3",
            ".col-lg-3"
        ]
        
        print("\n🔍 測試各種選擇器:")
        for selector in selectors_to_try:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"   {selector:<25}: {len(elements)} 個元素")
                
                # 如果找到元素，顯示前3個的內容
                if elements and len(elements) > 0:
                    print(f"      前3個元素內容預覽:")
                    for i, elem in enumerate(elements[:3], 1):
                        text = elem.text.strip()[:100].replace('\n', ' ')
                        print(f"         {i}. {text}")
                    print()
            except Exception as e:
                print(f"   {selector:<25}: 錯誤 - {e}")
        
        # 查看頁面源碼的特定部分
        print("\n📋 頁面標題和主要內容:")
        try:
            title = driver.title
            print(f"   頁面標題: {title}")
            
            body = driver.find_element(By.TAG_NAME, "body")
            body_text = body.text[:500]
            print(f"   頁面內容預覽: {body_text}")
            
        except Exception as e:
            print(f"   獲取頁面內容失敗: {e}")
        
        input("\n按 Enter 繼續查看詳細的 HTML 結構...")
        
        # 獲取部分 HTML 結構
        print("\n🔍 HTML 結構分析:")
        try:
            html_source = driver.page_source
            print(f"   HTML 長度: {len(html_source)}")
            
            # 查找常見的活動相關類名
            common_classes = ['activity', 'event', 'show', 'concert', 'ticket', 'card', 'item']
            for class_name in common_classes:
                count = html_source.lower().count(class_name)
                print(f"   '{class_name}' 出現次數: {count}")
            
        except Exception as e:
            print(f"   HTML 分析失敗: {e}")
            
    finally:
        input("\n按 Enter 關閉瀏覽器...")
        driver.quit()
        print("✅ 調試完成")


if __name__ == "__main__":
    print("🔍 Tixcraft 網站結構調試工具")
    print("=" * 50)
    debug_page_structure()