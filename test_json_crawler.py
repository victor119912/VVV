#!/usr/bin/env python3
"""
Tixcraft 測試版 - 驗證JSON儲存功能
只爬取前3個活動來快速測試
"""

from time import sleep
from datetime import datetime
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class TixcraftTestScraper:
    """Tixcraft 測試爬取器 - 只爬取前3個活動"""
    
    def __init__(self, base_url="https://tixcraft.com/activity"):
        self.base_url = base_url
        self.driver = self._setup_driver()
        self.events_data = []

    def _setup_driver(self):
        """配置並初始化 Chrome 瀏覽器（防偵測版）"""
        print("🔧 設定瀏覽器...")
        options = Options()
        
        # === 防偵測核心設定 ===
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 效能與穩定性設定
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument("--disable-gpu")
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # === CDP 指令隱藏 webdriver 屬性 ===
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        print("✅ 瀏覽器設定完成")
        return driver

    def scrape_activity_urls(self):
        """抓取活動網址"""
        print("🔍 抓取活動網址...")
        self.driver.get(self.base_url)
        sleep(3)
        
        activity_links = self.driver.find_elements(By.CSS_SELECTOR, "div.thumbnails a")
        if not activity_links:
            activity_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='activity/detail']")
        
        urls = []
        for link in activity_links[:3]:  # 只取前3個
            try:
                url = link.get_attribute('href')
                if url and 'activity/detail' in url:
                    urls.append(url)
            except:
                continue
        
        print(f"✅ 找到 {len(urls)} 個測試網址")
        return urls

    def scrape_single_event(self, url, index):
        """爬取單個活動"""
        print(f"\n🔍 === 第 {index} 個測試活動 ===")
        print(f"🌐 進入: {url}")
        
        event_data = {
            'index': index,
            'title': '未找到',
            'date': '未找到',
            'time': '未找到', 
            'location': '未找到',
            'price': '未找到',
            'url': url
        }
        
        try:
            self.driver.get(url)
            sleep(2)
            
            # 抓取標題
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                title = title_element.text.strip()
                if title:
                    event_data['title'] = title
                print(f"🎭 標題: {title}")
            except:
                print("⚠️ 標題抓取失敗")
            
            # 抓取詳細資訊
            try:
                intro_element = self.driver.find_element(By.ID, "intro")
                intro_text = intro_element.text.strip()
                
                if intro_text:
                    lines = intro_text.split('\n')
                    date_info = []
                    time_info = []
                    location_info = []
                    price_info = []
                    
                    for line in lines[:10]:  # 只檢查前10行節省時間
                        line = line.strip()
                        if not line:
                            continue
                        
                        if any(keyword in line for keyword in ['演出日期', '日期', '2026/', '(一)', '(二)', '(三)', '(四)', '(五)', '(六)', '(日)']):
                            date_info.append(line)
                        elif any(keyword in line for keyword in ['演出時間', '時間', ':', '點']) and any(time_word in line for time_word in [':', '點', 'PM', 'AM']):
                            time_info.append(line)
                        elif any(keyword in line for keyword in ['演出地點', '地點', '場地', '館']):
                            location_info.append(line)
                        elif any(keyword in line for keyword in ['票價', 'NT$', '元']) and any(price_word in line for price_word in ['NT$', '元', '$']):
                            price_info.append(line)
                    
                    # 儲存解析結果
                    if date_info:
                        event_data['date'] = '; '.join(date_info[:2])  # 最多2個
                    if time_info:
                        event_data['time'] = '; '.join(time_info[:2])
                    if location_info:
                        event_data['location'] = '; '.join(location_info[:2])
                    if price_info:
                        event_data['price'] = '; '.join(price_info[:2])
                    
                    print(f"📅 日期: {event_data['date']}")
                    print(f"⏰ 時間: {event_data['time']}")
                    print(f"📍 地點: {event_data['location']}")
                    print(f"💰 票價: {event_data['price']}")
                    
            except:
                print("⚠️ 詳細資訊抓取失敗")
            
            print(f"✅ 第 {index} 個活動完成")
            self.events_data.append(event_data)
            return True
            
        except Exception as e:
            print(f"❌ 第 {index} 個活動失敗: {e}")
            return False

    def save_to_json(self, filename='test_tixcraft_activities.json'):
        """儲存為JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_events': len(self.events_data),
                    'events': self.events_data
                }, f, ensure_ascii=False, indent=2)
            print(f"\n💾 測試資料已儲存至 {filename}")
            return True
        except Exception as e:
            print(f"\n❌ 儲存失敗: {e}")
            return False

    def run_test(self):
        """執行測試"""
        print("\n🧪 開始 JSON 儲存功能測試")
        print("=" * 50)
        
        try:
            # 抓取網址
            urls = self.scrape_activity_urls()
            if not urls:
                print("❌ 無測試網址")
                return
            
            # 爬取前3個活動
            success_count = 0
            for i, url in enumerate(urls, 1):
                if self.scrape_single_event(url, i):
                    success_count += 1
            
            print(f"\n📊 測試統計: {success_count}/{len(urls)} 成功")
            
            # 儲存JSON
            if self.events_data:
                self.save_to_json()
                print(f"🎯 JSON內容預覽：")
                print(f"   - 爬取時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   - 活動數量：{len(self.events_data)}")
                print(f"   - 有標題的：{sum(1 for e in self.events_data if e['title'] != '未找到')}")
                print(f"   - 有日期的：{sum(1 for e in self.events_data if e['date'] != '未找到')}")
                
        except Exception as e:
            print(f"❌ 測試錯誤: {e}")
        finally:
            print("\n🔚 測試完成")
            input("按 Enter 關閉...")
            self.driver.quit()


if __name__ == "__main__":
    print("🧪 Tixcraft JSON 儲存功能測試")
    print("=" * 40)
    tester = TixcraftTestScraper()
    tester.run_test()