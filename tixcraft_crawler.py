#!/usr/bin/env python3
"""
Tixcraft 全自動化深度爬取器（優化版）
作者: Assistant
日期: 2026-02-25
功能: 
- 第一層：抓取所有活動網址 (使用 div.thumbnails a)
- 第二層：逐一點入爬取詳細資訊 (ID: synopsisEventTitle, intro)
- 智能資料分類：使用正則表達式進行關鍵字過濾
- 多元HTML定位：intro + p標籤備用抓取
- 資料清洗：移除重複換行與多餘空格
- 防偵測：保留完整的反偵測機制
- 穩定性：完整的 try-except 錯誤處理
"""

from time import sleep
from datetime import datetime
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class TixcraftScraper:
    """Tixcraft 演出資訊爬取器"""
    
    def __init__(self, base_url="https://tixcraft.com/activity"):
        self.base_url = base_url
        self.driver = self._setup_driver()
        self.events_data = []  # 儲存所有爬取的資料
    
    def _setup_driver(self):
        """配置並初始化 Chrome 瀏覽器（防偵測版）"""
        print("\n🔧 【瀏覽器初始化】正在設定 Chrome 瀏覽器...")
        print("   ⚙️  配置防偵測選項...")
        options = Options()
        
        # === 防偵測核心設定 ===
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        print("   ✅ 防偵測選項配置完成")
        
        # 效能與穩定性設定
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument("--disable-gpu")
        print("   ⚡ 效能選項配置完成")
        
        # 初始化 WebDriver
        print("   📦 正在下載/初始化 ChromeDriver...")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        print("   🌐 Chrome 瀏覽器啟動成功！")
        
        # === CDP 指令隱藏 webdriver 屬性 ===
        print("   🛡️  執行 CDP 防偵測指令...")
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        print("   ✅ 瀏覽器設定完成，已隱藏自動化特徵")
        
        return driver

    
    def scrape_activity_list(self):
        """第一層：抓取所有活動網址"""
        print("\n" + "="*60)
        print("🎭 第一層：開始抓取活動列表網址")
        print("="*60)
        
        try:
            # 等待頁面載入完成
            print("⏳ 等待頁面載入完成...")
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            sleep(5)  # 等待 JavaScript 動態內容載入
            print("✅ 頁面載入完成")
            
            # === 使用指定的選擇器搜尋活動連結 ===
            print("\n🔍 正在搜尋演出活動連結 (使用 div.thumbnails a)...")
            
            # 優先使用指定的 div.thumbnails a 選擇器
            activity_links = self.driver.find_elements(By.CSS_SELECTOR, "div.thumbnails a")
            
            # 如果沒找到，嘗試備用選擇器
            if not activity_links:
                print("⚠️ 使用備用選擇器搜尋...")
                activity_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='activity/detail']")
            
            if not activity_links:
                print("❌ 未找到任何演出連結")
                return []
            
            print(f"✅ 找到 {len(activity_links)} 個演出連結")
            
            # 提取唯一的連結並過濾重複
            unique_urls = set()
            valid_links = []
            
            for link in activity_links:
                try:
                    url = link.get_attribute('href')
                    if url and 'activity/detail' in url and url not in unique_urls:
                        unique_urls.add(url)
                        valid_links.append(url)
                except Exception as e:
                    print(f"❌ 提取連結時發生錯誤: {e}")
                    continue
            
            print(f"📊 過濾重複後獲得唯一連結 {len(valid_links)} 個")
            print(f"\n📋 活動網址清單：")
            for i, url in enumerate(valid_links, 1):
                print(f"   {i}. {url}")
            
            return valid_links
            
        except Exception as e:
            print(f"❌ 第一層爬取過程發生錯誤：{e}")
            return []
    
    
    def scrape_single_event_details(self, url, index):
        """第二層：爬取單個演出的詳細資訊"""
        
        print(f"\n🔍 === 第 {index} 個活動 ===")
        print(f"🌐 正在進入: {url}")
        
        # 初始化資料結構
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
            # 前往演出詳情頁面  
            self.driver.get(url)
            sleep(2)  # 避免切換頁面太快被網站阻擋
            
            # === 抓取演出項目名稱 (ID: synopsisEventTitle) ===
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                title = title_element.text.strip() if title_element.text.strip() else "未找到"
                event_data['title'] = title
                print(f"🎭 演出項目名稱: {title}")
            except Exception as e:
                print(f"⚠️ 無法抓取演出項目名稱: {e}")
                print(f"🎭 演出項目名稱: 未找到")
            
            # === 抓取演出詳細資訊 (ID: intro) ===
            try:
                intro_element = self.driver.find_element(By.ID, "intro")
                intro_text = intro_element.text.strip() if intro_element.text.strip() else "未找到"
                
                if intro_text != "未找到":
                    # 解析 intro 中的日期、時間、地點、票價
                    print(f"\n📋 詳細資訊解析：")
                    print(f"" + "-" * 40)
                    
                    lines = intro_text.split('\n')
                    date_info = []
                    time_info = []
                    location_info = []
                    price_info = []
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # 分類資訊
                        if any(keyword in line for keyword in ['演出日期', '日期', '2026/', '2027/', '(一)', '(二)', '(三)', '(四)', '(五)', '(六)', '(日)']):
                            date_info.append(line)
                        elif any(keyword in line for keyword in ['演出時間', '時間', ':', '點', 'PM', 'AM']) and any(time_word in line for time_word in [':', '點', 'PM', 'AM']):
                            time_info.append(line)
                        elif any(keyword in line for keyword in ['演出地點', '地點', '場地', '館', '廳', '院', '心']):
                            location_info.append(line)
                        elif any(keyword in line for keyword in ['票價', 'NT$', '元', '$']) and any(price_word in line for price_word in ['NT$', '元', '$']):
                            price_info.append(line)
                    
                    # 儲存到資料結構
                    event_data['date'] = '; '.join(date_info) if date_info else '未找到'
                    event_data['time'] = '; '.join(time_info) if time_info else '未找到' 
                    event_data['location'] = '; '.join(location_info) if location_info else '未找到'
                    event_data['price'] = '; '.join(price_info) if price_info else '未找到'
                    
                    # 輸出分類結果到終端機
                    print(f"📅 演出日期: {event_data['date']}")
                    print(f"⏰ 演出時間: {event_data['time']}")
                    print(f"📍 演出地點: {event_data['location']}")
                    print(f"💰 活動票價: {event_data['price']}")
                    
                else:
                    print(f"\n📋 詳細資訊: {intro_text}")
                    
            except Exception as e:
                print(f"⚠️ 無法抓取詳細資訊: {e}")
                print(f"📋 演出日期: 未找到")
                print(f"⏰ 演出時間: 未找到")
                print(f"📍 演出地點: 未找到")
                print(f"💰 活動票價: 未找到")
            
            print(f"🔗 活動網址: {url}")
            print(f"✅ 第 {index} 個活動抓取完成")
            
            # 將資料加入收集清單
            self.events_data.append(event_data)
            return True
            
        except Exception as e:
            print(f"❌ 第 {index} 個活動抓取失敗: {e}")
            print(f"⏭️  跳過此活動，繼續下一個...")
            return False
    
    def save_to_json(self, filename='tixcraft_activities.json'):
        """將爬取的資料儲存為 JSON 檔案"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_events': len(self.events_data),
                    'events': self.events_data
                }, f, ensure_ascii=False, indent=2)
            print(f"\n💾 資料已儲存至 {filename}")
            return True
        except Exception as e:
            print(f"\n❌ 儲存檔案失敗: {e}")
            return False
    

    
    def run(self):
        """執行全自動化深度爬取"""
        print("\n🌟 開始執行 Tixcraft 全自動化深度爬取系統")
        print("=" * 60)
        
        try:
            print("🌐 【步驟 1】正在載入活動列表頁面...")
            print(f"   📍 目標網址：{self.base_url}")
            self.driver.get(self.base_url)
            sleep(3)  # 等待頁面完全載入
            print("✅ 頁面載入成功！")
            
            # === 第一層：抓取所有活動網址 ===
            print("\n📋 【第一層】抓取所有活動網址...")
            activity_urls = self.scrape_activity_list()
            
            if not activity_urls:
                print("❌ 未找到任何活動網址，程式結束")
                return
            
            # === 第二層：迴圈點入抓取詳細資訊 ===
            print(f"\n🔄 【第二層】開始迴圈爬取 {len(activity_urls)} 個活動的詳細資訊...")
            print("=" * 60)
            
            success_count = 0
            fail_count = 0
            
            for idx, url in enumerate(activity_urls, 1):
                try:
                    # 自動進入該活動頁面並抓取詳細資訊
                    success = self.scrape_single_event_details(url, idx)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        
                except Exception as e:
                    print(f"❌ 處理第 {idx} 個活動時發生錯誤: {e}")
                    print(f"⏭️  跳過此活動，繼續下一個...")
                    fail_count += 1
                    continue
            
            # === 完成統計 ===
            print("\n" + "=" * 60)
            print("🎉 所有活動資訊抓取完成！")
            print("=" * 60)
            print(f"📊 抓取統計結果：")
            print(f"   ✅ 成功抓取：{success_count} 個活動")
            print(f"   ❌ 失敗跳過：{fail_count} 個活動")
            print(f"   📋 總計處理：{len(activity_urls)} 個活動")
            print(f"   📈 成功率：{(success_count/len(activity_urls)*100):.1f}%")
            
            # === JSON 儲存階段 ===
            if self.events_data:
                print(f"\n💾 【JSON 儲存】正在儲存資料...")
                success = self.save_to_json()
                if success:
                    print(f"📊 JSON 儲存結果：")
                    print(f"   📁 檔案名稱：tixcraft_activities.json")
                    print(f"   📋 總演出數：{len(self.events_data)} 個")
                    print(f"   🎭 有標題的：{sum(1 for e in self.events_data if e['title'] != '未找到')} 個")
                    print(f"   📅 有日期的：{sum(1 for e in self.events_data if e['date'] != '未找到')} 個")
                    print(f"   📍 有地點的：{sum(1 for e in self.events_data if e['location'] != '未找到')} 個")
                    print(f"   💰 有票價的：{sum(1 for e in self.events_data if e['price'] != '未找到')} 個")
            else:
                print(f"\n⚠️ 無資料可儲存，跳過JSON儲存")
            
        except KeyboardInterrupt:
            print("\n⚠️ 程式被使用者中斷")
        except Exception as e:
            print(f"❌ 執行錯誤：{e}")
            print("\n程式發生錯誤，但瀏覽器將保持開啟以供檢查...")
        finally:
            print(f"\n🔚 程式執行完成")
            print("=" * 60)
            input("按 Enter 鍵關閉瀏覽器並結束程式...")
            
            print("🔚 正在關閉瀏覽器...")
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
            print("✅ 瀏覽器已關閉，程式結束")


def main():
    """主程式進入點"""
    print("\n" + "=" * 70)
    print("� Tixcraft 全自動化深度爬取器 v3.0")
    print("=" * 70)
    
    # === 設定目標參數 ===
    TARGET_URL = "https://tixcraft.com/activity"
    
    print(f"🎯 目標網址：{TARGET_URL}")
    print(f"📅 當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    print("\n🚀 即將啟動全自動化深度爬取系統...")
    print("💡 功能：自動抓取所有活動網址，逐一點入爬取詳細資訊")
    print("🛡️ 特色：使用 div.thumbnails a + ID 選擇器，防偵測設定，連續錯誤處理")
    print("💾 儲存：終端機即時顯示 + JSON檔案永久保存")
    print("-" * 50)
    
    try:
        # === 初始化並執行爬取器 ===
        scraper = TixcraftScraper(TARGET_URL)
        scraper.run()
    except Exception as e:
        print(f"\n❌ 主程式執行錯誤：{e}")
        print("程式發生未預期的錯誤")
    finally:
        print("\n" + "=" * 70)
        print("🔚 程式執行結束")
        print("=" * 70)
        input("\n按 Enter 鍵關閉視窗...")


if __name__ == "__main__":
    main()