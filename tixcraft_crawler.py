#!/usr/bin/env python3

# 導入 selenium 相關套件
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# 使用 webdriver_manager 自動下載 chromedriver
from webdriver_manager.chrome import ChromeDriverManager

import time
from datetime import datetime


def setup_chrome_driver():
    """設定 Chrome 瀏覽器參數並返回 webdriver"""
    chrome_options = Options()
    
    # 隱藏 "受到自動控制" 的提示字樣
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # 其他常用設定（可選）
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    # 自動下載 ChromeDriver
    service = Service(ChromeDriverManager().install())
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # 去除 webdriver 屬性，進一步隱藏自動化特徵
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver


def check_time_and_refresh(driver):
    """檢查現在時間，如果是 12:00:00 就重新整理頁面"""
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"當前時間：{current_time}")
    
    if current_time == "12:00:00":
        print("時間到了 12:00:00，正在重新整理頁面...")
        driver.refresh()
        return True
    return False


def find_and_click_buy_button(driver):
    """在頁面中尋找 ID 為 'gameListContainer' 裡的 '立即購票' 按鈕並點擊"""
    try:
        # 等待 gameListContainer 元素出現
        container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "gameListContainer"))
        )
        
        # 在 gameListContainer 中尋找 "立即購票" 按鈕
        # 可能的按鈕選擇器（根據實際網頁結構調整）
        buy_button_selectors = [
            "//button[contains(text(), '立即購票')]",
            "//a[contains(text(), '立即購票')]",
            "//input[@value='立即購票']",
            "//*[contains(@class, 'btn') and contains(text(), '立即購票')]"
        ]
        
        for selector in buy_button_selectors:
            try:
                buy_button = container.find_element(By.XPATH, f".{selector}")
                if buy_button.is_displayed() and buy_button.is_enabled():
                    print("找到 '立即購票' 按鈕，正在點擊...")
                    driver.execute_script("arguments[0].click();", buy_button)
                    return True
            except NoSuchElementException:
                continue
        
        print("在 gameListContainer 中未找到可用的 '立即購票' 按鈕")
        return False
        
    except TimeoutException:
        print("未找到 gameListContainer 元素")
        return False
    except Exception as e:
        print(f"尋找購票按鈕時發生錯誤：{e}")
        return False


def main():
    """主程式"""
    driver = None
    
    try:
        # 設定並啟動瀏覽器
        print("正在啟動 Chrome 瀏覽器...")
        driver = setup_chrome_driver()
        
        # 前往目標網址
        target_url = "https://tixcraft.com/activity/detail/26_kamenashi"
        print(f"正在前往網址：{target_url}")
        driver.get(target_url)
        
        print("頁面載入完成，開始監控...")
        
        # 主要監控迴圈
        while True:
            # 檢查時間並刷新頁面
            if check_time_and_refresh(driver):
                time.sleep(2)  # 等待頁面載入
            
            # 嘗試尋找並點擊購票按鈕
            if find_and_click_buy_button(driver):
                print("成功點擊 '立即購票' 按鈕！")
                break
            
            # 等待1秒後繼續檢查
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n程式被使用者中斷")
    except Exception as e:
        print(f"程式執行時發生錯誤：{e}")
    finally:
        if driver:
            print("正在關閉瀏覽器...")
            driver.quit()


if __name__ == "__main__":
    main()