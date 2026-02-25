#!/usr/bin/env python3
"""
Tixcraft 終極爬蟲系統（v5.0）
作者: Assistant
日期: 2026-02-25
功能: 
- 精確「行」分流邏輯：避免重複與誤抓
- JS載入優化：WebDriverWait 監控 dataLayer.artistName
- 即時寫入：每個URL爬完立刻保存，避免資料遺失
- 智能場館辨識：過濾文宣，保留核心地點資訊
- 強化標題機制：JS → HTML → 保底三層策略
"""

from time import sleep
from datetime import datetime
import json
import re
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class TixcraftUltimateCrawler:
    """Tixcraft 終極爬蟲系統（精確分流版）"""
    
    def __init__(self, base_url="https://tixcraft.com/activity"):
        self.base_url = base_url
        self.driver = self._setup_driver()
        self.json_filename = 'tixcraft_activities_ultimate.json'
        self.current_data = self._load_existing_data()
    
    def _load_existing_data(self):
        """載入現有的JSON資料，支援斷點續爬"""
        if os.path.exists(self.json_filename):
            try:
                with open(self.json_filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"📂 載入現有資料：{len(data.get('events', []))} 個活動")
                    return data
            except Exception as e:
                print(f"⚠️ 載入現有資料失敗：{e}")
        
        return {
            'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_events': 0,
            'events': []
        }
    
    def _save_single_event(self, event_data):
        """即時保存單個活動資料"""
        try:
            # 檢查是否已存在相同URL的資料
            existing_urls = [event['url'] for event in self.current_data['events']]
            if event_data['url'] not in existing_urls:
                self.current_data['events'].append(event_data)
                self.current_data['total_events'] = len(self.current_data['events'])
                self.current_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # 立刻寫入檔案
                with open(self.json_filename, 'w', encoding='utf-8') as f:
                    json.dump(self.current_data, f, ensure_ascii=False, indent=2)
                
                print(f"💾 即時保存：第 {event_data['index']} 個活動已存入 {self.json_filename}")
                return True
            else:
                print(f"⚠️ 第 {event_data['index']} 個活動已存在於資料庫中，跳過重複保存")
                return False
        except Exception as e:
            print(f"❌ 即時保存失敗：{e}")
            return False
    
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
    
    def get_data_from_js_optimized(self):
        """JS載入優化：WebDriverWait監控dataLayer.artistName"""
        print("🔍 正在使用WebDriverWait監控JavaScript dataLayer...")
        
        try:
            def check_artist_name(driver):
                """檢查dataLayer中是否存在artistName"""
                try:
                    result = driver.execute_script("""
                        if (typeof dataLayer !== 'undefined' && dataLayer.length > 0) {
                            for (let i = 0; i < dataLayer.length; i++) {
                                if (dataLayer[i].artistName) {
                                    return dataLayer[i].artistName;
                                }
                            }
                        }
                        return null;
                    """)
                    return result
                except:
                    return None
            
            # 使用WebDriverWait等待最多10秒
            wait = WebDriverWait(self.driver, 10)
            
            # 每0.5秒檢查一次dataLayer
            for attempt in range(20):  # 10秒 / 0.5秒 = 20次嘗試
                artist_name = check_artist_name(self.driver)
                if artist_name:
                    print(f"✅ JS成功提取標題：{artist_name}")
                    return artist_name
                sleep(0.5)
                print(f"⏳ 等待dataLayer載入... ({attempt+1}/20)")
            
            print("❌ 10秒等待後，dataLayer仍未載入artistName")
            return None
            
        except Exception as e:
            print(f"❌ JS載入監控失敗：{e}")
            return None
    
    def get_fallback_title_enhanced(self):
        """增強版保底標題提取"""
        try:
            page_title = self.driver.title
            if page_title and len(page_title.strip()) > 0:
                # 使用split('-')[0]提取標題的第一部分
                clean_title = page_title.split('-')[0].strip()
                
                # 進一步清理常見的網站後綴
                clean_title = re.sub(r'(\s*[\|｜]\s*.*)|(\s*-\s*.*)', '', clean_title)
                clean_title = clean_title.replace('拓元售票', '').replace('tixcraft', '').strip()
                
                if clean_title and len(clean_title) > 2:
                    print(f"✅ 保底標題提取成功：{clean_title}")
                    return clean_title
            
            print("⚠️ 網頁標題為空或過短，使用預設值")
            return "請參閱官網詳細說明"
            
        except Exception as e:
            print(f"❌ 保底標題提取失敗：{e}")
            return "請參閱官網詳細說明"
    
    def classify_content_precisely(self, text_content):
        """精確內容分流：避免重複與誤抓"""
        
        if not text_content:
            return {
                'event_datetime': '請參閱官網詳細說明',
                'sale_info': '請參閱官網詳細說明', 
                'location': '請參閱官網詳細說明',
                'price': '請參閱官網詳細說明'
            }
        
        # 分行處理
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # 資料分類容器
        event_datetime_info = []
        sale_info_list = []
        location_info = []
        price_info = []
        
        print(f"\n🔍 【精確分流】正在分析 {len(lines)} 行內容...")
        
        for line in lines:
            line = self.clean_text(line)
            if not line or len(line) < 4:  # 忽略過短的行
                continue
            
            print(f"   處理行：{line[:60]}...")  # 顯示前60字符
            
            # === 1. event_datetime (活動時間) ===
            # 捕捉包含日期/時間格式的行
            datetime_patterns = [
                r'202[0-9]/\d{1,2}/\d{1,2}',  # 2026/01/01
                r'\d{1,2}月\d{1,2}日',        # 1月1日
                r'\d{1,2}:\d{2}',             # 19:00
                r'演出.*?時間',                # 演出時間
                r'活動.*?時間',                # 活動時間
                r'Date.*?Time',               # Date/Time
            ]
            
            has_datetime = any(re.search(pattern, line, re.IGNORECASE) for pattern in datetime_patterns)
            
            # 排除條件：包含售票相關關鍵字
            exclude_sale_keywords = ['開賣', '售票', '預售', '啟售', '全面開賣', '清票', '預購', '購票']
            has_sale_keyword = any(keyword in line for keyword in exclude_sale_keywords)
            
            if has_datetime and not has_sale_keyword:
                event_datetime_info.append(line)
                print(f"     ➤ 歸類為：活動時間")
                continue
            
            # === 2. sale_info (售票資訊) ===
            sale_patterns = [
                r'開賣',
                r'售票時間',
                r'預售',
                r'啟售',
                r'全面開賣',
                r'預購',
                r'購票.*?時間',
                r'會員.*?購',
                r'一般.*?售',
            ]
            
            has_sale_pattern = any(re.search(pattern, line, re.IGNORECASE) for pattern in sale_patterns)
            has_date = re.search(r'202[0-9]|\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}', line)
            
            if has_sale_pattern and has_date:
                sale_info_list.append(line)
                print(f"     ➤ 歸類為：售票資訊")
                continue
            
            # === 3. location (地點精確化) ===
            venue_keywords = ['館', '巨蛋', '中心', 'Legacy', 'Zepp', '滑雪場', 'Sub Live', 'Exhibition Hall', 
                             'Arena', 'TICC', '體育', '會議', '音樂', '展覽', 'WESTAR', '國際']
            
            has_venue = any(keyword in line for keyword in venue_keywords)
            is_too_long = len(line) > 60  # 過長的通常是文宣
            
            # 排除文宣性質的長文
            if has_venue and not is_too_long:
                # 進一步檢查是否為地點相關
                location_indicators = ['地點', '場地', 'Venue', '演出地', '活動地', '會場']
                is_location = any(indicator in line for indicator in location_indicators) or has_venue
                
                if is_location:
                    location_info.append(line)
                    print(f"     ➤ 歸類為：活動地點")
                    continue
            
            # === 4. price (票價) ===
            price_patterns = [
                r'NT\$\d+',                    # NT$2000
                r'\d+元',                      # 2000元
                r'\$\d+',                      # $2000
                r'票價',                       # 票價
                r'VIP.*?\d+',                  # VIP 2000
                r'價格',                       # 價格
                r'\d+(?:,\d{3})*元',          # 2,000元
            ]
            
            has_price = any(re.search(pattern, line, re.IGNORECASE) for pattern in price_patterns)
            
            # 排除規則性文字
            exclude_price_keywords = ['姓名', '會員資料', '限購', '服務費', '手續費', '退票', '規定', '注意']
            has_exclude_keyword = any(keyword in line for keyword in exclude_price_keywords)
            
            if has_price and not has_exclude_keyword:
                price_info.append(line)
                print(f"     ➤ 歸類為：票價資訊")
                continue
            
            print(f"     ➤ 未歸類（跳過）")
        
        # === 保底機制：sale_info 為空時的額外檢查 ===
        if not sale_info_list:
            print("⚠️ 售票資訊為空，啟動保底機制...")
            for line in lines:
                # 尋找常見售票時間格式
                if re.search(r'\d{1,2}:\d{2}.*?(售|賣)', line) or re.search(r'(售|賣).*?\d{1,2}:\d{2}', line):
                    sale_info_list.append(line)
                    print(f"✅ 保底機制找到售票時間：{line[:50]}...")
                    break
        
        # 組裝結果
        result = {
            'event_datetime': '; '.join(event_datetime_info) if event_datetime_info else '請參閱官網詳細說明',
            'sale_info': '; '.join(sale_info_list) if sale_info_list else '請參閱官網詳細說明',
            'location': '; '.join(location_info) if location_info else '請參閱官網詳細說明',
            'price': '; '.join(price_info) if price_info else '請參閱官網詳細說明'
        }
        
        # 輸出分類統計
        print(f"\n📊 【分類統計】")
        print(f"   🗓️ 活動時間: {len(event_datetime_info)} 條")
        print(f"   🎟️ 售票資訊: {len(sale_info_list)} 條")
        print(f"   📍 活動地點: {len(location_info)} 條")
        print(f"   💰 票價資訊: {len(price_info)} 條")
        
        return result
    
    def extract_alternative_content(self):
        """備用資料抓取：嘗試從多種HTML元素獲取資訊"""
        try:
            print("🔄 正在嘗試備用資料抓取方法...")
            
            # 方法1: 抓取所有p標籤
            p_elements = self.driver.find_elements(By.TAG_NAME, "p")
            p_content = ""
            
            for p in p_elements:
                text = p.text.strip()
                if text and len(text) > 10:
                    p_content += text + "\n"
            
            if p_content and len(p_content) > 50:
                print(f"✅ 從 {len(p_elements)} 個 p 標籤中提取到內容")
                return p_content
            
            # 方法2: 抓取div容器內容
            div_selectors = [
                "div.content", "div.detail", "div.info", 
                ".event-info", ".activity-detail", "div.description"
            ]
            
            for selector in div_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and len(text) > 30:
                            print(f"✅ 從 {selector} 中提取到內容")
                            return text
                except:
                    continue
            
            # 方法3: 抓取表格內容
            table_elements = self.driver.find_elements(By.TAG_NAME, "table")
            table_content = ""
            
            for table in table_elements:
                text = table.text.strip()
                if text and len(text) > 20:
                    table_content += text + "\n"
            
            if table_content:
                print(f"✅ 從 {len(table_elements)} 個 table 標籤中提取到內容")
                return table_content
            
            print("⚠️ 所有備用抓取方法都未找到足夠內容")
            return None
            
        except Exception as e:
            print(f"❌ 備用抓取方法失敗: {e}")
            return None
    
    def _setup_driver(self):
        """配置並初始化Chrome瀏覽器（防偵測版）"""
        print("\n🔧 【瀏覽器初始化】正在設定Chrome瀏覽器...")
        options = Options()
        
        # 防偵測核心設定
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 效能與穩定性設定
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        print("   ✅ 防偵測與效能選項配置完成")
        
        # 建立Chrome瀏覽器實例
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # 進階JavaScript防偵測設定
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        driver.set_window_size(1920, 1080)
        print("   🛡️ JavaScript防偵測設定完成")
        return driver
    
    def scrape_activity_list_enhanced(self):
        """增強版活動列表抓取"""
        try:
            print(f"\n🌐 正在載入拓元售票活動列表頁面...")
            self.driver.get(self.base_url)
            sleep(8)  # 確保JavaScript動態內容完全載入
            print("✅ 頁面載入完成")
            
            print("\n🔍 正在搜尋演出活動連結（多重策略）...")
            
            activity_links = []
            
            # 策略1: 指定的 div.thumbnails a
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, "div.thumbnails a")
                if links:
                    activity_links.extend(links)
                    print(f"   策略1 (div.thumbnails a): 找到 {len(links)} 個連結")
            except Exception as e:
                print(f"   策略1失敗: {e}")
            
            # 策略2: 所有包含 activity/detail 的 a 標籤
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='activity/detail']")
                if links:
                    activity_links.extend(links)
                    print(f"   策略2 (a[href*='activity/detail']): 找到 {len(links)} 個連結")
            except Exception as e:
                print(f"   策略2失敗: {e}")
            
            # 策略3: class包含thumbnail相關的元素
            try:
                links = self.driver.find_elements(By.CSS_SELECTOR, "[class*='thumbnail'] a, [class*='thumb'] a")
                if links:
                    activity_links.extend(links)
                    print(f"   策略3 ([class*='thumbnail'] a): 找到 {len(links)} 個連結")
            except Exception as e:
                print(f"   策略3失敗: {e}")
            
            if not activity_links:
                print("❌ 所有策略都未找到任何演出連結")
                return []
            
            print(f"✅ 總共找到 {len(activity_links)} 個候選連結")
            
            # 提取唯一的連結並過濾重複
            unique_urls = set()
            valid_links = []
            
            for link in activity_links:
                try:
                    url = link.get_attribute('href')
                    if url and ('activity/detail' in url or '/activity/' in url) and url not in unique_urls:
                        unique_urls.add(url)
                        valid_links.append(url)
                except Exception as e:
                    print(f"❌ 提取連結時發生錯誤: {e}")
                    continue
            
            print(f"📊 過濾重複後獲得唯一連結 {len(valid_links)} 個")
            
            # 如果連結數太少，嘗試擴展搜尋
            if len(valid_links) < 30:
                print("⚠️ 連結數量偏少，嘗試擴展搜尋...")
                try:
                    all_links = self.driver.find_elements(By.TAG_NAME, "a")
                    for link in all_links:
                        try:
                            url = link.get_attribute('href')
                            if url and ('/activity/' in url or 'tixcraft.com' in url) and 'detail' in url and url not in unique_urls:
                                unique_urls.add(url)
                                valid_links.append(url)
                        except:
                            continue
                    print(f"📊 擴展搜尋後獲得連結 {len(valid_links)} 個")
                except Exception as e:
                    print(f"擴展搜尋失敗: {e}")
            
            print(f"\n📋 活動網址清單：")
            for i, url in enumerate(valid_links, 1):
                print(f"   {i}. {url}")
            
            return valid_links
            
        except Exception as e:
            print(f"❌ 第一層爬取過程發生錯誤：{e}")
            return []
    
    def scrape_single_event_ultimate(self, url, index):
        """終極版單個活動詳細資訊爬取"""
        
        print(f"\n🔍 === 第 {index} 個活動 ===")
        print(f"🌐 正在進入: {url}")
        
        # 初始化資料結構
        event_data = {
            'index': index,
            'title': '請參閱官網詳細說明',
            'event_datetime': '請參閱官網詳細說明',
            'sale_info': '請參閱官網詳細說明',
            'location': '請參閱官網詳細說明', 
            'price': '請參閱官網詳細說明',
            'url': url,
            'scrape_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            # 前往演出詳情頁面
            self.driver.get(url)
            sleep(3)  # 等待頁面載入
            
            # === 標題抓取：三層優先策略 ===
            title_found = False
            
            # 優先1: JS dataLayer.artistName
            try:
                js_title = self.get_data_from_js_optimized()
                if js_title and len(js_title.strip()) > 0:
                    event_data['title'] = self.clean_text(js_title)
                    title_found = True
                    print(f"🎭 演出項目名稱 (JS): {event_data['title']}")
            except Exception as e:
                print(f"⚠️ JS標題提取失敗: {e}")
            
            # 優先2: HTML synopsisEventTitle
            if not title_found:
                try:
                    title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                    if title_element.text and len(title_element.text.strip()) > 0:
                        event_data['title'] = self.clean_text(title_element.text)
                        title_found = True
                        print(f"🎭 演出項目名稱 (HTML): {event_data['title']}")
                except Exception as e:
                    print(f"⚠️ HTML標題提取失敗: {e}")
            
            # 優先3: 保底機制
            if not title_found:
                event_data['title'] = self.get_fallback_title_enhanced()
                print(f"🎭 演出項目名稱 (保底): {event_data['title']}")
            
            # === 內容抓取與分類 ===
            content_found = False
            intro_text = ""
            
            # 主要方法：抓取intro元素
            try:
                intro_element = self.driver.find_element(By.ID, "intro")
                intro_text = intro_element.text.strip() if intro_element.text else ""
                
                if intro_text and len(intro_text) > 30:
                    content_found = True
                    print(f"✅ 從 intro 元素成功抓取內容 ({len(intro_text)} 字符)")
                else:
                    print(f"⚠️ intro 元素內容不足，嘗試備用方法...")
                    
            except Exception as e:
                print(f"⚠️ 無法抓取 intro 元素: {e}")
            
            # 備用方法：其他HTML元素
            if not content_found:
                alternative_content = self.extract_alternative_content()
                if alternative_content and len(alternative_content) > 30:
                    intro_text = alternative_content
                    content_found = True
                    print(f"✅ 備用方法成功獲取內容 ({len(intro_text)} 字符)")
                else:
                    print(f"❌ 所有方法都無法獲取足夠內容")
            
            # === 精確分流處理 ===
            if content_found and intro_text:
                print(f"\n📋 【精確分流處理】")
                classified_info = self.classify_content_precisely(intro_text)
                
                # 更新資料結構
                event_data.update({
                    'event_datetime': classified_info['event_datetime'],
                    'sale_info': classified_info['sale_info'],
                    'location': classified_info['location'],
                    'price': classified_info['price']
                })
                
                # 輸出分類結果
                print(f"\n📊 【分類結果】")
                print("-" * 60)
                print(f"🗓️ 活動時間: {event_data['event_datetime'][:100]}...")
                print(f"🎟️ 售票資訊: {event_data['sale_info'][:100]}...")
                print(f"📍 活動地點: {event_data['location'][:100]}...")
                print(f"💰 票價資訊: {event_data['price'][:100]}...")
                
            else:
                print(f"\n📋 ⚠️ 未能獲取足夠的詳細資訊，保持預設值")
            
            print(f"🔗 活動網址: {url}")
            
            # === 即時保存單個活動 ===
            save_success = self._save_single_event(event_data)
            
            if save_success:
                print(f"✅ 第 {index} 個活動抓取並保存完成")
                return True
            else:
                print(f"⚠️ 第 {index} 個活動抓取完成但保存失敗")
                return False
            
        except Exception as e:
            print(f"❌ 第 {index} 個活動抓取失敗: {e}")
            print(f"⏭️  記錄失敗資料並跳過...")
            
            # 即使失敗也要記錄基本資訊
            event_data['error'] = str(e)
            self._save_single_event(event_data)
            return False
    
    def run_ultimate_crawl(self):
        """執行終極版智能化深度爬取"""
        print("\n🌟 開始執行 Tixcraft 終極爬蟲系統 v5.0")
        print("=" * 70)
        
        try:
            print("🌐 【步驟 1】正在載入活動列表頁面...")
            
            # === 第一層：抓取所有活動網址 ===
            activity_urls = self.scrape_activity_list_enhanced()
            
            if not activity_urls:
                print("❌ 未找到任何活動網址，程式結束")
                return
            
            print(f"\n📊 找到 {len(activity_urls)} 個活動，準備開始逐一爬取")
            
            # 檢查是否有已爬取的資料
            existing_count = len(self.current_data['events'])
            if existing_count > 0:
                print(f"📂 發現已存在 {existing_count} 筆資料，將進行增量爬取")
            
            # === 第二層：迴圈點入抓取詳細資訊 ===
            print(f"\n🔄 【第二層】開始迴圈爬取詳細資訊...")
            print("=" * 70)
            
            success_count = 0
            fail_count = 0
            skip_count = 0
            
            for idx, url in enumerate(activity_urls, 1):
                try:
                    # 檢查是否已經爬取過
                    existing_urls = [event['url'] for event in self.current_data['events']]
                    if url in existing_urls:
                        print(f"⏭️  第 {idx} 個活動已存在，跳過: {url}")
                        skip_count += 1
                        continue
                    
                    # 爬取單個活動資訊
                    success = self.scrape_single_event_ultimate(url, idx)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        
                    # 每爬取5個活動後短暫休息
                    if idx % 5 == 0:
                        print(f"\n⏳ 已處理 {idx} 個活動，休息 2 秒...")
                        sleep(2)
                        
                except KeyboardInterrupt:
                    print(f"\n⚠️ 使用者中斷程式")
                    break
                except Exception as e:
                    print(f"❌ 處理第 {idx} 個活動時發生錯誤: {e}")
                    fail_count += 1
                    continue
            
            # === 完成統計 ===
            total_processed = success_count + fail_count
            total_in_db = len(self.current_data['events'])
            
            print("\n" + "=" * 70)
            print("🎉 Tixcraft 終極爬蟲系統執行完成！")
            print("=" * 70)
            print(f"📊 本次爬取統計：")
            print(f"   ✅ 成功爬取：{success_count} 個活動")
            print(f"   ❌ 失敗跳過：{fail_count} 個活動")
            print(f"   ⏭️  重複跳過：{skip_count} 個活動")
            print(f"   📋 本次處理：{total_processed} 個活動")
            if total_processed > 0:
                print(f"   📈 成功率：{(success_count/total_processed*100):.1f}%")
            
            print(f"\n💾 資料庫統計：")
            print(f"   📁 檔案名稱：{self.json_filename}")
            print(f"   📋 總活動數：{total_in_db} 個")
            print(f"   🕐 最後更新：{self.current_data.get('last_update', 'N/A')}")
            
            # 計算各欄位的有效資料數量
            if total_in_db > 0:
                valid_titles = sum(1 for e in self.current_data['events'] if e.get('title', '') != '請參閱官網詳細說明')
                valid_datetime = sum(1 for e in self.current_data['events'] if e.get('event_datetime', '') != '請參閱官網詳細說明')
                valid_sale = sum(1 for e in self.current_data['events'] if e.get('sale_info', '') != '請參閱官網詳細說明')
                valid_locations = sum(1 for e in self.current_data['events'] if e.get('location', '') != '請參閱官網詳細說明')
                valid_prices = sum(1 for e in self.current_data['events'] if e.get('price', '') != '請參閱官網詳細說明')
                
                print(f"\n📈 資料品質統計：")
                print(f"   🎭 有標題的：{valid_titles} 個 ({(valid_titles/total_in_db*100):.1f}%)")
                print(f"   🗓️ 有活動時間：{valid_datetime} 個 ({(valid_datetime/total_in_db*100):.1f}%)")
                print(f"   🎟️ 有售票資訊：{valid_sale} 個 ({(valid_sale/total_in_db*100):.1f}%)")
                print(f"   📍 有地點的：{valid_locations} 個 ({(valid_locations/total_in_db*100):.1f}%)")
                print(f"   💰 有票價的：{valid_prices} 個 ({(valid_prices/total_in_db*100):.1f}%)")
            
        except KeyboardInterrupt:
            print("\n⚠️ 程式被使用者中斷")
        except Exception as e:
            print(f"❌ 執行錯誤：{e}")
        finally:
            print(f"\n🔚 程式執行完成")
            print("=" * 70)
            input("按 Enter 鍵關閉瀏覽器並結束程式...")
            
            print("🔚 正在關閉瀏覽器...")
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
            print("✅ 瀏覽器已關閉，程式結束")


def main():
    """主程式進入點"""
    print("\n" + "=" * 80)
    print("🧠 Tixcraft 終極爬蟲系統 v5.0 - 精確分流版")
    print("=" * 80)
    
    TARGET_URL = "https://tixcraft.com/activity"
    
    print(f"🎯 目標網址：{TARGET_URL}")
    print(f"📅 當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    print("\n🚀 系統功能特色：")
    print("💡 精確「行」分流：避免重複與誤抓")
    print("🔍 JS載入優化：WebDriverWait監控dataLayer.artistName")
    print("💾 即時寫入：每個URL爬完立刻保存，支援斷點續爬")
    print("🎯 智能場館辨識：過濾文宣，保留核心地點資訊")
    print("🛡️ 三層標題策略：JS → HTML → 保底，絕不出現「js失敗」")
    print("🔄 增量爬取：自動跳過已爬取的活動")
    print("-" * 60)
    
    try:
        crawler = TixcraftUltimateCrawler(TARGET_URL)
        crawler.run_ultimate_crawl()
    except Exception as e:
        print(f"\n❌ 主程式執行錯誤：{e}")
        print("程式發生未預期的錯誤")
    finally:
        print("\n" + "=" * 80)
        print("🔚 程式執行結束")
        print("=" * 80)
        input("\n按 Enter 鍵關閉視窗...")


if __name__ == "__main__":
    main()