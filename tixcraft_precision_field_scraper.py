import json
import re
import time
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
        
    def setup_driver(self):
        """設置Chrome瀏覽器選項"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 反偵測設置
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # 設置用戶代理
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 執行反偵測腳本
            self.driver.execute_cdp_cmd('Runtime.evaluate', {
                "expression": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            self.logger.info("Chrome瀏覽器已成功啟動")
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
        [核心功能] 執行 JavaScript 從 dataLayer 提取 100% 準確的後台參數
        """
        try:
            # 這是針對拓元 dataLayer 結構設計的精確提取邏輯
            js_script = """
            var data = dataLayer.find(item => item.artistName !== undefined) || 
                       dataLayer.find(item => item.event === 'EnterActivityDetail') || 
                       {};
            return data;
            """
            raw_info = driver.execute_script(js_script)
            
            if not raw_info:
                return {
                    "title": "未抓到標題", "category": "未抓到分類", 
                    "game_code": "N/A", "promoter": "N/A"
                }

            return {
                "title": raw_info.get('artistName', '未抓到標題'),
                "category": raw_info.get('childCategoryName', '未抓到分類'),
                "game_code": raw_info.get('gameCode', 'N/A'),
                "promoter": raw_info.get('promoter', 'N/A')
            }
        except Exception as e:
            self.logger.error(f"JavaScript 數據提取失敗: {e}")
            return {"title": "JS提取失敗", "category": "JS提取失敗", "game_code": "N/A", "promoter": "N/A"}
        
    def extract_precise_date(self, lines):
        """演出日期精確化提取"""
        for line in lines:
            # 排除包含特定關鍵詞的行
            if any(keyword in line for keyword in ['退票', '手續費', 'ibon']):
                continue
                
            # 長度限制：小於100字
            if len(line) > 100:
                continue
                
            # 檢查是否包含日期格式 YYYY/MM/DD 或 MM/DD
            date_patterns = [
                r'\d{4}/\d{1,2}/\d{1,2}',  # YYYY/MM/DD
                r'\d{1,2}/\d{1,2}',        # MM/DD
                r'\d{4}-\d{1,2}-\d{1,2}',  # YYYY-MM-DD
                r'演出日期',
                r'活動日期',
                r'舉辦日期'
            ]
            
            if any(re.search(pattern, line) for pattern in date_patterns):
                return self.clean_text(line)
                
        return "未找到"
        
    def extract_precise_price(self, lines):
        """活動票價嚴格化提取"""
        for line in lines:
            # 字數超過200字則跳過（通常是退票須知）
            if len(line) > 200:
                continue
                
            # 必須包含 NT$ 或 元
            price_matches = re.findall(r'NT\$\s?[\d,]+|[\d,]+元', line)
            
            if price_matches:
                # 檢查是否包含票價相關關鍵字
                price_keywords = ['票價', 'Price', 'NT$', '元']
                if any(keyword in line for keyword in price_keywords):
                    return self.clean_text(line)
                    
        return "未找到"
        
    def extract_precise_location(self, lines):
        """演出地點鎖定提取"""
        location_keywords = ['地點', 'Venue', '館', '體育場', '中心', 'Legacy', 'Zepp', '演出地點', '活動地點']
        
        for line in lines:
            if any(keyword in line for keyword in location_keywords):
                # 優先權處理：如果同時出現「地點」與「注意事項」
                if '地點' in line and '注意事項' in line:
                    # 提取地點後的內容，截斷注意事項
                    location_part = line.split('注意事項')[0]
                    return self.clean_text(location_part)
                else:
                    return self.clean_text(line)
                    
        return "未找到"
        
    def extract_precise_sale_time(self, lines):
        """售票時間精確提取"""
        sale_keywords = ['開賣', '啟售', '中午', '下午', '售票時間', '開賣時間']
        time_pattern = r'\d{1,2}:\d{2}'  # 時間格式 HH:MM
        
        for line in lines:
            # 檢查是否包含售票關鍵字
            if any(keyword in line for keyword in sale_keywords):
                # 檢查是否包含時間格式
                if re.search(time_pattern, line):
                    return self.clean_text(line)
                    
        return "未找到"
        
    def extract_precise_time(self, lines):
        """演出時間提取"""
        time_keywords = ['演出時間', '開演時間', '表演時間', '時間']
        time_pattern = r'\d{1,2}:\d{2}'
        
        for line in lines:
            if any(keyword in line for keyword in time_keywords):
                if re.search(time_pattern, line):
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
        """處理單一活動的完整邏輯"""
        try:
            self.logger.info(f"處理活動 {index}：{url}")
            
            # 進入頁面並等待JavaScript載入
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)  # 確保 JS 載入完成
            
            # 優先使用 JavaScript dataLayer 提取精確數據
            js_data = self.get_clean_data_from_js(self.driver)
            
            # 提取HTML基本資訊作為備用
            title, lines = self.extract_all_text_from_intro(url)
            
            # 決定最終標題：優先使用JS數據
            final_title = title
            if js_data['title'] != '未抓到標題' and js_data['title'] != 'JS提取失敗':
                final_title = js_data['title']
                self.logger.info(f"  [優先] 使用JS標題: {final_title}")
            else:
                self.logger.info(f"  [備用] 使用HTML標題: {final_title}")
            
            if not lines:
                return {
                    'index': index,
                    'title': final_title,
                    'js_title': js_data['title'],
                    'category': js_data['category'],
                    'game_code': js_data['game_code'],
                    'promoter': js_data['promoter'],
                    'date': "未找到",
                    'time': "未找到", 
                    'location': "未找到",
                    'price': "未找到",
                    'sale_time': "未找到",
                    'url': url
                }
            
            # 使用精確提取規則
            date = self.extract_precise_date(lines)
            time_info = self.extract_precise_time(lines)
            location = self.extract_precise_location(lines)
            price = self.extract_precise_price(lines)
            sale_time = self.extract_precise_sale_time(lines)
            
            result = {
                'index': index,
                'title': final_title,
                'js_title': js_data['title'],
                'category': js_data['category'],
                'game_code': js_data['game_code'],
                'promoter': js_data['promoter'],
                'date': date,
                'time': time_info,
                'location': location,
                'price': price,
                'sale_time': sale_time,
                'url': url
            }
            
            # 日誌輸出
            self.logger.info(f"  標題：{final_title}")
            self.logger.info(f"  JS分類：{js_data['category']}")
            self.logger.info(f"  遊戲代碼：{js_data['game_code']}")
            self.logger.info(f"  主辦方：{js_data['promoter']}")
            self.logger.info(f"  日期：{date}")
            self.logger.info(f"  時間：{time_info}")
            self.logger.info(f"  地點：{location}")
            self.logger.info(f"  票價：{price}")
            self.logger.info(f"  售票時間：{sale_time}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"處理活動失敗 {url}: {e}")
            return {
                'index': index,
                'title': "錯誤",
                'js_title': "提取失敗",
                'category': "提取失敗",
                'game_code': "提取失敗",
                'promoter': "提取失敗",
                'date': "提取失敗",
                'time': "提取失敗",
                'location': "提取失敗",
                'price': "提取失敗", 
                'sale_time': "提取失敗",
                'url': url
            }
            
    def scrape_all_events(self):
        """爬取所有活動並處理"""
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
                    
            self.logger.info(f"找到 {len(activity_links)} 個活動")
            
            # 處理每個活動
            events = []
            success_count = 0
            
            for index, url in enumerate(activity_links, 1):
                event_data = self.process_single_event(url, index)
                events.append(event_data)
                
                if event_data['title'] != "錯誤":
                    success_count += 1
                    
                # 避免過快請求
                time.sleep(1)
            
            # 計算統計數據
            success_rate = (success_count / len(events)) * 100 if events else 0
            
            # 載入現有資料
            existing_data = self.load_existing_data('tixcraft_activities.json')
            
            # 合併新舊資料
            merged_events = self.merge_data(existing_data, events)
            
            # 重新計算統計資料
            merged_success_count = sum(1 for event in merged_events 
                                     if not all(field == "未找到" for field in [
                                         event.get('date', ''),
                                         event.get('time', ''),
                                         event.get('location', ''),
                                         event.get('price', ''),
                                         event.get('sale_time', '')
                                     ]))
            merged_success_rate = (merged_success_count / len(merged_events)) * 100 if merged_events else 0
            
            # 準備最終結果
            result = {
                'scrape_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'last_update': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_events': len(merged_events),
                'success_count': merged_success_count,
                'success_rate': f'{merged_success_rate:.1f}%',
                'extraction_method': 'precision_field_extraction',
                'current_scrape_count': len(events),
                'current_scrape_success': success_count,
                'events': merged_events
            }
            
            # 儲存結果到統一檔案
            output_file = 'tixcraft_activities.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"本次爬取：成功處理 {success_count}/{len(events)} 個活動")
            self.logger.info(f"本次成功率：{success_rate:.1f}%")
            self.logger.info(f"總資料庫：{len(merged_events)} 個活動，整體成功率：{merged_success_rate:.1f}%")
            self.logger.info(f"結果已更新至：{output_file}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"爬取過程發生錯誤：{e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()
                
def main():
    scraper = TixcraftPrecisionFieldScraper()
    result = scraper.scrape_all_events()
    
    if result:
        print(f"\n=== 🎯 增強版資料更新結果 ===")
        print(f"更新時間：{result['last_update']}")
        print(f"本次爬取：{result['current_scrape_count']} 個活動")
        print(f"本次成功：{result['current_scrape_success']} 個")
        print(f"資料庫總計：{result['total_events']} 個活動")
        print(f"整體成功率：{result['success_rate']}")
        print(f"提取方法：{result['extraction_method']} + JavaScript dataLayer")
        print(f"儲存檔案：tixcraft_activities.json")
        
        # 分析JavaScript數據提取效果
        js_success_count = sum(1 for event in result['events'] 
                              if event.get('js_title', '未抓到標題') not in ['未抓到標題', 'JS提取失敗', '提取失敗'])
        print(f"📊 JavaScript成功率：{js_success_count}/{result['total_events']} ({js_success_count/result['total_events']*100:.1f}%)")
        
        # 顯示最近更新的5個活動示例
        print(f"\n=== 🔍 最新活動資料示例 ===")
        recent_events = result['events'][:5]  # 取前5個作為示例
        for i, event in enumerate(recent_events, 1):
            print(f"\n【活動 {i}】{event['title']}")
            print(f"  🎭 JS標題：{event.get('js_title', 'N/A')}")
            print(f"  📂 分類：{event.get('category', 'N/A')}")
            print(f"  🎮 遊戲代碼：{event.get('game_code', 'N/A')}")
            print(f"  🏢 主辦方：{event.get('promoter', 'N/A')}")
            print(f"  📅 日期：{event['date']}")
            print(f"  ⏰ 時間：{event['time']}")
            print(f"  📍 地點：{event['location']}")
            print(f"  💰 票價：{event['price']}")
            print(f"  🎟️ 售票時間：{event['sale_time']}")
        
        print(f"\n✅ 資料已成功更新到 tixcraft_activities.json")
        print(f"🚀 現在包含JavaScript後台數據包提取功能！")
        print(f"📊 總共管理 {result['total_events']} 個活動資料")
        
    else:
        print("❌ 爬取失敗，請檢查日誌文件")

if __name__ == "__main__":
    main()