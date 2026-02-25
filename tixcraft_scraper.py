#!/usr/bin/env python3
"""
拓元售票網 (Tixcraft) 資訊爬蟲
目標：自動抓取演出活動詳細資訊
作者: Assistant
日期: 2026-02-25
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time


def setup_browser():
    """設定並初始化 Chrome 瀏覽器"""
    print("🌐 正在設定瀏覽器...")
    
    # Chrome 選項設定（防偵測）
    options = Options()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # 自動管理 ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    # 去除 webdriver 屬性
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def scrape_event_title(driver):
    """抓取演出項目標題"""
    try:
        print("📋 正在抓取演出項目...")
        wait = WebDriverWait(driver, 10)
        
        title_element = wait.until(
            EC.presence_of_element_located((By.ID, "synopsisEventTitle"))
        )
        
        event_title = title_element.text.strip()
        print(f"✅ 演出項目：{event_title}")
        return event_title
        
    except TimeoutException:
        print("❌ 無法找到演出項目標題 (ID: synopsisEventTitle)")
        return None
    except Exception as e:
        print(f"❌ 抓取演出標題時發生錯誤：{e}")
        return None


def scrape_event_details(driver):
    """抓取演出詳細資訊 (intro 區塊)"""
    try:
        print("📝 正在抓取演出詳細資訊...")
        wait = WebDriverWait(driver, 10)
        
        intro_element = wait.until(
            EC.presence_of_element_located((By.ID, "intro"))
        )
        
        intro_text = intro_element.text.strip()
        
        if intro_text:
            print("✅ 演出詳細資訊：")
            print("=" * 50)
            
            # 逐行處理並分類顯示
            lines = intro_text.split('\n')
            for line in lines:
                line = line.strip()
                if line:  # 跳過空行
                    # 根據關鍵字分類顯示
                    if any(keyword in line for keyword in ['日期', '時間', '場次']):
                        print(f"📅 {line}")
                    elif any(keyword in line for keyword in ['地點', '場地', '館']):
                        print(f"📍 {line}")
                    elif any(keyword in line for keyword in ['票價', '價格', '元', '$', 'NT']):
                        print(f"💰 {line}")
                    elif any(keyword in line for keyword in ['售票', '開賣', '預售']):
                        print(f"🎫 {line}")
                    else:
                        print(f"ℹ️  {line}")
            
            print("=" * 50)
            return intro_text
        else:
            print("⚠️ intro 區塊內容為空")
            return None
            
    except TimeoutException:
        print("❌ 無法找到演出詳細資訊 (ID: intro)")
        return None
    except Exception as e:
        print(f"❌ 抓取演出詳情時發生錯誤：{e}")
        return None


def scrape_additional_info(driver):
    """嘗試抓取其他可用的活動資訊"""
    print("🔍 正在搜尋其他活動資訊...")
    
    # 其他可能包含資訊的元素 ID 或 Class
    additional_selectors = [
        {"name": "活動描述", "selector": By.CLASS_NAME, "value": "event-description"},
        {"name": "票價資訊", "selector": By.CLASS_NAME, "value": "price-info"},
        {"name": "場地資訊", "selector": By.CLASS_NAME, "value": "venue-info"},
        {"name": "注意事項", "selector": By.CLASS_NAME, "value": "notice"},
        {"name": "主辦單位", "selector": By.CLASS_NAME, "value": "organizer"}
    ]
    
    found_info = []
    
    for item in additional_selectors:
        try:
            element = driver.find_element(item["selector"], item["value"])
            if element.text.strip():
                print(f"✅ {item['name']}：{element.text.strip()[:100]}...")
                found_info.append({item["name"]: element.text.strip()})
        except NoSuchElementException:
            continue
    
    return found_info


def main():
    """主程式"""
    # 目標網址
    target_url = "https://tixcraft.com/activity/detail/26_kamenashi"
    
    print("🎭 拓元售票網資訊爬蟲啟動")
    print("=" * 60)
    print(f"🎯 目標網址：{target_url}")
    print("=" * 60)
    
    driver = None
    
    try:
        # 1. 設定瀏覽器
        driver = setup_browser()
        
        # 2. 前往目標網址
        print(f"🌐 正在前往目標網址...")
        driver.get(target_url)
        
        # 3. 等待頁面載入
        print("⏳ 等待頁面完全載入...")
        time.sleep(3)  # 給頁面一些時間載入 JavaScript 內容
        
        # 4. 抓取演出標題
        event_title = scrape_event_title(driver)
        
        # 5. 抓取演出詳細資訊
        event_details = scrape_event_details(driver)
        
        # 6. 嘗試抓取其他資訊
        additional_info = scrape_additional_info(driver)
        
        # 7. 顯示抓取總結
        print("\n🎉 資訊抓取完成!")
        print("=" * 60)
        
        if event_title or event_details or additional_info:
            print("✅ 成功抓取到以下資訊：")
            if event_title:
                print(f"- 演出項目標題")
            if event_details:
                print(f"- 演出詳細資訊 ({len(event_details.split())} 個字)")
            if additional_info:
                print(f"- 其他資訊 ({len(additional_info)} 項)")
        else:
            print("⚠️ 未能抓取到任何資訊，可能需要檢查網頁結構")
            
    except KeyboardInterrupt:
        print("\n⚠️ 程式被使用者中斷")
    except Exception as e:
        print(f"❌ 程式執行錯誤：{e}")
    finally:
        if driver:
            print("\n🔚 正在關閉瀏覽器...")
            driver.quit()
            print("✅ 瀏覽器已關閉")


if __name__ == "__main__":
    main()