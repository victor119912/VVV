#!/usr/bin/env python3
"""
拓元售票網活動監控爬蟲
功能：自動監控活動列表頁，追蹤新演出並抓取詳細資訊
作者: Assistant
日期: 2026-02-25
"""

import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import os


class TixcraftMonitor:
    """拓元售票網活動監控系統"""
    
    def __init__(self, check_interval=600):  # 預設10分鐘檢查一次
        self.check_interval = check_interval
        self.base_url = "https://tixcraft.com/activity"
        self.data_file = "tixcraft_activities.json"
        self.driver = None
        self.activities_data = self.load_activities_data()
        
    def setup_driver(self):
        """設定防偵測瀏覽器"""
        if self.driver:
            return self.driver
            
        print("🔧 正在設定瀏覽器...")
        options = Options()
        
        # 防偵測設定
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # 靜音模式（可選）
        # options.add_argument("--headless")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # 去除 webdriver 屬性
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return self.driver

    def load_activities_data(self):
        """載入本地活動資料"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"📂 載入本地資料：{len(data)} 個活動")
                    return data
            except Exception as e:
                print(f"⚠️ 載入資料檔案失敗：{e}")
        
        print("📝 建立新的活動追蹤清單")
        return {}

    def save_activities_data(self):
        """儲存活動資料到本地檔案"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.activities_data, f, ensure_ascii=False, indent=2)
            print(f"💾 已儲存 {len(self.activities_data)} 個活動資料")
        except Exception as e:
            print(f"❌ 儲存資料失敗：{e}")

    def scrape_activity_list(self):
        """抓取活動列表頁的所有活動"""
        try:
            print("🌐 正在前往活動列表頁...")
            self.driver.get(self.base_url)
            
            # 等待頁面載入
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # 額外等待 JavaScript 載入
            
            activities = []
            
            # 多種可能的活動容器選擇器
            container_selectors = [
                "div.thumbnails",
                ".activity-list", 
                ".event-list",
                ".row .col-md-4",
                ".activity-item"
            ]
            
            activity_elements = []
            
            # 嘗試找到活動容器
            for selector in container_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        print(f"✅ 找到活動容器：{selector} ({len(elements)} 個元素)")
                        activity_elements = elements
                        break
                except:
                    continue
            
            # 如果沒有找到特定容器，嘗試查找包含連結的活動
            if not activity_elements:
                print("🔍 嘗試查找活動連結...")
                activity_elements = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/activity/detail/']")
                print(f"📋 找到 {len(activity_elements)} 個活動連結")
            
            # 解析每個活動
            for element in activity_elements[:20]:  # 限制前20個避免過載
                try:
                    activity_info = self.parse_activity_element(element)
                    if activity_info:
                        activities.append(activity_info)
                except Exception as e:
                    print(f"⚠️ 解析活動元素失敗：{e}")
                    continue
            
            print(f"📊 成功抓取 {len(activities)} 個活動")
            return activities
            
        except TimeoutException:
            print("❌ 頁面載入超時")
            return []
        except Exception as e:
            print(f"❌ 抓取活動列表失敗：{e}")
            return []

    def parse_activity_element(self, element):
        """解析單個活動元素"""
        try:
            # 嘗試找活動連結
            link_element = element
            if element.tag_name != 'a':
                link_element = element.find_element(By.CSS_SELECTOR, "a[href*='/activity/detail/']")
            
            # 獲取活動連結
            activity_url = link_element.get_attribute('href')
            if not activity_url or '/activity/detail/' not in activity_url:
                return None
            
            # 獲取活動 ID
            activity_id = activity_url.split('/activity/detail/')[-1].split('?')[0]
            
            # 嘗試獲取活動名稱
            activity_name = ""
            name_selectors = [
                "img[alt]", 
                ".title", 
                "h3", 
                "h4",
                ".card-title",
                ".activity-name"
            ]
            
            for selector in name_selectors:
                try:
                    name_elem = element.find_element(By.CSS_SELECTOR, selector)
                    if selector == "img[alt]":
                        activity_name = name_elem.get_attribute('alt')
                    else:
                        activity_name = name_elem.text.strip()
                    
                    if activity_name:
                        break
                except:
                    continue
            
            # 如果還是沒有名稱，使用 activity_id
            if not activity_name:
                activity_name = f"活動_{activity_id}"
            
            # 嘗試獲取狀態
            status = "未知狀態"
            status_selectors = [
                ".status",
                ".sale-status", 
                ".btn",
                ".badge"
            ]
            
            for selector in status_selectors:
                try:
                    status_elem = element.find_element(By.CSS_SELECTOR, selector)
                    status_text = status_elem.text.strip()
                    if status_text and len(status_text) < 20:
                        status = status_text
                        break
                except:
                    continue
            
            return {
                'id': activity_id,
                'name': activity_name,
                'url': activity_url,
                'status': status,
                'found_time': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"⚠️ 解析活動元素時發生錯誤：{e}")
            return None

    def scrape_activity_details(self, activity_url):
        """抓取活動詳細資訊"""
        try:
            print(f"🔍 正在抓取活動詳情：{activity_url}")
            self.driver.get(activity_url)
            
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)
            
            details = {
                'title': '',
                'date': '',
                'time': '',
                'venue': '',
                'prices': [],
                'sale_time': ''
            }
            
            # 抓取標題
            try:
                title_elem = self.driver.find_element(By.ID, "synopsisEventTitle")
                details['title'] = title_elem.text.strip()
            except:
                pass
            
            # 抓取詳細資訊
            try:
                intro_elem = self.driver.find_element(By.ID, "intro")
                intro_text = intro_elem.text
                
                # 解析 intro 內容
                lines = intro_text.split('\n')
                for line in lines:
                    line = line.strip()
                    if '演出日期' in line:
                        details['date'] = line.replace('演出日期｜', '').replace('演出日期：', '')
                    elif '演出時間' in line:
                        details['time'] = line.replace('演出時間｜', '').replace('演出時間：', '')
                    elif '演出地點' in line or '場地' in line:
                        details['venue'] = line.replace('演出地點｜', '').replace('演出地點：', '')
                    elif 'NT$' in line and '元' in line:
                        details['prices'].append(line)
                    elif '售票時間' in line:
                        details['sale_time'] = line.replace('售票時間｜', '').replace('售票時間：', '')
            except:
                pass
            
            return details
            
        except Exception as e:
            print(f"❌ 抓取活動詳情失敗：{e}")
            return None

    def process_activities(self, current_activities):
        """處理活動列表，比對新舊資料"""
        new_activities = []
        updated_activities = []
        
        # 檢查新活動
        for activity in current_activities:
            activity_id = activity['id']
            
            if activity_id not in self.activities_data:
                # 發現新活動
                print(f"🆕 偵測到新演出！正在抓取內容...")
                print(f"   📋 活動名稱：{activity['name']}")
                print(f"   🔗 活動連結：{activity['url']}")
                
                # 抓取詳細資訊
                details = self.scrape_activity_details(activity['url'])
                if details:
                    activity.update(details)
                
                self.activities_data[activity_id] = activity
                new_activities.append(activity)
                
            else:
                # 更新既有活動狀態
                old_status = self.activities_data[activity_id].get('status', '')
                if old_status != activity['status']:
                    print(f"🔄 活動狀態更新：{activity['name']} ({old_status} → {activity['status']})")
                    updated_activities.append(activity)
                
                self.activities_data[activity_id].update(activity)
        
        # 標記不再出現的活動
        current_ids = {act['id'] for act in current_activities}
        for activity_id, activity_data in self.activities_data.items():
            if activity_id not in current_ids and activity_data.get('status') != '已結束':
                print(f"⚠️ 活動不再出現，標記為已結束：{activity_data.get('name', activity_id)}")
                self.activities_data[activity_id]['status'] = '已結束'
                self.activities_data[activity_id]['ended_time'] = datetime.now().isoformat()
        
        return new_activities, updated_activities

    def display_activities_summary(self):
        """顯示活動清單摘要"""
        print("\n" + "="*80)
        print("📋 拓元活動監控清單")
        print("="*80)
        
        active_activities = [act for act in self.activities_data.values() if act.get('status') != '已結束']
        ended_activities = [act for act in self.activities_data.values() if act.get('status') == '已結束']
        
        print(f"🎪 進行中活動：{len(active_activities)} 個")
        for i, activity in enumerate(active_activities[:10], 1):  # 只顯示前10個
            print(f"   {i:2d}. {activity.get('name', '未知活動')[:50]}")
            print(f"       📅 {activity.get('date', '')} {activity.get('time', '')}")
            print(f"       📍 {activity.get('venue', '')}")
            print(f"       🎫 {activity.get('status', '')}")
            print()
        
        if ended_activities:
            print(f"🏁 已結束活動：{len(ended_activities)} 個")
            
        print(f"📊 總計追蹤：{len(self.activities_data)} 個活動")
        print(f"⏰ 最後更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)

    def monitor_loop(self):
        """主監控迴圈"""
        print("🚀 拓元活動監控系統啟動")
        print(f"🔄 檢查間隔：{self.check_interval//60} 分鐘")
        print("="*60)
        
        iteration = 0
        
        try:
            # 初始化瀏覽器
            self.setup_driver()
            
            while True:
                iteration += 1
                print(f"\n🔍 第 {iteration} 次掃描 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                
                try:
                    # 抓取當前活動列表
                    current_activities = self.scrape_activity_list()
                    
                    if current_activities:
                        # 處理新舊活動比對
                        new_activities, updated_activities = self.process_activities(current_activities)
                        
                        # 儲存更新的資料
                        self.save_activities_data()
                        
                        # 顯示摘要
                        self.display_activities_summary()
                        
                        if new_activities:
                            print(f"✨ 本次發現 {len(new_activities)} 個新活動")
                        
                        if updated_activities:
                            print(f"🔄 本次更新 {len(updated_activities)} 個活動狀態")
                            
                    else:
                        print("⚠️ 未能抓取到活動資料，將在下次檢查時重試")
                
                except Exception as e:
                    print(f"❌ 掃描過程發生錯誤：{e}")
                
                # 等待下次檢查
                print(f"\n⏳ 等待 {self.check_interval//60} 分鐘後進行下次掃描...")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n⚠️ 監控系統被使用者中斷")
        except Exception as e:
            print(f"❌ 監控系統發生錯誤：{e}")
        finally:
            if self.driver:
                print("🔚 正在關閉瀏覽器...")
                self.driver.quit()
                print("✅ 瀏覽器已關閉")

    def run_single_scan(self):
        """執行單次掃描（測試用）"""
        print("🔍 執行單次活動掃描...")
        
        try:
            self.setup_driver()
            current_activities = self.scrape_activity_list()
            
            if current_activities:
                new_activities, updated_activities = self.process_activities(current_activities)
                self.save_activities_data()
                self.display_activities_summary()
                
                print(f"✅ 掃描完成：發現 {len(current_activities)} 個活動")
            else:
                print("⚠️ 未能抓取到活動資料")
                
        except Exception as e:
            print(f"❌ 掃描失敗：{e}")
        finally:
            if self.driver:
                self.driver.quit()


def main():
    """主程式"""
    monitor = TixcraftMonitor(check_interval=600)  # 10分鐘間隔
    
    print("🎭 拓元售票網活動監控爬蟲")
    print("="*60)
    print("選擇執行模式：")
    print("1. 持續監控模式（每10分鐘檢查一次）")
    print("2. 單次掃描模式（測試用）")
    
    try:
        choice = input("\n請選擇 (1/2): ").strip()
        
        if choice == "1":
            monitor.monitor_loop()
        elif choice == "2":
            monitor.run_single_scan()
        else:
            print("無效選擇，執行單次掃描...")
            monitor.run_single_scan()
            
    except KeyboardInterrupt:
        print("\n程式被中斷")
    except Exception as e:
        print(f"執行錯誤：{e}")


if __name__ == "__main__":
    main()