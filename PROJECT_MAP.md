# 專案整理地圖

## 1) 目前保留核心

- `run_scraper.py`：統一入口（先用這支）
- `tixcraft_precision_field_scraper.py`：主力爬蟲（`run_scraper.py` 預設會跑）
- `tixcraft_monitor.py`：監控 `tixcraft_activities.json`

## 2) 資料輸出檔

- `tixcraft_activities.json`

## 3) 使用方式

1. 平常只記這兩個指令：
   - `python run_scraper.py`
   - `python run_scraper.py --list`
2. 目前可執行目標只保留：
   - `precision-field`
   - `monitor`
