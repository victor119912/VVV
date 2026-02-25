import json
import re
import time
import random
import logging
import pandas as pd
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

class TixcraftUltimateScraper:
    """終極版 Tixcraft 爬蟲 - 智能語意過濾與即時同步"""
    
    def __init__(self):
        self.setup_logging()
        self.driver = None
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]
        
    def setup_logging(self):
        """設置日誌系統"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tixcraft_ultimate.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_stealth_driver(self):
        """設置隱身瀏覽器 - 強化版反偵測"""
        chrome_options = Options()
        
        # 隱身設定
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 性能優化
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 隨機 User-Agent
        random_ua = random.choice(self.user_agents)
        chrome_options.add_argument(f'--user-agent={random_ua}')
        
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 移除 webdriver 標識
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            self.logger.info(f"✅ 隱身瀏覽器啟動成功 - UA: {random_ua[:50]}...")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 瀏覽器啟動失敗: {e}")
            return False
    
    def get_data_from_js(self, max_wait_time=5, check_interval=0.5):
        """JavaScript 監控 dataLayer - setInterval 版本"""
        self.logger.info(f"🔍 開始 JS 監控 dataLayer，最多等待 {max_wait_time} 秒...")
        
        # JavaScript setInterval 監控腳本
        js_monitor_script = """
        return new Promise((resolve) => {
            let attempts = 0;
            const maxAttempts = arguments[0] / arguments[1]; // max_wait_time / check_interval
            
            const checkDataLayer = () => {
                attempts++;
                
                try {
                    if (window.dataLayer && window.dataLayer.length > 0) {
                        for (let i = window.dataLayer.length - 1; i >= 0; i--) {
                            const item = window.dataLayer[i];
                            
                            if (item && (item.artistName || item.gameCode)) {
                                resolve({
                                    found: true,
                                    title: item.artistName || item.eventName || '未抓到標題',
                                    game_code: item.gameCode || 'N/A',
                                    category: item.childCategoryName || item.category || '未抓到分類',
                                    promoter: item.promoter || 'N/A',
                                    attempts: attempts
                                });
                                return;
                            }
                        }
                    }
                } catch (e) {
                    console.log('DataLayer 檢查錯誤:', e);
                }
                
                if (attempts >= maxAttempts) {
                    resolve({
                        found: false,
                        title: document.title || 'JS監控超時',
                        game_code: 'N/A',
                        category: '未抓到分類',
                        promoter: 'N/A',
                        attempts: attempts
                    });
                } else {
                    setTimeout(checkDataLayer, arguments[1] * 1000); // check_interval in ms
                }
            };
            
            checkDataLayer();
        });
        """
        
        try:
            result = self.driver.execute_async_script(js_monitor_script, max_wait_time, check_interval)
            
            if result['found']:
                self.logger.info(f"🎯 第 {result['attempts']} 次嘗試成功！找到 dataLayer: {result['title']}")
            else:
                self.logger.warning(f"⏰ JS 監控超時 ({result['attempts']} 次嘗試)，使用 document.title 作為備援")
                
            return result
            
        except Exception as e:
            self.logger.error(f"❌ JavaScript 執行失敗: {e}")
            return {
                'found': False,
                'title': 'JS執行失敗',
                'game_code': 'N/A',
                'category': '未抓到分類',
                'promoter': 'N/A',
                'attempts': 0
            }
    
    def semantic_filter_event_info(self, lines):
        """語意過濾 - 演出資訊提取"""
        event_info_lines = []
        
        # 日期時間模式
        datetime_patterns = [
            r'\d{4}/\d{1,2}/\d{1,2}',     # YYYY/MM/DD
            r'\d{1,2}/\d{1,2}/\d{4}',     # MM/DD/YYYY  
            r'\d{1,2}/\d{1,2}',           # MM/DD
            r'\d{4}-\d{1,2}-\d{1,2}',     # YYYY-MM-DD
            r'\d{4}年\d{1,2}月\d{1,2}日', # YYYY年MM月DD日
            r'\d{1,2}月\d{1,2}日',        # MM月DD日
            r'\d{1,2}:\d{2}',             # HH:MM
            r'\d{1,2}：\d{2}'             # HH：MM
        ]
        
        # 售票關鍵字（這些會被歸類到 sale_time）
        sale_time_keywords = ['售票', '開賣', '預售', '啟售', '購票', '預購', '開放購買']
        
        for line in lines:
            line = line.strip()
            if len(line) < 3:
                continue
                
            # 檢查是否包含日期時間
            has_datetime = any(re.search(pattern, line) for pattern in datetime_patterns)
            
            if has_datetime:
                # 如果包含售票關鍵字，跳過（這會在 sale_time 處理）
                is_sale_time = any(keyword in line for keyword in sale_time_keywords)
                if not is_sale_time:
                    clean_line = self.clean_text(line)
                    if clean_line and clean_line not in event_info_lines:
                        event_info_lines.append(clean_line)
        
        return ' ; '.join(event_info_lines[:3])  # 最多3行
        
    def semantic_filter_price(self, lines):
        """語意過濾 - 票價提取"""
        price_lines = []
        
        # 票價模式 - 更精確的匹配
        price_patterns = [
            r'NT\$[\d,]+',              # NT$1,800
            r'\$[\d,]+',                # $1,800  
            r'[\d,]+元',                # 1,800元
            r'VVIP[\s:：]*[\d,]+',      # VVIP 8,800
            r'VIP[\s:：]*[\d,]+',       # VIP 5,800
            r'CAT\d+[\s:：]*[\d,]+',    # CAT1 4,800
            r'[\d,]+/[\d,]+',           # 4270/3770
            r'[\d,]+\s*[-~]\s*[\d,]+',  # 1800-3000
            r'免費|FREE|Free',            # 免費
            r'票價[：:][^；;。]*[\d,]+', # 票價：開頭的行
            r'門票[：:][^；;。]*'         # 門票：開頭的行
        ]
        
        # 排除關鍵字 - 更全面
        exclude_keywords = [
            '單筆訂單限購', '系統服務費', '限購1張', '限購', '手續費', 
            '注意事項', '購買前請注意', '活動日期', '演出日期', '售票時間', 
            '預售', '開賣', '演出時間', '開演時間'
        ]
        
        for line in lines:
            line = line.strip()
            if len(line) < 3:
                continue
                
            # 排除規則性文字和非價格相關內容
            if any(keyword in line for keyword in exclude_keywords):
                continue
                
            # 檢查是否包含票價模式
            has_price = any(re.search(pattern, line) for pattern in price_patterns)
            
            if has_price:
                clean_line = self.clean_text(line)
                if clean_line and clean_line not in price_lines:
                    price_lines.append(clean_line)
        
        return ' ; '.join(price_lines[:2])  # 最多2行
        
    def semantic_filter_location(self, lines):
        """語意過濾 - 地點提取"""
        location_lines = []
        
        # 場館關鍵字
        venue_keywords = [
            '體育館', '巨蛋', '中心', 'Legacy', 'Zepp', '海音館', '滑雪場', 
            'Westar', 'Sub Live', 'SUB LIVE', 'Arena', 'Hall', 'Stadium',
            '展覽館', '會議中心', '音樂廳', '演藝廳', 'TICC', 'ATT', 'Dome',
            '地點', '場地', '演出地點', '活動地點'
        ]
        
        # 文宣動詞（用於過濾） - 擴展版
        promotional_verbs = ['重返', '震撼', '篇章', '喚起', '點燃', '引爆', '席捲', '降臨', '登陸', '盛大', '傳奇', '夢幻', '熱血', '回憶', '感動']
        
        for line in lines:
            line = line.strip()
            if len(line) < 3:
                continue
                
            # 檢查是否包含場館關鍵字
            has_venue = any(keyword in line for keyword in venue_keywords)
            
            if has_venue:
                # 強化文宣過濾：檢查多個條件
                has_promotional = any(verb in line for verb in promotional_verbs)
                has_long_description = len(line) > 40
                has_multiple_venues = line.count('館') + line.count('中心') + line.count('巨蛋') > 1
                
                # 更嚴格的文宣過濾
                if has_promotional and has_long_description:
                    self.logger.debug(f"過濾文宣: {line[:30]}...")
                    continue
                    
                # 如果包含多個場館名稱（可能是比較性文宣），跳過
                if has_multiple_venues and has_long_description:
                    continue
                    
                # 優先選擇簡潔的地點資訊（30字以內的優先）
                if len(line) <= 30:
                    clean_line = self.clean_text(line)
                    if clean_line and clean_line not in location_lines:
                        location_lines.append(clean_line)
                elif len(line) <= 50 and not has_promotional:
                    # 較長的但沒有文宣詞的也可以接受
                    clean_line = self.clean_text(line)
                    if clean_line and clean_line not in location_lines:
                        location_lines.append(clean_line)
        
        return ' ; '.join(location_lines[:2])  # 最多2行
        
    def semantic_filter_sale_time(self, lines):
        """語意過濾 - 售票時間提取"""
        sale_time_lines = []
        
        # 售票關鍵字
        sale_keywords = ['售票', '開賣', '預售', '啟售', '購票', '預購', '開放購買', '發售']
        
        # 日期模式（確保是售票時間而不是演出時間）
        date_patterns = [
            r'\d{4}/\d{1,2}/\d{1,2}',
            r'\d{1,2}/\d{1,2}',
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{1,2}月\d{1,2}日'
        ]
        
        for line in lines:
            line = line.strip()
            if len(line) < 5:
                continue
                
            # 必須同時包含售票關鍵字和日期
            has_sale = any(keyword in line for keyword in sale_keywords)
            has_date = any(re.search(pattern, line) for pattern in date_patterns)
            
            if has_sale and has_date:
                clean_line = self.clean_text(line)
                if clean_line and clean_line not in sale_time_lines:
                    sale_time_lines.append(clean_line)
        
        return ' ; '.join(sale_time_lines[:3])  # 最多3行
        
    def clean_text(self, text):
        """文字清理"""
        if not text:
            return ""
            
        # 移除多餘空白和符號
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[★☆▪▫●○■□◆◇▲△▼▽]', '', text)
        
        return text.strip()
    
    def extract_page_content(self, url):
        """提取頁面內容"""
        try:
            self.driver.get(url)
            
            # 等待頁面載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # JavaScript 提取 dataLayer
            js_data = self.get_data_from_js()
            
            # 提取頁面文字內容
            try:
                intro_element = self.driver.find_element(By.CSS_SELECTOR, ".intro, .content, .description, .detail")
                content_text = intro_element.text
            except NoSuchElementException:
                content_text = self.driver.find_element(By.TAG_NAME, "body").text
                
            lines = [line.strip() for line in content_text.split('\n') if line.strip()]
            
            # 語意過濾提取各欄位
            event_info = self.semantic_filter_event_info(lines)
            price = self.semantic_filter_price(lines) 
            location = self.semantic_filter_location(lines)
            sale_time = self.semantic_filter_sale_time(lines)
            
            # 如果語意過濾結果為空，使用備援方法
            if not event_info:
                event_info = "未找到"
            if not price:
                price = "未找到"  
            if not location:
                location = "未找到"
            if not sale_time:
                sale_time = "未找到"
            
            return {
                'title': js_data['title'],
                'event_info': event_info,
                'location': location,
                'price': price,
                'sale_time': sale_time,
                'url': url
            }
            
        except Exception as e:
            self.logger.error(f"❌ 提取頁面內容失敗 {url}: {e}")
            return {
                'title': '提取失敗',
                'event_info': '未找到',
                'location': '未找到', 
                'price': '未找到',
                'sale_time': '未找到',
                'url': url
            }
    
    def load_existing_data(self, filename='tixcraft_activities.json'):
        """載入現有 JSON 資料"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'total_events': 0,
                'success_count': 0,
                'events': []
            }
    
    def save_data_immediately(self, data, filename='tixcraft_activities.json'):
        """即時儲存資料"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            self.logger.error(f"❌ 儲存失敗: {e}")
            return False
    
    def should_skip_url(self, existing_events, url):
        """斷點續爬 - 檢查是否應該跳過此URL"""
        for event in existing_events:
            if event.get('url') == url:
                # 如果標題不是"未找到"，則跳過
                if event.get('title') not in ['未找到', '提取失敗', 'JS監控超時', 'JS執行失敗']:
                    return True, event
                break
        return False, None
    
    def scrape_all_events(self, urls, filename='tixcraft_activities.json'):
        """主要爬取流程 - 即時同步版本"""
        if not self.setup_stealth_driver():
            return False
            
        try:
            total_urls = len(urls)
            success_count = 0
            
            for i, url in enumerate(urls, 1):
                self.logger.info(f"📋 處理活動 {i}/{total_urls}: {url}")
                
                # 載入現有資料
                existing_data = self.load_existing_data(filename)
                existing_events = existing_data.get('events', [])
                
                # 斷點續爬檢查
                should_skip, existing_event = self.should_skip_url(existing_events, url)
                if should_skip:
                    self.logger.info(f"⏭️ 跳過已存在的活動: {existing_event['title']}")
                    success_count += 1
                    continue
                
                # 提取新資料
                event_data = self.extract_page_content(url)
                event_data['index'] = i
                
                # 更新或新增到現有資料
                updated = False
                for j, existing_event in enumerate(existing_events):
                    if existing_event.get('url') == url:
                        existing_events[j] = event_data
                        updated = True
                        break
                
                if not updated:
                    existing_events.append(event_data)
                
                # 更新統計資訊
                existing_data['events'] = existing_events
                existing_data['last_update'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                existing_data['total_events'] = len(existing_events)
                
                # 計算成功率
                valid_events = sum(1 for e in existing_events if e.get('title') not in ['未找到', '提取失敗', 'JS監控超時', 'JS執行失敗'])
                existing_data['success_count'] = valid_events
                existing_data['success_rate'] = f"{(valid_events/len(existing_events)*100):.1f}%" if existing_events else "0%"
                existing_data['current_progress'] = f"{i}/{total_urls}"
                
                # 即時儲存
                if self.save_data_immediately(existing_data, filename):
                    self.logger.info(f"💾 已即時同步至 JSON，進度: {i}/{total_urls} ({i/total_urls*100:.1f}%)")
                    
                    # 顯示提取資訊
                    self.logger.info(f"  標題: {event_data['title']}")
                    self.logger.info(f"  演出資訊: {event_data['event_info'][:50]}...")
                    self.logger.info(f"  地點: {event_data['location'][:30]}...")
                    self.logger.info(f"  票價: {event_data['price'][:30]}...")
                    
                    if event_data['title'] not in ['未找到', '提取失敗', 'JS監控超時', 'JS執行失敗']:
                        success_count += 1
                
                # 防封鎖延遲
                if i % 10 == 0:
                    self.logger.info("😴 已處理10筆，強制休息15秒...")
                    time.sleep(15)
                else:
                    delay = random.uniform(3, 7)
                    self.logger.info(f"⏱️ 隨機延遲 {delay:.1f} 秒...")
                    time.sleep(delay)
            
            self.logger.info(f"🎉 爬取完成！總共 {total_urls} 筆，成功 {success_count} 筆")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ 爬取過程發生錯誤: {e}")
            return False
            
        finally:
            if self.driver:
                self.driver.quit()

def main():
    """主程式入口"""
    # 拓元活動 URL 列表 (範例)
    urls = [
        'https://tixcraft.com/activity/detail/26_fujirock',
        'https://tixcraft.com/activity/detail/26_mltr',
        'https://tixcraft.com/activity/detail/26_kamenashi', 
        'https://tixcraft.com/activity/detail/26_anson_c',
        'https://tixcraft.com/activity/detail/26_anson',
        'https://tixcraft.com/activity/detail/26_ztmy_a',
        'https://tixcraft.com/activity/detail/26_chyiyu',
        'https://tixcraft.com/activity/detail/26_cxm_d',
        'https://tixcraft.com/activity/detail/26_cxm',
        'https://tixcraft.com/activity/detail/26_amz',
        'https://tixcraft.com/activity/detail/26_billyrrom',
        'https://tixcraft.com/activity/detail/26_della'
    ]
    
    # 啟動爬蟲
    scraper = TixcraftUltimateScraper()
    
    print("🚀 TixcraftUltimateScraper 啟動中...")
    print("✨ 功能特色:")
    print("  - JavaScript setInterval 監控 dataLayer")
    print("  - 智能語意過濾 (event_info/price/location/sale_time)")
    print("  - 即時同步 JSON 資料")
    print("  - 斷點續爬功能")
    print("  - 強化防封鎖機制")
    print("-" * 50)
    
    success = scraper.scrape_all_events(urls)
    
    if success:
        print("✅ 爬取任務完成！請查看 tixcraft_activities.json")
    else:
        print("❌ 爬取任務失敗，請查看日誌檔案")

if __name__ == "__main__":
    main()