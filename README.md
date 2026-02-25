# Tixcraft 爬蟲程式

這是一個用於 Tixcraft 售票網站的自動化爬蟲程式。

## 功能特色

- 自動下載並管理 ChromeDriver
- 隱藏瀏覽器自動化控制提示
- 自動檢查時間，在指定時間（12:00:00）重新整理頁面
- 自動尋找並點擊「立即購票」按鈕

## 安裝需求

請確保您的電腦已安裝 Python 3.6 或更高版本。

### 安裝依賴套件

在命令提示字元或 PowerShell 中執行：

```bash
pip install -r requirements.txt
```

## 使用方法

在命令提示字元或 PowerShell 中執行：

```bash
python tixcraft_crawler.py
```

## 程式說明

### 主要函數

1. `setup_chrome_driver()` - 設定 Chrome 瀏覽器參數
2. `check_time_and_refresh(driver)` - 檢查時間並在 12:00:00 時重新整理頁面
3. `find_and_click_buy_button(driver)` - 尋找並點擊購票按鈕

### 注意事項

- 程式會自動前往指定的 Tixcraft 活動頁面
- 每秒檢查一次是否有購票按鈕出現
- 在 12:00:00 時會自動重新整理頁面
- 按 Ctrl+C 可以中斷程式執行

## 免責聲明

此程式僅供學習和研究目的使用。使用者需要遵守網站的使用條款和相關法律規定。