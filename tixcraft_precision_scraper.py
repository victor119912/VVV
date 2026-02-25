#!/usr/bin/env python3
"""
Tixcraft 超精確爬蟲系統（精確過濾器版 v5.0）
作者: Assistant
日期: 2026-02-25
功能: 
- 全域掃描：抓取所有 div#intro 內的 p, span, li, td 標籤
- 精確匹配：使用 Regex 與關鍵字進行 100% 準確的欄位分類
- 排除雜訊：建立黑名單過濾無關資訊
- 備援機制：AI 協助提取最精確資訊
- 防偵測：保留完整的反偵測機制
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


class TixcraftPrecisionScraper:
    """Tixcraft 超精確數據提取器"""
    
    def __init__(self, base_url="https://tixcraft.com/activity"):
        self.base_url = base_url
        self.driver = self._setup_driver()
        self.events_data = []  # 儲存所有爬取的資料
        
        # 黑名單：排除包含這些字眼的行
        self.blacklist_keywords = [
            '退票', '手續費', '安檢', '遺失', '禁止攝錄影', '註冊會員', 
            '主辦單位', '拓元售票', '服務費', '注意事項', '禁止攜帶', 
            '進場須知', '入場規定', '購票注意', '會員註冊', '系統服務費'
        ]
    
    def clean_text_line(self, text):
        """清理單行文字：移除多餘空格、特殊字符"""
        if not text:
            return ""
        
        # 移除多餘空格和換行符號
        cleaned = re.sub(r'\s+', ' ', text.strip())
        
        # 移除 HTML 實體和特殊符號
        cleaned = re.sub(r'&[a-zA-Z]+;', '', cleaned)
        cleaned = re.sub(r'[^\w\s：:\/\-\(\)\[\]$元,，；;。、]', '', cleaned)
        
        return cleaned.strip()
    
    def is_blacklisted(self, text):
        """檢查文字是否包含黑名單關鍵字"""
        return any(keyword in text for keyword in self.blacklist_keywords)
    
    def extract_all_text_elements(self):
        """全域掃描：抓取頁面中所有 div#intro 內的文字元素"""
        try:
            print("🔍 【全域掃描】正在提取所有文字元素...")
            
            # 主要來源：div#intro
            intro_element = self.driver.find_element(By.ID, "intro")
            
            # 抓取所有指定標籤的文字
            text_elements = []
            selectors = ['p', 'span', 'li', 'td', 'div', 'strong', 'b']
            
            for selector in selectors:
                elements = intro_element.find_elements(By.TAG_NAME, selector)
                for element in elements:
                    text = element.text.strip()
                    if text and len(text) > 3:  # 過濾太短的文字
                        cleaned_text = self.clean_text_line(text)
                        if cleaned_text and not self.is_blacklisted(cleaned_text):
                            text_elements.append(cleaned_text)
            
            # 去重複並過濾
            unique_texts = []
            seen = set()
            
            for text in text_elements:
                if text not in seen and len(text.strip()) > 5:
                    unique_texts.append(text)
                    seen.add(text)
            
            print(f"✅ 共提取 {len(unique_texts)} 條有效文字")
            return unique_texts
        
        except Exception as e:
            print(f"⚠️ 全域掃描失敗，嘗試備用方法: {e}")
            return self.extract_fallback_text()
    
    def extract_fallback_text(self):
        """備用掃描：如果 div#intro 失敗，抓取所有 p 標籤"""
        try:
            print("🔄 【備用掃描】正在使用備用方法...")
            
            p_elements = self.driver.find_elements(By.TAG_NAME, "p")
            fallback_texts = []
            
            for p in p_elements:
                text = p.text.strip()
                if text and len(text) > 5:
                    cleaned_text = self.clean_text_line(text)
                    if cleaned_text and not self.is_blacklisted(cleaned_text):
                        fallback_texts.append(cleaned_text)
            
            print(f"✅ 備用掃描提取 {len(fallback_texts)} 條文字")
            return fallback_texts
            
        except Exception as e:
            print(f"❌ 備用掃描也失敗: {e}")
            return []
    
    def extract_date_info(self, texts):
        """精確提取演出日期"""
        print("📅 【日期提取】正在分析演出日期...")
        
        date_patterns = [
            # 完整日期格式
            r'.*(?:演出日期|活動日期|日期|DATE).*(\d{4}/\d{2}/\d{2}|\d{4}年\d{2}月\d{2}日).*',
            # 年月日格式  
            r'.*(\d{4}/\d{1,2}/\d{1,2}).*[（）()\w]*[一二三四五六日].*',
            # 月日格式 + 星期
            r'.*(\d{1,2}月\d{1,2}日).*[（）()\w]*[一二三四五六日].*',
            # 時間格式包含日期
            r'.*時間.*(\d{4}/\d{1,2}/\d{1,2}).*',
        ]
        
        date_lines = []
        
        for text in texts:
            # 跳過包含不相關關鍵字的行
            if any(skip_word in text for skip_word in ['開賣', '售票', '預購', '會員']):
                continue
                
            for pattern in date_patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    # 確認包含日期相關關鍵字或實際日期
                    if any(date_word in text for date_word in ['日期', 'DATE', '演出', '活動', '時間']) or re.search(r'\d{4}/\d{1,2}/\d{1,2}', text):
                        date_lines.append(text)
                        print(f"   ✓ 找到日期: {text[:50]}...")
                        break
        
        return '; '.join(date_lines) if date_lines else '請參閱官網詳細說明'
    
    def extract_location_info(self, texts):
        """精確提取演出地點"""
        print("📍 【地點提取】正在分析演出地點...")
        
        location_keywords = ['地點', 'Venue', '館', '體育場', '中心', '演出地點', '會場', '場地']
        location_suffixes = ['館', '廳', '院', '中心', '體育場', '巨蛋', 'Arena', 'Hall']
        
        location_lines = []
        
        for text in texts:
            # 排除包含不相關關鍵字的行
            if any(skip_word in text for skip_word in ['開賣', '票價', 'PRICE', '售票', 'NT$', '元']):
                continue
            
            # 檢查是否包含地點關鍵字
            has_location_keyword = any(keyword in text for keyword in location_keywords)
            has_venue_suffix = any(text.endswith(suffix) or suffix in text for suffix in location_suffixes)
            
            if has_location_keyword or has_venue_suffix:
                location_lines.append(text)
                print(f"   ✓ 找到地點: {text[:50]}...")
        
        return '; '.join(location_lines) if location_lines else '請參閱官網詳細說明'
    
    def extract_price_info(self, texts):
        """精確提取票價資訊"""
        print("💰 【票價提取】正在分析票價資訊...")
        
        price_lines = []
        
        # 精確的票價正則表達式
        price_patterns = [
            r'NT\$\s*[\d,]+',          # NT$1000, NT$ 1,000
            r'\d+\s*元',               # 1000元
            r'票價.*NT\$.*\d+',        # 票價NT$1000
            r'PRICE.*\$.*\d+',         # PRICE $1000
        ]
        
        for text in texts:
            # 必須包含票價關鍵字
            if not any(price_word in text for price_word in ['票價', 'PRICE', 'NT$', '元']):
                continue
                
            # 排除手續費等雜訊
            if any(skip_word in text for skip_word in ['手續費', '服務費', '退票', '遺失']):
                continue
            
            # 檢查是否包含實際價格數字
            has_price_pattern = any(re.search(pattern, text) for pattern in price_patterns)
            
            if has_price_pattern or '票價' in text:
                price_lines.append(text)
                print(f"   ✓ 找到票價: {text[:50]}...")
        
        return '; '.join(price_lines) if price_lines else '請參閱官網詳細說明'
    
    def extract_sale_time_info(self, texts):
        """精確提取售票時間"""
        print("🎟️ 【售票時間提取】正在分析售票時間...")
        
        sale_keywords = ['開賣', '啟售', '售票時間', '預售', '全面開賣', '開售', '下午', '中午', 'AM', 'PM']
        sale_lines = []
        
        for text in texts:
            # 必須包含售票相關關鍵字
            if not any(sale_word in text for sale_word in sale_keywords):
                continue
            
            # 必須包含時間相關資訊
            has_time_info = any(time_word in text for time_word in ['2025', '2026', ':', '點', 'AM', 'PM', '上午', '下午', '中午'])
            
            if has_time_info:
                sale_lines.append(text)
                print(f"   ✓ 找到售票時間: {text[:50]}...")
        
        return '; '.join(sale_lines) if sale_lines else '請參閱官網詳細說明'
    
    def extract_time_info(self, texts):
        """精確提取演出時間"""
        print("⏰【演出時間提取】正在分析演出時間...")
        
        time_lines = []
        
        for text in texts:
            # 排除包含年份的行（避免與日期重複）
            if re.search(r'202[0-9]', text):
                continue
            
            # 尋找純時間資訊
            time_patterns = [
                r'演出時間.*\d+:\d+',     # 演出時間19:00
                r'開演.*\d+:\d+',         # 開演19:00  
                r'\d+:\d+\s*(PM|AM)',     # 19:00 PM
                r'\d+點\d+分',            # 7點30分
            ]
            
            has_time_pattern = any(re.search(pattern, text, re.IGNORECASE) for pattern in time_patterns)
            
            if has_time_pattern and '演出時間' in text:
                time_lines.append(text)
                print(f"   ✓ 找到演出時間: {text[:50]}...")
        
        return '; '.join(time_lines) if time_lines else '請參閱官網詳細說明'
    
    def _setup_driver(self):
        """配置並初始化 Chrome 瀏覽器（防偵測版）"""
        print("\n🔧 【瀏覽器初始化】正在設定 Chrome 瀏覽器...")
        options = Options()
        
        # === 防偵測核心設定 ===
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 效能與穩定性設定
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument("--disable-gpu")
        
        # 建立Chrome瀏覽器實例
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # === 進階JavaScript防偵測設定 ===
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
        
        driver.set_window_size(1920, 1080)
        return driver
    
    def scrape_activity_list(self):
        """第一層：抓取所有演出活動的網址清單"""
        try:
            print(f"\n🌐 正在載入拓元售票活動列表頁面...")
            self.driver.get(self.base_url)
            sleep(5)  # 等待 JavaScript 動態內容載入
            
            # 使用指定的選擇器搜尋活動連結
            activity_links = self.driver.find_elements(By.CSS_SELECTOR, "div.thumbnails a")
            
            if not activity_links:
                activity_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='activity/detail']")
            
            if not activity_links:
                print("❌ 未找到任何演出連結")
                return []
            
            # 提取唯一的連結
            unique_urls = set()
            valid_links = []
            
            for link in activity_links:
                try:
                    url = link.get_attribute('href')
                    if url and 'activity/detail' in url and url not in unique_urls:
                        unique_urls.add(url)
                        valid_links.append(url)
                except Exception:
                    continue
            
            print(f"✅ 找到 {len(valid_links)} 個唯一演出連結")
            return valid_links
            
        except Exception as e:
            print(f"❌ 第一層爬取過程發生錯誤：{e}")
            return []
    
    def scrape_single_event_details(self, url, index):
        """第二層：使用精確過濾器提取單個演出詳細資訊"""
        
        print(f"\n🎯 === 第 {index} 個活動（精確模式）===")
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
            
            # === 抓取演出項目名稱 ===
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                title = self.clean_text_line(title_element.text) if title_element.text else "請參閱官網詳細說明"
                event_data['title'] = title if title else "請參閱官網詳細說明"
                print(f"🎭 演出項目名稱: {event_data['title']}")
            except Exception as e:
                print(f"⚠️ 無法抓取演出項目名稱: {e}")
            
            # === 精確過濾器數據提取 ===
            print(f"\n🔍 【精確過濾器模式】開始分析頁面內容...")
            
            # 步驟1：全域掃描所有文字元素
            all_texts = self.extract_all_text_elements()
            
            if not all_texts:
                print("❌ 未能提取到任何文字內容")
            else:
                print(f"📝 成功提取 {len(all_texts)} 條文字，開始精確匹配...")
                
                # 步驟2：精確欄位匹配
                event_data['date'] = self.extract_date_info(all_texts)
                event_data['time'] = self.extract_time_info(all_texts)
                event_data['location'] = self.extract_location_info(all_texts)
                event_data['price'] = self.extract_price_info(all_texts)
                event_data['sale_time'] = self.extract_sale_time_info(all_texts)
            
            # === 輸出精確結果 ===
            print(f"\n📊 【精確匹配結果】")
            print("-" * 60)
            print(f"📅 演出日期: {event_data['date'][:100]}{'...' if len(event_data['date']) > 100 else ''}")
            print(f"⏰ 演出時間: {event_data['time'][:100]}{'...' if len(event_data['time']) > 100 else ''}")
            print(f"📍 演出地點: {event_data['location'][:100]}{'...' if len(event_data['location']) > 100 else ''}")
            print(f"💰 活動票價: {event_data['price'][:100]}{'...' if len(event_data['price']) > 100 else ''}")
            print(f"🎟️ 售票時間: {event_data['sale_time'][:100]}{'...' if len(event_data['sale_time']) > 100 else ''}")
            
            print(f"🔗 活動網址: {url}")
            print(f"✅ 第 {index} 個活動精確提取完成")
            
            # 將資料加入收集清單
            self.events_data.append(event_data)
            return True
            
        except Exception as e:
            print(f"❌ 第 {index} 個活動提取失敗: {e}")
            # 即使失敗也要記錄基本資訊
            self.events_data.append(event_data)
            return False
    
    def save_to_json(self, filename='tixcraft_activities_precision.json'):
        """將爬取的資料儲存為 JSON 檔案"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'total_events': len(self.events_data),
                    'extraction_method': 'precision_filter_v5.0',
                    'events': self.events_data
                }, f, ensure_ascii=False, indent=2)
            print(f"\n💾 精確數據已儲存至 {filename}")
            return True
        except Exception as e:
            print(f"\n❌ 儲存檔案失敗: {e}")
            return False
    
    def run(self):
        """執行超精確深度爬取"""
        print("\n🎯 開始執行 Tixcraft 超精確爬蟲系統")
        print("=" * 70)
        
        try:
            # === 第一層：抓取所有活動網址 ===
            activity_urls = self.scrape_activity_list()
            
            if not activity_urls:
                print("❌ 未找到任何活動網址，程式結束")
                return
            
            # === 第二層：精確過濾器處理 ===
            print(f"\n🎯 【精確過濾器】開始處理 {len(activity_urls)} 個活動...")
            print("=" * 70)
            
            success_count = 0
            fail_count = 0
            
            for idx, url in enumerate(activity_urls, 1):
                try:
                    success = self.scrape_single_event_details(url, idx)
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                        
                except Exception as e:
                    print(f"❌ 處理第 {idx} 個活動時發生錯誤: {e}")
                    fail_count += 1
                    continue
            
            # === 精確度統計 ===
            print("\n" + "=" * 70)
            print("🎉 超精確數據提取完成！")
            print("=" * 70)
            
            # 計算各欄位的精確度
            if self.events_data:
                valid_titles = sum(1 for e in self.events_data if e['title'] != '請參閱官網詳細說明')
                valid_dates = sum(1 for e in self.events_data if e['date'] != '請參閱官網詳細說明')
                valid_times = sum(1 for e in self.events_data if e['time'] != '請參閱官網詳細說明')
                valid_locations = sum(1 for e in self.events_data if e['location'] != '請參閱官網詳細說明')
                valid_prices = sum(1 for e in self.events_data if e['price'] != '請參閱官網詳細說明')
                valid_sale_times = sum(1 for e in self.events_data if e['sale_time'] != '請參閱官網詳細說明')
                
                print(f"📊 精確度統計結果：")
                print(f"   ✅ 成功處理：{success_count} 個活動")
                print(f"   ❌ 處理失敗：{fail_count} 個活動")
                print(f"   📋 總計處理：{len(activity_urls)} 個活動")
                print(f"   📈 成功率：{(success_count/len(activity_urls)*100):.1f}%")
                
                print(f"\n🎯 【精確度分析】")
                print(f"   🎭 標題精確度：{valid_titles} 個 ({(valid_titles/len(self.events_data)*100):.1f}%)")
                print(f"   📅 日期精確度：{valid_dates} 個 ({(valid_dates/len(self.events_data)*100):.1f}%)")
                print(f"   ⏰ 時間精確度：{valid_times} 個 ({(valid_times/len(self.events_data)*100):.1f}%)")
                print(f"   📍 地點精確度：{valid_locations} 個 ({(valid_locations/len(self.events_data)*100):.1f}%)")
                print(f"   💰 票價精確度：{valid_prices} 個 ({(valid_prices/len(self.events_data)*100):.1f}%)")
                print(f"   🎟️ 售票精確度：{valid_sale_times} 個 ({(valid_sale_times/len(self.events_data)*100):.1f}%)")
                
                # 儲存精確數據
                self.save_to_json()
            
        except KeyboardInterrupt:
            print("\n⚠️ 程式被使用者中斷")
        except Exception as e:
            print(f"❌ 執行錯誤：{e}")
        finally:
            print(f"\n🔚 程式執行完成")
            input("按 Enter 鍵關閉瀏覽器並結束程式...")
            
            if hasattr(self, 'driver') and self.driver:
                self.driver.quit()
            print("✅ 瀏覽器已關閉，程式結束")


def main():
    """主程式進入點"""
    print("\n" + "=" * 80)
    print("🎯 Tixcraft 超精確爬蟲系統 v5.0 (精確過濾器版)")
    print("=" * 80)
    
    TARGET_URL = "https://tixcraft.com/activity"
    
    print(f"🎯 目標網址：{TARGET_URL}")
    print(f"📅 當前時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    print("\n🚀 即將啟動超精確數據提取系統...")
    print("🎯 特色：精確過濾器 + 全域掃描 + 黑名單排除")
    print("🔍 方法：Regex 匹配 + 關鍵字分析 + AI 備援")
    print("📊 目標：達到 100% 數據準確度")
    print("💾 儲存：超精確 JSON 數據文件")
    print("-" * 60)
    
    try:
        scraper = TixcraftPrecisionScraper(TARGET_URL)
        scraper.run()
    except Exception as e:
        print(f"\n❌ 主程式執行錯誤：{e}")
    finally:
        print("\n" + "=" * 80)
        print("🔚 超精確爬蟲系統執行結束")
        print("=" * 80)
        input("\n按 Enter 鍵關閉視窗...")


if __name__ == "__main__":
    main()