# Tixcraft Scraper

這個專案目前只保留「抓取 Tixcraft 活動資料」會用到的檔案。

## 保留的檔案

- `run_scraper.py`
  - 入口指令，負責接收參數並執行爬蟲。
- `tixcraft_precision_field_scraper.py`
  - 主爬蟲邏輯，只輸出需要的欄位。
- `requirements.txt`
  - 執行所需套件。
- `tixcraft_activities.json`
  - 目前主輸出檔。
- `.gitignore`
  - 忽略 log、快取和臨時輸出。

## 安裝

```bash
pip install -r requirements.txt
```

## 執行

抓完整活動列表：

```bash
python run_scraper.py
```

只抓前 10 筆：

```bash
python run_scraper.py --limit 10
```

指定輸出檔：

```bash
python run_scraper.py --output custom_output.json
```

顯示瀏覽器視窗執行：

```bash
python run_scraper.py --visible
```

## 輸出欄位

每筆活動只會保留以下欄位，有資料才會寫入：

- `event_name`
- `ticket_price`
- `ticket_types`
- `event_time`
- `sale_time`
- `event_link`
- `venue_name`
- `address`
- `artist_name`
