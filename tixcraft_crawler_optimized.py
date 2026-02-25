#!/usr/bin/env python3
"""
Tixcraft 智能爬蟲系統（優化版 v4.0）
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


class TixcraftScraperOptimized:
    """Tixcraft 演出資訊爬取器（智能版）"""
    
    def __init__(self, base_url="https://tixcraft.com/activity"):
        self.base_url = base_url
        self.driver = self._setup_driver()
        self.events_data = []  # 儲存所有爬取的資料
    
    def clean_text(self, text):
        """清理文字：移除多餘空格、換行符號、特殊字符"""
        if not text:
            return ""
        
        # 移除多餘空格和換行符號
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # 移除多餘的標點符號重複
        cleaned = re.sub(r'[;,，；]{2,}', ';', cleaned)
        
        # 移除開頭結尾的分號或逗號
        cleaned = re.sub(r'^[;,，；\s]+|[;,，；\s]+$', '', cleaned)
        
        return cleaned.strip()
    
    def classify_event_info(self, text_content):
        """智能分類活動資訊：使用正則表達式進行關鍵字過濾"""
        
        if not text_content:
            return {
                'date': '請參閱官網詳細說明',
                'time': '請參閱官網詳細說明',
                'location': '請參閱官網詳細說明',
                'price': '請參閱官網詳細說明',
                'sale_time': '請參閱官網詳細說明'
            }
        
        # 分行處理
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # 資料分類容器
        date_info = []
        time_info = []
        location_info = []
        price_info = []
        sale_time_info = []
        
        print(f"\n🔍 【智能分類】正在分析 {len(lines)} 行內容...")
        
        for line in lines:
            line = self.clean_text(line)
            if not line or len(line) < 3:  # 忽略過短的行
                continue
            
            # === 日期資訊分類 ===
            date_patterns = [
                r'演出日期[：:\s]*',
                r'活動日期[：:\s]*',
                r'日期[：:\s]*',
                r'Date[：:\s]*',
                r'時間[：:\s]*.*?202[0-9]',  # 包含年份的時間
                r'202[0-9]/\d+/\d+',  # 日期格式 2026/01/01
                r'\d+月\d+日',  # 中文日期格式
                r'\d+/\d+\s*\([\u4e00-\u9fff日月火水木金土]\)',  # 日期+星期
            ]
            
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in date_patterns):
                # 避免票價被誤判為日期
                if not re.search(r'NT\$|元|價格|票價|PRICE', line, re.IGNORECASE):
                    date_info.append(line)
                    continue
            
            # === 地點資訊分類 ===
            location_patterns = [
                r'演出地點[：:\s]*',
                r'地點[：:\s]*',
                r'場地[：:\s]*',
                r'會場[：:\s]*',
                r'Venue[：:\s]*',
                r'演出場所[：:\s]*',
                r'.*?館$',  # 以館結尾
                r'.*?廳$',  # 以廳結尾
                r'.*?院$',  # 以院結尾
                r'.*?中心$',  # 以中心結尾
                r'.*?體育場$|.*?巨蛋$|.*?Arena$',  # 體育場館
            ]
            
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in location_patterns):
                # 避免其他資訊被誤判
                if not re.search(r'NT\$|元|價格|票價|時間|202[0-9]|PRICE', line, re.IGNORECASE):
                    location_info.append(line)
                    continue
            
            # === 票價資訊分類 ===
            price_patterns = [
                r'票價[：:\s]*',
                r'活動票價[：:\s]*',
                r'演出票價[：:\s]*',  
                r'Price[：:\s]*',
                r'NT\$\s*\d+',  # NT$數字
                r'\d+\s*元',  # 數字+元
                r'VIP.*?\$\d+|VVIP.*?\$\d+',  # VIP票價
                r'\$\d+[\s/]*',  # $數字
                r'門票[：:\s]*.*?\d+',  # 門票+數字
            ]
            
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in price_patterns):
                # 進一步確認是票價相關
                if re.search(r'NT\$|\d+元|\$\d+|價格|票價|PRICE|VIP|身障', line, re.IGNORECASE):
                    price_info.append(line)
                    continue
            
            # === 售票時間分類 ===
            sale_patterns = [
                r'開賣[：:\s]*',
                r'售票時間[：:\s]*',
                r'預售[：:\s]*',
                r'開售[：:\s]*',
                r'全面開賣[：:\s]*',
                r'預購[：:\s]*',
                r'Sale[：:\s]*.*?202[0-9]',
            ]
            
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in sale_patterns):
                if re.search(r'202[0-9]', line):  # 必須包含年份
                    sale_time_info.append(line)
                    continue
            
            # === 演出時間分類 (更精確) ===
            time_patterns = [
                r'演出時間[：:\s]*.*?\d+:\d+',  # 演出時間+時分
                r'開演[：:\s]*.*?\d+:\d+',  # 開演+時分
                r'時間[：:\s]*.*?\d+:\d+',  # 時間+時分，但不包含年份
                r'\d+:\d+\s*(PM|AM)',  # 時分+PM/AM
                r'\d+點\d+分',  # 中文時間格式
            ]
            
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in time_patterns):
                # 確保不是包含年份的日期資訊
                if not re.search(r'202[0-9]|\d+月\d+日', line):
                    time_info.append(line)
                    continue
        
        # 組裝結果
        result = {
            'date': '; '.join(date_info) if date_info else '請參閱官網詳細說明',
            'time': '; '.join(time_info) if time_info else '請參閱官網詳細說明', 
            'location': '; '.join(location_info) if location_info else '請參閱官網詳細說明',
            'price': '; '.join(price_info) if price_info else '請參閱官網詳細說明',
            'sale_time': '; '.join(sale_time_info) if sale_time_info else '請參閱官網詳細說明'
        }
        
        # 輸出分類統計
        print(f"   📅 日期資訊: {len(date_info)} 條")
        print(f"   ⏰ 時間資訊: {len(time_info)} 條") 
        print(f"   📍 地點資訊: {len(location_info)} 條")
        print(f"   💰 票價資訊: {len(price_info)} 條")
        print(f"   🎟️ 售票資訊: {len(sale_time_info)} 條")
        
        return result
    
    def extract_alternative_content(self):
        """備用資料抓取：嘗試從p標籤或其他元素獲取資訊"""
        try:
            print("🔄 正在嘗試備用資料抓取方法...")
            
            # 方法1: 抓取所有p標籤
            p_elements = self.driver.find_elements(By.TAG_NAME, "p")
            p_content = ""
            
            for p in p_elements:
                text = p.text.strip()
                if text and len(text) > 10:  # 過濾太短的內容
                    p_content += text + "\n"
            
            if p_content:
                print(f"✅ 從 {len(p_elements)} 個 p 標籤中提取到內容")
                return p_content
            
            # 方法2: 抓取表格內容
            table_elements = self.driver.find_elements(By.TAG_NAME, "table")
            table_content = ""
            
            for table in table_elements:
                text = table.text.strip()
                if text and len(text) > 10:
                    table_content += text + "\n"
            
            if table_content:
                print(f"✅ 從 {len(table_elements)} 個 table 標籤中提取到內容")
                return table_content
            
            # 方法3: 抓取div.description或類似容器
            div_selectors = [
                "div.description", "div.content", "div.detail", 
                "div.info", ".event-info", ".activity-detail"
            ]
            
            for selector in div_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 20:
                            print(f"✅ 從 {selector} 中提取到內容")
                            return text
                except:
                    continue
            
            print("⚠️ 備用抓取方法未找到有效內容")
            return None
            
        except Exception as e:
            print(f"❌ 備用抓取方法失敗: {e}")
            return None
    
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
        
        # 建立Chrome瀏覽器實例
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # === 進階JavaScript防偵測設定 ===
        print("   🛡️  執行進階防偵測JavaScript...")
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        print("   ✅ JavaScript防偵測設定完成")
        
        # 設定預設視窗大小與位置
        driver.set_window_size(1920, 1080)
        print("   🖥️  瀏覽器視窗設定完成")
        
        return driver
    
    def scrape_activity_list(self):
        """第一層：抓取所有演出活動的網址清單"""
        
        try:
            print(f"\n🌐 正在載入拓元售票活動列表頁面...")
            self.driver.get(self.base_url)
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
        """第二層：爬取單個演出的詳細資訊（智能版）"""
        
        print(f"\n🔍 === 第 {index} 個活動 ===")
        print(f"🌐 正在進入: {url}")
        
        # 初始化資料結構
        event_data = {
            'index': index,
            'title': '請參閱官網詳細說明',
            'date': '請參閱官網詳細說明',
            'time': '請參閱官網詳細說明', 
            'location': '請參閱官網詳細說明',
            'price': '請參閱官網詳細說明',
            'sale_time': '請參閱官網詳細說明',
            'url': url
        }
        
        try:
            # 前往演出詳情頁面  
            self.driver.get(url)
            sleep(2)  # 避免切換頁面太快被網站阻擋
            
            # === 抓取演出項目名稱 (ID: synopsisEventTitle) ===
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                title = self.clean_text(title_element.text) if title_element.text else "請參閱官網詳細說明"
                event_data['title'] = title if title else "請參閱官網詳細說明"
                print(f"🎭 演出項目名稱: {event_data['title']}")
            except Exception as e:
                print(f"⚠️ 無法抓取演出項目名稱: {e}")
                print(f"🎭 演出項目名稱: 請參閱官網詳細說明")
            
            # === 抓取演出詳細資訊 (ID: intro) ===
            content_found = False
            intro_text = ""
            
            try:
                intro_element = self.driver.find_element(By.ID, "intro")
                intro_text = intro_element.text.strip() if intro_element.text else ""
                
                if intro_text and len(intro_text) > 20:  # 確保內容足夠豐富
                    content_found = True
                    print(f"✅ 從 intro 元素成功抓取到內容")
                else:
                    print(f"⚠️ intro 元素內容不足，嘗試備用方法...")
                    
            except Exception as e:
                print(f"⚠️ 無法抓取 intro 元素: {e}")
            
            # === 如果intro不夠完整，嘗試備用抓取方法 ===
            if not content_found:
                alternative_content = self.extract_alternative_content()
                if alternative_content:
                    intro_text = alternative_content
                    content_found = True
                    print(f"✅ 備用方法成功獲取內容")
                else:
                    print(f"❌ 所有抓取方法都無法獲取足夠內容")
            
            # === 智能分類資料 ===
            if content_found and intro_text:
                print(f"\n📋 【內容分析】正在進行智能分類...")
                print(f"📝 原始內容長度: {len(intro_text)} 字符")
                
                # 使用智能分類功能
                classified_info = self.classify_event_info(intro_text)
                
                # 更新資料結構 (除了title以外)
                for key in ['date', 'time', 'location', 'price', 'sale_time']:
                    event_data[key] = classified_info[key]
                
                # 輸出分類結果到終端機
                print(f"\n📊 【分類結果】")
                print("-" * 50)
                print(f"📅 演出日期: {event_data['date']}")
                print(f"⏰ 演出時間: {event_data['time']}")
                print(f"📍 演出地點: {event_data['location']}")
                print(f"💰 活動票價: {event_data['price']}")
                print(f"🎟️ 售票時間: {event_data['sale_time']}")
                
            else:
                print(f"\n📋 ⚠️ 未能獲取足夠的詳細資訊")
                print(f"📅 演出日期: 請參閱官網詳細說明")
                print(f"⏰ 演出時間: 請參閱官網詳細說明")
                print(f"📍 演出地點: 請參閱官網詳細說明")
                print(f"💰 活動票價: 請參閱官網詳細說明")
                print(f"🎟️ 售票時間: 請參閱官網詳細說明")
            
            print(f"🔗 活動網址: {url}")
            print(f"✅ 第 {index} 個活動抓取完成")
            
            # 將資料加入收集清單
            self.events_data.append(event_data)
            return True
            
        except Exception as e:
            print(f"❌ 第 {index} 個活動抓取失敗: {e}")
            print(f"⏭️  跳過此活動，繼續下一個...")
            # 即使失敗也要記錄基本資訊
            self.events_data.append(event_data)
            return False
    
    def save_to_json(self, filename='tixcraft_activities_optimized.json'):
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
        """執行智能化深度爬取"""
        print("\n🌟 開始執行 Tixcraft 智能爬蟲系統")
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
                    print(f"   📁 檔案名稱：tixcraft_activities_optimized.json")
                    print(f"   📋 總演出數：{len(self.events_data)} 個")
                    
                    # 計算各欄位的有效資料數量
                    valid_titles = sum(1 for e in self.events_data if e['title'] != '請參閱官網詳細說明')
                    valid_dates = sum(1 for e in self.events_data if e['date'] != '請參閱官網詳細說明')
                    valid_times = sum(1 for e in self.events_data if e['time'] != '請參閱官網詳細說明')
                    valid_locations = sum(1 for e in self.events_data if e['location'] != '請參閱官網詳細說明')
                    valid_prices = sum(1 for e in self.events_data if e['price'] != '請參閱官網詳細說明')
                    valid_sale_times = sum(1 for e in self.events_data if e['sale_time'] != '請參閱官網詳細說明')
                    
                    print(f"   🎭 有標題的：{valid_titles} 個 ({(valid_titles/len(self.events_data)*100):.1f}%)")
                    print(f"   📅 有日期的：{valid_dates} 個 ({(valid_dates/len(self.events_data)*100):.1f}%)")
                    print(f"   ⏰ 有時間的：{valid_times} 個 ({(valid_times/len(self.events_data)*100):.1f}%)")
                    print(f"   📍 有地點的：{valid_locations} 個 ({(valid_locations/len(self.events_data)*100):.1f}%)")
                    print(f"   💰 有票價的：{valid_prices} 個 ({(valid_prices/len(self.events_data)*100):.1f}%)")
                    print(f"   🎟️ 有售票時間：{valid_sale_times} 個 ({(valid_sale_times/len(self.events_data)*100):.1f}%)")
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
    print("🧠 Tixcraft 智能爬蟲系統 v4.0 (優化版)")
    print("=" * 70)
    
    # === 設定目標參數 ===
    TARGET_URL = "https://tixcraft.com/activity"
    
    print(f"🎯 目標網址：{TARGET_URL}")
    print(f"📅 當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    print("\n🚀 即將啟動智能化深度爬取系統...")
    print("💡 功能：自動抓取所有活動網址，逐一點入爬取詳細資訊")
    print("🧠 智能：使用正則表達式進行關鍵字過濾與資料分類")
    print("🔄 備用：intro無效時自動嘗試p標籤等其他HTML元素")
    print("🧹 清洗：去除多餘空格、換行符號，優化資料品質")
    print("🛡️ 特色：防偵測設定 + 連續錯誤處理 + 智能容錯")
    print("💾 儲存：終端機即時顯示 + JSON檔案永久保存")
    print("-" * 50)
    
    try:
        # === 初始化並執行爬取器 ===
        scraper = TixcraftScraperOptimized(TARGET_URL)
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