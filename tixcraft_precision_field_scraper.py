import json
import re
import time
import random
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

class TixcraftPrecisionFieldScraper:
    def __init__(self):
        self.setup_logging()
        self.driver = None
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tixcraft_precision_field.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_existing_data(self, filename='tixcraft_activities.json'):
        """載入現有的JSON資料"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.logger.info(f"成功載入現有資料：{len(data.get('events', []))} 個活動")
                return data
        except FileNotFoundError:
            self.logger.info(f"檔案 {filename} 不存在，將建立新檔案")
            return None
        except Exception as e:
            self.logger.error(f"載入現有資料時發生錯誤：{e}")
            return None
    
    def merge_data(self, existing_data, new_events):
        """合併新舊資料，以URL作為唯一識別符去重複"""
        if not existing_data:
            return new_events
            
        existing_events = existing_data.get('events', [])
        existing_urls = {event['url']: event for event in existing_events}
        
        # 更新或新增事件
        updated_count = 0
        new_count = 0
        
        for new_event in new_events:
            url = new_event['url']
            if url in existing_urls:
                # 更新現有事件（保留索引但更新其他資料）
                old_index = existing_urls[url].get('index', new_event['index'])
                new_event['index'] = old_index
                existing_urls[url] = new_event
                updated_count += 1
                self.logger.debug(f"更新活動：{new_event['title']}")
            else:
                # 新增事件
                existing_urls[url] = new_event
                new_count += 1
                self.logger.debug(f"新增活動：{new_event['title']}")
        
        # 重新排序並分配索引
        merged_events = list(existing_urls.values())
        for i, event in enumerate(merged_events, 1):
            event['index'] = i
            
        self.logger.info(f"資料合併完成：更新 {updated_count} 個活動，新增 {new_count} 個活動，總計 {len(merged_events)} 個活動")
        return merged_events
        
    def get_random_user_agent(self):
        """隨機選擇真實的 User-Agent 字串"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        ]
        return random.choice(user_agents)
        
    def setup_driver(self):
        """設置Chrome瀏覽器選項 - 強化版反偵測功能"""
        chrome_options = Options()
        
        # 關閉 Headless 模式以便手動驗證
        # chrome_options.add_argument('--headless')
        
        # 基本穩定性設定
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1366,768')  # 常見解析度
        
        # 強化版 WebDriver 特徵隱藏
        chrome_options.add_experimental_option("excludeSwitches", [
            "enable-automation",
            "enable-logging",
            "disable-extensions",
            "test-type",
            "disable-background-timer-throttling",
            "disable-renderer-backgrounding",
            "disable-backgrounding-occluded-windows"
        ])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 隨機 User-Agent
        user_agent = self.get_random_user_agent()
        chrome_options.add_argument(f'--user-agent={user_agent}')
        self.logger.info(f"使用 User-Agent: {user_agent}")
        
        # 進階反偵測設定
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        chrome_options.add_argument('--disable-popup-blocking')
        
        # 加速設定 - 禁用圖片和多媒體（保留JavaScript用於dataLayer提取）
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_experimental_option('prefs', {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_setting_values.media_stream': 2,
        })
        
        # 模擬真實瀏覽行為
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_experimental_option('prefs', {
            'profile.default_content_setting_values.notifications': 2,
            'profile.default_content_settings.popups': 0
        })
        
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 執行強化版反偵測腳本
            self.driver.execute_cdp_cmd('Runtime.evaluate', {
                "expression": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            # 隱藏 Selenium 標識
            self.driver.execute_cdp_cmd('Runtime.evaluate', {
                "expression": "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})"
            })
            
            self.driver.execute_cdp_cmd('Runtime.evaluate', {
                "expression": "Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW', 'zh', 'en']})"
            })
            
            self.driver.execute_cdp_cmd('Runtime.evaluate', {
                "expression": "window.chrome = { runtime: {} };"
            })
            
            self.logger.info("Chrome瀏覽器已成功啟動（反偵測模式）")
        except Exception as e:
            self.logger.error(f"Chrome瀏覽器啟動失敗：{e}")
            raise
            
    def clean_text(self, text):
        """清洗器：移除特殊符號和雜質"""
        if not text:
            return ""
            
        # 移除指定的特殊符號
        symbols_to_remove = [';', '&nbsp;', '●', '👉', '※', '★', '▲', '■', '◆', '🎫', '📍', '💎', '❋']
        
        for symbol in symbols_to_remove:
            text = text.replace(symbol, '')
        
        # 移除多餘空白並清理
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
        
    def get_clean_data_from_js(self, driver):
        """
        [暴力強化版] 動態重試監控 JavaScript dataLayer 提取
        - 每隔0.5秒重試，最多等待5秒
        - 擴大搜索範圍：遍歷整個dataLayer陣列
        - 只要含有 artistName、gameCode 或 item_name 就立刻提取
        """
        max_wait_time = 5.0  # 最多等待5秒
        retry_interval = 0.5  # 每0.5秒重試一次
        attempt = 0
        start_time = time.time()
        
        self.logger.info("開始暴力監控 dataLayer，最多等待5秒...")
        
        while time.time() - start_time < max_wait_time:
            attempt += 1
            try:
                # 暴力搜索整個 dataLayer 陣列的 JavaScript 腳本
                js_script = """
                // 確保 dataLayer 存在
                if (typeof dataLayer === 'undefined' || !Array.isArray(dataLayer)) {
                    return null;
                }
                
                // 遍歷整個 dataLayer 陣列，擴大搜索範圍
                for (let i = 0; i < dataLayer.length; i++) {
                    let item = dataLayer[i];
                    
                    // 只要包含以下任一欄位就立刻提取
                    if (item.artistName || item.gameCode || item.item_name) {
                        return {
                            found: true,
                            artistName: item.artistName || item.item_name || '',
                            gameCode: item.gameCode || '',
                            childCategoryName: item.childCategoryName || '',
                            promoter: item.promoter || '',
                            event: item.event || '',
                            venueInfo: item.venueInfo || item.venue || '',
                            location: item.location || '',
                            rawData: item
                        };
                    }
                }
                
                // 如果沒找到，返回搜索狀態
                return {found: false, dataLayerLength: dataLayer.length};
                """
                
                raw_info = driver.execute_script(js_script)
                
                if raw_info and raw_info.get('found'):
                    # 成功找到數據！
                    result = {
                        "title": raw_info.get('artistName', '未抓到標題'),
                        "category": raw_info.get('childCategoryName', '未抓到分類'),
                        "game_code": raw_info.get('gameCode', 'N/A'),
                        "promoter": raw_info.get('promoter', 'N/A'),
                        "venue_info": raw_info.get('venueInfo', ''),
                        "location": raw_info.get('location', '')
                    }
                    
                    self.logger.info(f"🎯 第{attempt}次嘗試成功！找到dataLayer數據: {result['title']}")
                    return result
                
                elif raw_info:
                    self.logger.debug(f"第{attempt}次嘗試：dataLayer長度={raw_info.get('dataLayerLength', 0)}，未找到目標數據")
                else:
                    self.logger.debug(f"第{attempt}次嘗試：dataLayer不存在或無法訪問")
                
                # 如果沒找到，等待後重試
                if time.time() - start_time < max_wait_time:
                    time.sleep(retry_interval)
                    
            except Exception as e:
                self.logger.debug(f"第{attempt}次JavaScript執行失敗: {e}")
                if time.time() - start_time < max_wait_time:
                    time.sleep(retry_interval)
        
        # 超時後返回空結果
        self.logger.warning(f"暴力監控超時({max_wait_time}秒)，共嘗試{attempt}次，未找到有效dataLayer數據")
        return {
            "title": "JS監控超時", 
            "category": "未抓到分類", 
            "game_code": "N/A", 
            "promoter": "N/A",
            "venue_info": "",
            "location": ""
        }
        
    def extract_event_info(self, lines):
        """【合併版】演出資訊提取 - 統一處理日期時間資訊"""
        event_info_lines = []
        
        # 擴展的日期時間匹配模式
        datetime_patterns = [
            r'\d{4}/\d{1,2}/\d{1,2}',     # YYYY/MM/DD 日期格式
            r'\d{1,2}/\d{1,2}/\d{4}',     # MM/DD/YYYY 日期格式  
            r'\d{1,2}/\d{1,2}',          # MM/DD 簡化日期格式
            r'\d{4}-\d{1,2}-\d{1,2}',     # YYYY-MM-DD 日期格式
            r'\d{4}年\d{1,2}月\d{1,2}日', # YYYY年MM月DD日 中文日期格式
            r'\d{1,2}月\d{1,2}日',        # MM月DD日 中文簡化格式
            r'\d{1,2}:\d{2}',           # HH:MM 時間格式
            r'\d{1,2}：\d{2}'           # HH：MM 中文冒號時間格式
        ]
        
        # 相關關鍵字（演出資訊相關）
        event_keywords = [
            '演出日期', '活動日期', '舉辦日期', '表演日期', '開演日期',
            '演出時間', '開演時間', '表演時間', '活動時間',
            '日期', '時間', '開始時間', '活動資訊'
        ]
        
        for line in lines:
            # 排除干擾內容
            if any(exclude in line for exclude in ['退票', '手續費', 'ibon', '客服', '注意事項']):
                continue
                
            # 檢查是否包含日期時間格式或相關關鍵字
            has_datetime = any(re.search(pattern, line) for pattern in datetime_patterns)
            has_keyword = any(keyword in line for keyword in event_keywords)
            
            if has_datetime or has_keyword:
                clean_line = self.clean_text(line)
                if clean_line and clean_line not in event_info_lines:
                    event_info_lines.append(clean_line)
        
        # 合併所有相關資訊，用分號分隔
        if event_info_lines:
            return ' ; '.join(event_info_lines)
        
        return "未找到"
        
    def extract_precise_price(self, lines):
        """活動票價提取 - 放寬規則版"""
        for line in lines:
            # 移除長度限制，改用 Regex 提取
            # 必須包含 NT$ 或 元
            price_matches = re.findall(r'NT\$\s?[\d,]+|[\d,]+元', line)
            
            if price_matches:
                # 檢查是否包含票價相關關鍵字
                price_keywords = ['票價', 'Price', 'NT$', '元', 'VIP', 'VVIP', 'A區', 'B區']
                if any(keyword in line for keyword in price_keywords):
                    return self.clean_text(line)
                    
        return "未找到"
        
    def extract_precise_location(self, lines, js_data=None):
        """【精簡版】演出地點提取 - 自動截斷冗長內容"""
        # 如果 JS 的 dataLayer 物件裡有場館資訊，優先使用
        if js_data:
            if js_data.get('venue_info') and js_data['venue_info'].strip():
                venue_info = self.clean_text(js_data['venue_info'])
                return self.simplify_location(venue_info)
            if js_data.get('location') and js_data['location'].strip():
                location = self.clean_text(js_data['location'])
                return self.simplify_location(location)
        
        # 場館關鍵字
        location_keywords = [
            '地點', 'Venue', '館', '體育場', '中心', 'Legacy', 'Zepp', 
            '演出地點', '活動地點', '舉辦地點', '場地', 'Arena', '巨蛋',
            '音樂中心', '展覽館', '體育館', '演藝廳', '劇院', '音樂廳',
            '工商展覽', 'TICC', 'ATT', '流行音樂', '小巨蛋'
        ]
        
        for line in lines:
            if any(keyword in line for keyword in location_keywords):
                # 優先權處理：如果同時出現「地點」與「注意事項」
                if '地點' in line and '注意事項' in line:
                    location_part = line.split('注意事項')[0]
                    clean_location = self.clean_text(location_part)
                    return self.simplify_location(clean_location)
                else:
                    clean_location = self.clean_text(line)
                    return self.simplify_location(clean_location)
        
        # JS 備援：如果找不到地點，嘗試從主辦方找線索
        if js_data and js_data.get('promoter') and js_data['promoter'] != 'N/A':
            promoter = js_data['promoter']
            if any(venue in promoter for venue in ['台北', '高雄', '台中', '新北']):
                return self.clean_text(f"主辦方線索：{promoter}")
                    
        return "未找到"
    
    def simplify_location(self, location_text):
        """精簡地點資訊 - 自動截斷冗長退票規範"""
        if not location_text or location_text == "未找到":
            return location_text
        
        # 如果字數超過 50 字，檢查是否包含退票規範並自動截斷
        if len(location_text) > 50:
            # 退票規範關鍵字
            refund_keywords = ['退票', '退換', '手續費', '規定', '政策', '條款', '說明', '注意事項', '提醒', '須知']
            
            # 如果包含退票規範，在第一個退票關鍵字前截斷
            for keyword in refund_keywords:
                if keyword in location_text:
                    truncated = location_text.split(keyword)[0].strip()
                    if truncated:
                        self.logger.debug(f"地點資訊已截斷：{len(location_text)} 字 → {len(truncated)} 字")
                        return truncated
                    break
            
            # 如果沒有退票關鍵字但超過 50 字，直接截取前 50 字
            if len(location_text) > 50:
                truncated = location_text[:50] + "..."
                self.logger.debug(f"地點資訊已截斷至 50 字：{truncated}")
                return truncated
        
        return location_text
        
    def extract_precise_sale_time(self, lines):
        """售票時間獨立提取 - 專門處理售票資訊"""
        sale_keywords = ['售票', '開賣', '啟售', '開售', '購票', '預售', '會員購']  # 擴展售票關鍵字
        time_pattern = r'\d{1,2}:\d{2}'  # 時間格式 HH:MM
        
        for line in lines:
            # 檢查是否包含售票關鍵字 
            if any(keyword in line for keyword in sale_keywords):
                # 移除長度限制，只要包含售票關鍵字就保留
                return self.clean_text(line)
                
        return "未找到"
        
    def extract_precise_time_backup(self, lines):
        """演出時間備用提取 - 已整合至 event_info"""
        show_keywords = ['演出', '開演', '表演']  
        time_pattern = r'\d{1,2}:\d{2}'
        
        for line in lines:
            if any(keyword in line for keyword in show_keywords) and re.search(time_pattern, line):
                return self.clean_text(line)
                    
        return "未找到"
        
        
    def extract_all_text_from_intro(self, url):
        """從intro區塊提取所有文字行"""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 提取標題
            title = "未找到"
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                title = self.clean_text(title_element.text)
            except NoSuchElementException:
                try:
                    title_element = self.driver.find_element(By.TAG_NAME, "h1")
                    title = self.clean_text(title_element.text)
                except NoSuchElementException:
                    pass
            
            # 提取intro區塊文字
            lines = []
            try:
                intro_element = self.driver.find_element(By.ID, "intro")
                all_text = intro_element.text
                
                # 按換行分割成獨立行
                lines = [line.strip() for line in all_text.split('\n') if line.strip()]
                
            except NoSuchElementException:
                self.logger.warning(f"未找到intro區塊：{url}")
                
            return title, lines
            
        except Exception as e:
            self.logger.error(f"提取文字失敗 {url}: {e}")
            return "錯誤", []
            
    def process_single_event(self, url, index):
        """處理單一活動的完整邏輯 - 強化版"""
        try:
            self.logger.info(f"處理活動 {index}：{url}")
            
            # 進入頁面並等待JavaScript載入
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(random.uniform(3, 6))  # 隨機等待 3-6 秒
            
            # 優先使用 JavaScript dataLayer 提取精確數據
            js_data = self.get_clean_data_from_js(self.driver)
            
            # 提取HTML基本資訊作為備用
            title, lines = self.extract_all_text_from_intro(url)
            
            # 標題強制補全：絕對不允許『未找到』
            final_title = "未找到"  # 預設值
            
            # 第一優先權：JS標題
            if (js_data.get('title') and 
                js_data['title'] not in ['未抓到標題', 'JS提取失敗', 'JS監控超時', ''] and 
                js_data['title'].strip()):
                final_title = js_data['title']
                self.logger.info(f"  [JS優先] 使用標題: {final_title}")
            # 第二優先權：HTML標題
            elif title and title not in ['未找到', '錯誤', ''] and title.strip():
                final_title = title
                self.logger.info(f"  [HTML備用] 使用標題: {final_title}")
            else:
                # 備援方案：強制使用瀏覽器分頁標題
                try:
                    browser_title = self.driver.title
                    if browser_title and browser_title.strip():
                        # 清理瀏覽器標題
                        clean_browser_title = browser_title.replace('拓元售票網', '').replace('TIXCRAFT', '').strip()
                        if clean_browser_title:
                            final_title = clean_browser_title
                            self.logger.info(f"  [瀏覽器備援] 使用標題: {final_title}")
                        else:
                            # 最後備援：從URL提取活動代碼作為標題
                            url_code = url.split('/')[-1] if '/' in url else 'unknown'
                            final_title = f"活動代碼：{url_code}"
                            self.logger.info(f"  [URL最終備援] 使用標題: {final_title}")
                    else:
                        # 最後備援：從URL提取活動代碼作為標題
                        url_code = url.split('/')[-1] if '/' in url else 'unknown'
                        final_title = f"活動代碼：{url_code}"
                        self.logger.info(f"  [URL最終備援] 使用標題: {final_title}")
                except Exception as e:
                    # 如果連瀏覽器標題都抓不到，使用URL代碼
                    url_code = url.split('/')[-1] if '/' in url else 'unknown'
                    final_title = f"活動代碼：{url_code}"
                    self.logger.warning(f"  [異常備援] 瀏覽器標題提取失敗({e})，使用: {final_title}")
            
            if not lines:
                return {
                    'index': index,
                    'title': final_title,
                    'event_info': "未找到",
                    'location': "未找到",
                    'price': "未找到",
                    'sale_time': "未找到",
                    'url': url
                }
            
            # 使用精確提取規則，防止位移問題 - 【合併版】
            event_info = self.extract_event_info(lines)  # 合併日期時間資訊
            
            # 修正地點提取，傳入 js_data
            location = self.extract_precise_location(lines, js_data)
            price = self.extract_precise_price(lines)
            sale_time = self.extract_precise_sale_time(lines)
            
            result = {
                'index': index,
                'title': final_title,
                'event_info': event_info,  # 合併的演出資訊
                'location': location,
                'price': price,
                'sale_time': sale_time,
                'url': url
            }
            
            # 日誌輸出 - 更新為新格式
            self.logger.info(f"  標題：{final_title}")
            self.logger.info(f"  JS分類：{js_data.get('category', 'N/A')}")
            self.logger.info(f"  遊戲代碼：{js_data.get('game_code', 'N/A')}")
            self.logger.info(f"  主辦方：{js_data.get('promoter', 'N/A')}")
            self.logger.info(f"  演出資訊：{event_info}")  # 合併顯示
            self.logger.info(f"  地點：{location}")
            self.logger.info(f"  票價：{price}")
            self.logger.info(f"  售票時間：{sale_time}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"處理活動失敗 {url}: {e}")
            return {
                'index': index,
                'title': "錯誤",
                'event_info': "提取失敗",
                'location': "提取失敗",
                'price': "提取失敗", 
                'sale_time': "提取失敗",
                'url': url
            }
            
    def scrape_all_events(self):
        """爬取所有活動並處理 - 即時儲存版"""
        output_file = 'tixcraft_activities.json'
        
        try:
            self.setup_driver()
            
            # 獲取活動列表
            base_url = "https://tixcraft.com/activity"
            self.driver.get(base_url)
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.thumbnails"))
            )
            
            # 收集所有活動連結
            activity_links = []
            thumbnails = self.driver.find_elements(By.CSS_SELECTOR, "div.thumbnails a")
            
            for link in thumbnails:
                href = link.get_attribute('href')
                if href and 'activity/detail' in href:
                    activity_links.append(href)
                    
            total_activities = len(activity_links)
            self.logger.info(f"🎯 找到 {total_activities} 個活動，開始即時處理...")
            
            # 即時處理每個活動
            current_success_count = 0
            
            for index, url in enumerate(activity_links, 1):
                # 處理單一活動
                event_data = self.process_single_event(url, index)
                
                if event_data['title'] not in ["錯誤", "提取失敗"]:
                    current_success_count += 1
                
                # ===== 即時儲存模式：每處理完一個活動就立刻存檔 =====
                try:
                    # 讀取現有資料（每次都重新載入確保最新）
                    existing_data = self.load_existing_data(output_file)
                    
                    # 合併新舊資料（將當前處理的活動加入）
                    current_events = [event_data]  # 當前只有一個活動
                    merged_events = self.merge_data(existing_data, current_events)
                    
                    # 重新計算統計資料 - 更新為新欄位結構
                    merged_success_count = sum(1 for event in merged_events 
                                             if not all(field == "未找到" for field in [
                                                 event.get('event_info', ''),  # 更新為合併欄位
                                                 event.get('location', ''),
                                                 event.get('price', ''),
                                                 event.get('sale_time', '')
                                             ]))
                    merged_success_rate = (merged_success_count / len(merged_events)) * 100 if merged_events else 0
                    
                    # 準備即時結果
                    real_time_result = {
                        'scrape_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'last_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'total_events': len(merged_events),
                        'success_count': merged_success_count,
                        'success_rate': f'{merged_success_rate:.1f}%',
                        'extraction_method': 'realtime_precision_field_extraction',
                        'current_progress': f'{index}/{total_activities}',
                        'current_session_success': current_success_count,
                        'events': merged_events
                    }
                    
                    # 即時寫入 JSON 檔案
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(real_time_result, f, ensure_ascii=False, indent=2)
                    
                    # 增加安全感：每次存檔後在 Log 中印出進度
                    self.logger.info(f"💾 已同步至 JSON 檔案，目前進度：{index}/{total_activities} ({index/total_activities*100:.1f}%)")
                    self.logger.info(f"📊 本次成功：{current_success_count}，整體成功率：{merged_success_rate:.1f}%")
                    
                except Exception as save_error:
                    self.logger.error(f"❌ 即時存檔失敗: {save_error}")
                    # 即使存檔失敗也繼續處理下一個活動
                
                # 隨機等待時間，模擬真實瀏覽行為
                time.sleep(random.uniform(2, 4))
                
                # 每 5 個活動就休息 8-12 秒
                if index % 5 == 0:
                    rest_time = random.uniform(8, 12)
                    self.logger.info(f"⏸️  已處理 {index} 個活動，休息 {rest_time:.1f} 秒以避免被封鎖...")
                    time.sleep(rest_time)
            
            # 最終統計和確認
            final_data = self.load_existing_data(output_file)
            final_events = final_data.get('events', []) if final_data else []
            
            self.logger.info(f"🎉 所有活動處理完成！")
            self.logger.info(f"📈 本次工作階段成功處理：{current_success_count}/{total_activities} 個活動")
            self.logger.info(f"📂 最終資料庫包含：{len(final_events)} 個活動")
            self.logger.info(f"💾 即時儲存完成：{output_file}")
            
            # 返回最終結果
            return final_data if final_data else {
                'total_events': 0,
                'success_count': 0,
                'success_rate': '0.0%',
                'current_session_success': current_success_count,
                'events': []
            }
            
        except Exception as e:
            self.logger.error(f"❌ 爬取過程發生錯誤：{e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
                
def main():
    scraper = TixcraftPrecisionFieldScraper()
    result = scraper.scrape_all_events()
    
    if result:
        print(f"\n=== 🎯 即時儲存版資料更新結果 ===")
        print(f"更新時間：{result.get('last_update', 'N/A')}")
        print(f"處理進度：{result.get('current_progress', 'N/A')}")
        print(f"本次工作階段成功：{result.get('current_session_success', 0)} 個")
        print(f"資料庫總計：{result.get('total_events', 0)} 個活動")
        print(f"整體成功率：{result.get('success_rate', '0.0%')}")
        print(f"提取方法：{result.get('extraction_method', 'realtime_precision_field_extraction')}")
        print(f"儲存檔案：tixcraft_activities.json")
        
        # 顯示最近更新的5個活動示例
        events = result.get('events', [])
        if events:
            print(f"\n=== 🔍 最新活動資料示例 ===")
            recent_events = events[:5]  # 取前5個作為示例
            for i, event in enumerate(recent_events, 1):
                print(f"\n【活動 {i}】{event.get('title', 'N/A')}")
                print(f"  📅 演出資訊：{event.get('event_info', 'N/A')}")  # 合併顯示
                print(f"  📍 地點：{event.get('location', 'N/A')}")
                print(f"  💰 票價：{event.get('price', 'N/A')}")
                print(f"  🎟️ 售票時間：{event.get('sale_time', 'N/A')}")
        
        print(f"\n✅ 即時儲存功能已啟用！")
        print(f"💾 每處理一個活動都會立刻更新 JSON 檔案")
        print(f"🔄 資料即時同步，無需等待全部完成")
        print(f"📊 總共管理 {result.get('total_events', 0)} 個活動資料")
        
    else:
        print("❌ 爬取失敗，請檢查日誌文件")

if __name__ == "__main__":
    main()