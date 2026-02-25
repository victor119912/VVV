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
            return parse_event_details(intro_text)
        else:
            print("⚠️ intro 區塊內容為空")
            return None
            
    except TimeoutException:
        print("❌ 無法找到演出詳細資訊 (ID: intro)")
        return None
    except Exception as e:
        print(f"❌ 抓取演出詳情時發生錯誤：{e}")
        return None


def parse_event_details(intro_text):
    """解析並格式化演出詳細資訊"""
    lines = intro_text.split('\n')
    
    # 初始化資料字典
    event_data = {
        'date': '',
        'time': '',
        'venue': '',
        'prices': [],
        'sale_time': '',
        'organizer': '',
        'description': []
    }
    
    # 解析每一行資料
    for line in lines:
        line = line.strip()
        if not line or line == '-':
            continue
            
        # 演出日期
        if '演出日期' in line:
            event_data['date'] = line.replace('演出日期｜', '').replace('演出日期：', '')
        
        # 演出時間
        elif '演出時間' in line:
            event_data['time'] = line.replace('演出時間｜', '').replace('演出時間：', '')
        
        # 演出地點
        elif '演出地點' in line or '場地' in line:
            event_data['venue'] = line.replace('演出地點｜', '').replace('演出地點：', '')
        
        # 票價資訊
        elif '活動票價' in line or (('NT$' in line or '元' in line) and '票價' in line):
            event_data['prices'].append(line.replace('活動票價｜', ''))
        elif 'NT$' in line and '元' in line and '票價' not in line:
            event_data['prices'].append(line)
        
        # 售票時間
        elif '售票時間' in line:
            event_data['sale_time'] = line.replace('售票時間｜', '').replace('售票時間：', '')
        
        # 主辦單位
        elif '主辦單位' in line:
            event_data['organizer'] = line.replace('主辦單位｜', '').replace('主辦單位：', '')
        
        # 其他描述
        else:
            if not line.startswith('票價$') and not line.startswith('#'):
                event_data['description'].append(line)
    
    # 格式化輸出
    display_formatted_data(event_data)
    return event_data


def display_formatted_data(data):
    """清晰格式化顯示資料"""
    print("\n" + "=" * 60)
    print("🎭 演出活動詳細資訊")
    print("=" * 60)
    
    if data['date']:
        print(f"📅 演出日期：{data['date']}")
    
    if data['time']:
        print(f"⏰ 演出時間：{data['time']}")
    
    if data['venue']:
        print(f"📍 演出地點：{data['venue']}")
    
    if data['prices']:
        print(f"💰 票價資訊：")
        for price in data['prices']:
            if price.strip():
                print(f"   • {price}")
    
    if data['sale_time']:
        print(f"🎫 售票時間：{data['sale_time']}")
    
    if data['organizer']:
        print(f"🏢 主辦單位：{data['organizer']}")
    
    if data['description']:
        print(f"📋 活動描述：")
        for desc in data['description'][:3]:  # 只顯示前3行描述
            if desc.strip() and len(desc) > 5:
                print(f"   • {desc}")
    
    print("=" * 60)


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
        
        # 6. 顯示完整摘要
        print("\n🎉 資料抓取完成!")
        print("🔍 以下是完整的演出資訊摘要：")
        
        if event_title:
            print(f"\n🎭 【演出項目】")
            print(f"    {event_title}")
        
        if not event_details:
            print("\n⚠️ 未能抓取到詳細資訊，可能需要檢查網頁結構或等待頁面完全載入")
        
        print(f"\n📊 抓取狀態：")
        print(f"   ✅ 演出標題：{'成功' if event_title else '失敗'}")
        print(f"   ✅ 詳細資訊：{'成功' if event_details else '失敗'}")
        print(f"   🔍 網頁來源：{target_url}")
            
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