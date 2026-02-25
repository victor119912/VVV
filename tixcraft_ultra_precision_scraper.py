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

class TixcraftUltraPrecisionScraper:
    def __init__(self):
        self.setup_logging()
        self.driver = None
        
        # 內容截斷關鍵字 - 遇到這些就停止處理後續內容
        self.stop_keywords = [
            '注意事項', '購票注意事項', '購票提醒', '取票提醒', '退票說明',
            '門票注意事項', '購票注意事項', '活動注意事項', '入場注意事項'
        ]
        
        # 強特徵過濾規則
        self.date_patterns = [
            r'\d{4}/\d{1,2}/\d{1,2}',
            r'\d{4}-\d{1,2}-\d{1,2}',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{1,2}-\d{1,2}-\d{4}'
        ]
        
        self.time_patterns = [
            r'\d{1,2}:\d{2}',
            r'\d{1,2}點\d{0,2}分?',
            r'PM|AM|pm|am'
        ]
        
        # 排除關鍵字
        self.date_exclude_keywords = ['退票', '服務費', '機台取票', '手續費', '客服', '取票', '退款']
        self.price_exclude_keywords = ['退款', '手續費', '取票', '客服']
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('tixcraft_ultra_precision.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
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
            
    def clean_html_text(self, text):
        """清理HTML標籤和特殊字符，僅保留純文字"""
        if not text:
            return ""
            
        # 移除HTML標籤
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除HTML實體
        html_entities = {
            '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
            '&quot;': '"', '&#39;': "'", '&hellip;': '...', '&ndash;': '-',
            '&mdash;': '—', '&rsquo;': "'", '&lsquo;': "'", '&rdquo;': '"',
            '&ldquo;': '"', '&middot;': '·', '&bull;': '•'
        }
        
        for entity, replacement in html_entities.items():
            text = text.replace(entity, replacement)
        
        # 清理多餘空白
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
        
    def extract_all_text_elements(self, container):
        """提取容器內所有文字元素並以換行符分割"""
        if not container:
            return []
            
        try:
            # 獲取所有文字內容
            all_elements = container.find_elements(By.XPATH, ".//*[text()]")
            text_lines = []
            
            for element in all_elements:
                text = element.text.strip()
                if text:
                    # 將文字按換行符分割
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    text_lines.extend(lines)
            
            # 去重並保持順序
            unique_lines = []
            seen = set()
            for line in text_lines:
                line = self.clean_html_text(line)
                if line and line not in seen:
                    unique_lines.append(line)
                    seen.add(line)
                    
            return unique_lines
            
        except Exception as e:
            self.logger.warning(f"提取文字元素失敗：{e}")
            return []
            
    def should_stop_processing(self, line):
        """檢查是否遇到停止關鍵字"""
        return any(keyword in line for keyword in self.stop_keywords)
        
    def extract_date_info(self, lines):
        """精確提取演出日期資訊"""
        date_keywords = ['活動日期', '演出日期', '舉辦日期', '時間']
        
        for line in lines:
            # 檢查是否遇到停止關鍵字
            if self.should_stop_processing(line):
                break
                
            # 檢查是否包含排除關鍵字
            if any(exclude in line for exclude in self.date_exclude_keywords):
                continue
                
            # 檢查是否包含日期關鍵字和日期格式
            has_keyword = any(keyword in line for keyword in date_keywords)
            has_date_format = any(re.search(pattern, line) for pattern in self.date_patterns)
            
            if has_keyword and has_date_format:
                return self.clean_html_text(line)
                
        # 如果沒找到含關鍵字的，找純日期格式
        for line in lines:
            if self.should_stop_processing(line):
                break
                
            if any(exclude in line for exclude in self.date_exclude_keywords):
                continue
                
            if any(re.search(pattern, line) for pattern in self.date_patterns):
                return self.clean_html_text(line)
                
        return "未找到"
        
    def extract_time_info(self, lines):
        """精確提取演出時間資訊"""
        time_keywords = ['演出時間', '開演時間', '表演時間', '開始時間']
        
        for line in lines:
            if self.should_stop_processing(line):
                break
                
            # 檢查是否包含時間關鍵字和時間格式
            has_keyword = any(keyword in line for keyword in time_keywords)
            has_time_format = any(re.search(pattern, line) for pattern in self.time_patterns)
            
            if has_keyword and has_time_format:
                return self.clean_html_text(line)
                
        return "未找到"
        
    def extract_location_info(self, lines):
        """精確提取演出地點資訊"""
        location_keywords = ['活動地點', '演出地點', '舉辦地點', '地點', 'Venue', '會場']
        
        for line in lines:
            if self.should_stop_processing(line):
                break
                
            # 檢查是否包含地點關鍵字
            if any(keyword in line for keyword in location_keywords):
                return self.clean_html_text(line)
                
        return "未找到"
        
    def extract_price_info(self, lines):
        """精確提取活動票價資訊"""
        price_keywords = ['票價說明', '票價', '價格', 'NT$', '元', 'Price']
        
        for line in lines:
            if self.should_stop_processing(line):
                break
                
            # 檢查是否包含排除關鍵字
            if any(exclude in line for exclude in self.price_exclude_keywords):
                continue
                
            # 檢查是否包含價格關鍵字和金額數字
            has_keyword = any(keyword in line for keyword in price_keywords)
            has_money = re.search(r'[\d,]+\s*元|NT\$\s*[\d,]+|\$\s*[\d,]+', line)
            
            if has_keyword and has_money:
                return self.clean_html_text(line)
                
        # 如果沒找到含關鍵字的，找純金額格式
        for line in lines:
            if self.should_stop_processing(line):
                break
                
            if any(exclude in line for exclude in self.price_exclude_keywords):
                continue
                
            if re.search(r'[\d,]+\s*元|NT\$\s*[\d,]+|\$\s*[\d,]+', line):
                return self.clean_html_text(line)
                
        return "未找到"
        
    def extract_sale_time_info(self, lines):
        """精確提取售票時間資訊"""
        sale_keywords = ['開賣時間', '啟售時間', '售票時間', '開賣', '預售', '販售']
        
        for line in lines:
            if self.should_stop_processing(line):
                break
                
            # 檢查是否包含售票關鍵字和時間格式
            has_keyword = any(keyword in line for keyword in sale_keywords)
            has_time_format = any(re.search(pattern, line) for pattern in self.time_patterns)
            
            if has_keyword and has_time_format:
                return self.clean_html_text(line)
                
        return "未找到"
        
    def extract_event_details(self, url):
        """提取單一活動詳細資訊"""
        try:
            self.logger.info(f"正在處理活動：{url}")
            self.driver.get(url)
            
            # 等待頁面載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # 提取標題（使用備援標題）
            title = "未找到"
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                title = self.clean_html_text(title_element.text)
            except NoSuchElementException:
                try:
                    title_element = self.driver.find_element(By.TAG_NAME, "h1")
                    title = self.clean_html_text(title_element.text)
                except NoSuchElementException:
                    pass
            
            # 提取intro區塊的所有文字並分行處理
            lines = []
            try:
                intro_container = self.driver.find_element(By.ID, "intro")
                lines = self.extract_all_text_elements(intro_container)
                self.logger.info(f"提取到 {len(lines)} 行文字內容")
            except NoSuchElementException:
                self.logger.warning("未找到intro區塊，嘗試其他選擇器")
                try:
                    # 嘗試其他可能的容器
                    containers = self.driver.find_elements(By.CSS_SELECTOR, ".tab-content, .activity-content, .content")
                    for container in containers:
                        container_lines = self.extract_all_text_elements(container)
                        if container_lines:
                            lines = container_lines
                            break
                except:
                    pass
            
            # 使用強特徵規則提取各欄位
            date = self.extract_date_info(lines)
            time = self.extract_time_info(lines)
            location = self.extract_location_info(lines)
            price = self.extract_price_info(lines)
            sale_time = self.extract_sale_time_info(lines)
            
            return {
                'title': title,
                'date': date,
                'time': time, 
                'location': location,
                'price': price,
                'sale_time': sale_time,
                'url': url
            }
            
        except Exception as e:
            self.logger.error(f"處理活動 {url} 時發生錯誤：{e}")
            return {
                'title': "錯誤",
                'date': "提取失敗",
                'time': "提取失敗",
                'location': "提取失敗", 
                'price': "提取失敗",
                'sale_time': "提取失敗",
                'url': url
            }
            
    def scrape_activities(self):
        """爬取所有活動資訊"""
        try:
            self.setup_driver()
            
            # 首頁URL
            base_url = "https://tixcraft.com/activity"
            self.driver.get(base_url)
            
            # 等待頁面載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.thumbnails"))
            )
            
            # 獲取所有活動連結
            activity_links = []
            thumbnails = self.driver.find_elements(By.CSS_SELECTOR, "div.thumbnails a")
            
            for link in thumbnails:
                href = link.get_attribute('href')
                if href and 'activity/detail' in href:
                    activity_links.append(href)
            
            self.logger.info(f"找到 {len(activity_links)} 個活動")
            
            # 處理每個活動
            activities = []
            success_count = 0
            
            for index, url in enumerate(activity_links, 1):
                self.logger.info(f"處理進度：{index}/{len(activity_links)}")
                
                activity_data = self.extract_event_details(url)
                if activity_data:
                    activity_data['index'] = index
                    activities.append(activity_data)
                    
                    if activity_data['title'] != "錯誤":
                        success_count += 1
                        
                    # 輸出當前活動資訊
                    self.logger.info(f"活動 {index}：{activity_data['title']}")
                    self.logger.info(f"  日期：{activity_data['date']}")
                    self.logger.info(f"  時間：{activity_data['time']}")
                    self.logger.info(f"  地點：{activity_data['location']}")
                    self.logger.info(f"  票價：{activity_data['price']}")
                    self.logger.info(f"  售票時間：{activity_data['sale_time']}")
                
                # 間隔避免被偵測
                time.sleep(1)
            
            # 統計結果
            success_rate = (success_count / len(activities)) * 100 if activities else 0
            
            # 準備最終結果
            result = {
                'scrape_time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_events': len(activities),
                'success_count': success_count,
                'success_rate': f'{success_rate:.1f}%',
                'events': activities
            }
            
            # 儲存結果
            output_file = 'tixcraft_ultra_precision_results.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"爬取完成！成功處理 {success_count}/{len(activities)} 個活動")
            self.logger.info(f"成功率：{success_rate:.1f}%")
            self.logger.info(f"結果已儲存至：{output_file}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"爬取過程中發生錯誤：{e}")
            return None
        finally:
            if self.driver:
                self.driver.quit()

def main():
    scraper = TixcraftUltraPrecisionScraper()
    result = scraper.scrape_activities()
    
    if result:
        print(f"\n=== 爬取結果摘要 ===")
        print(f"爬取時間：{result['scrape_time']}")
        print(f"總活動數：{result['total_events']}")
        print(f"成功處理：{result['success_count']}")
        print(f"成功率：{result['success_rate']}")
        print(f"結果檔案：tixcraft_ultra_precision_results.json")
    else:
        print("爬取失敗，請檢查錯誤日誌")

if __name__ == "__main__":
    main()