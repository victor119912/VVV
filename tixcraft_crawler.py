#!/usr/bin/env python3
"""
Tixcraft 自動搶票腳本 - 完整版
作者: Assistant
日期: 2026-02-25
功能: 自動爬取演出資訊、網路時間同步、防偵測自動購票
"""

import ntplib
from time import sleep
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager


class TixcraftBot:
    """Tixcraft 自動搶票機器人"""
    
    def __init__(self, target_url, target_datetime):
        self.target_url = target_url
        self.target_time = target_datetime.timestamp()
        self.driver = self._setup_driver()
    
    def _setup_driver(self):
        """配置並初始化 Chrome 瀏覽器（防偵測版）"""
        options = Options()
        
        # === 防偵測核心設定 ===
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 效能與穩定性設定
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument("--disable-gpu")
        
        # 初始化 WebDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # === CDP 指令隱藏 webdriver 屬性 ===
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        
        return driver
    
    def get_network_time(self):
        """獲取 NTP 網路標準時間"""
        try:
            client = ntplib.NTPClient()
            response = client.request('pool.ntp.org', version=3)
            return response.tx_time
        except Exception as e:
            print(f"NTP 時間同步失敗，使用本機時間: {e}")
            return datetime.now().timestamp()
    
    def scrape_event_info(self):
        """爬取並顯示演出基本資訊"""
        print("\n🎭 正在爬取演出資訊...")
        try:
            # 等待頁面載入完成
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # === 爬取演出標題 ===
            try:
                title_element = self.driver.find_element(By.ID, "synopsisEventTitle")
                event_title = title_element.text.strip()
                print(f"📌 演出項目：{event_title}")
            except NoSuchElementException:
                print("⚠️ 無法取得演出標題")
            
            # === 爬取詳細資訊 (intro 區塊) ===
            try:
                intro_section = self.driver.find_element(By.ID, "intro")
                intro_text = intro_section.text
                
                print("📋 演出詳細資訊：")
                print("-" * 50)
                
                # 解析並格式化 intro 內容
                lines = intro_text.split('\n')
                for line in lines:
                    if line.strip():
                        if '日期' in line or '時間' in line:
                            print(f"📅 {line}")
                        elif '地點' in line or '場地' in line:
                            print(f"📍 {line}")
                        elif '票價' in line or '價格' in line or '$' in line:
                            print(f"💰 {line}")
                        else:
                            print(f"ℹ️  {line}")
                            
                print("-" * 50)
                
            except NoSuchElementException:
                print("⚠️ 無法取得 intro 區塊資訊")
            
        except TimeoutException:
            print("⚠️ 頁面載入超時，跳過資訊爬取")
    
    def click_buy_button(self):
        """智能搜尋並點擊購票按鈕"""
        try:
            wait = WebDriverWait(self.driver, 0.5)
            
            # === 多重購票按鈕選擇器 ===
            selectors = [
                "//a[contains(text(), '立即購票')]",
                "//button[contains(text(), '立即購票')]", 
                "//input[@value='立即購票']",
                "//*[contains(@class, 'btn') and contains(text(), '立即購票')]",
                "//a[contains(@href, 'buy')]",
                "//*[@id='gameListContainer']//a[contains(text(), '立即購票')]",
                "//a[contains(text(), '購票')]",
                "//*[contains(@class, 'buy-btn')]"
            ]
            
            for selector in selectors:
                try:
                    buy_btn = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    # 使用 JavaScript 點擊避免被攔截
                    self.driver.execute_script("arguments[0].click();", buy_btn)
                    return True
                except:
                    continue
                    
            return False
            
        except Exception:
            return False
    
    def countdown_timer(self):
        """智能倒數計時與搶票執行"""
        print("\n⏰ 開始時間監控...")
        
        while True:
            current_time = self.get_network_time()
            remaining = self.target_time - current_time
            
            if remaining <= 0.5:
                # === 搶票衝刺階段 ===
                print("🚀 時間到！開始搶票衝刺...")
                self.driver.refresh()
                sleep(0.3)  # 等待頁面重載
                
                # 連續嘗試點擊購票按鈕
                success = False
                for attempt in range(100):  # 最多嘗試100次
                    if self.click_buy_button():
                        print(f"✅ 搶票成功！耗時 {attempt + 1} 次嘗試")
                        success = True
                        break
                    sleep(0.05)  # 極短間隔重試
                
                if not success:
                    print("❌ 搶票失敗：未找到可用的購票按鈕")
                
                break
                
            elif remaining > 5:
                # === 遠距離監控階段 ===
                minutes, seconds = divmod(int(remaining), 60)
                hours, minutes = divmod(minutes, 60)
                if hours > 0:
                    print(f"⏳ 距離開賣還有 {hours}:{minutes:02d}:{seconds:02d}")
                else:
                    print(f"⏳ 距離開賣還有 {minutes}:{seconds:02d}")
                sleep(1)  # 每秒更新一次
                
            else:
                # === 高精度準備階段 ===
                print(f"🎯 倒數 {remaining:.2f} 秒，高精度準備中...")
                sleep(0.1)  # 高頻率檢測
    
    def run(self):
        """執行完整搶票流程"""
        try:
            print("🌐 正在載入目標頁面...")
            self.driver.get(self.target_url)
            
            # === 資訊爬取階段 ===
            self.scrape_event_info()
            
            # === 手動登入時間 ===
            print(f"\n🔐 您有 30 秒時間完成登入（Google/Facebook 等）")
            print("請在新開啟的瀏覽器視窗中完成登入程序...")
            for i in range(30, 0, -1):
                print(f"⏰ 剩餘 {i} 秒...", end='\r')
                sleep(1)
            print("\n✅ 登入時間結束，開始自動監控")
            
            # === 倒數計時與搶票 ===
            self.countdown_timer()
            
            # === 搶票完成後暫停 ===
            print("\n🎉 搶票程序完成！瀏覽器將保持開啟...")
            print("請手動完成後續購票流程（選位、付款等）")
            input("按 Enter 鍵關閉程式...")
            
        except KeyboardInterrupt:
            print("\n⚠️ 程式被使用者中斷")
        except Exception as e:
            print(f"❌ 執行錯誤：{e}")
        finally:
            print("🔚 正在關閉瀏覽器...")
            self.driver.quit()


def main():
    """主程式進入點"""
    # === 設定目標參數 ===
    TARGET_URL = "https://tixcraft.com/activity/detail/26_kamenashi"
    TARGET_DATETIME = datetime(2026, 3, 7, 12, 0, 0)  # 2026-03-07 12:00:00
    
    print("=" * 60)
    print("🎪 Tixcraft 自動搶票腳本 v2.0")
    print("=" * 60)
    print(f"🎯 目標網址：{TARGET_URL}")
    print(f"⏰ 搶票時間：{TARGET_DATETIME.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # === 初始化並執行搶票機器人 ===
    bot = TixcraftBot(TARGET_URL, TARGET_DATETIME)
    bot.run()


if __name__ == "__main__":
    main()