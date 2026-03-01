# Tixcraft 爬蟲專案

本專案已精簡為核心版本，保留主力爬蟲與監控工具。

## 快速開始

1. 建立並啟用虛擬環境（建議）
2. 安裝套件

```bash
pip install -r requirements.txt
```

3. 使用統一入口執行（預設：`precision-field`）

```bash
python run_scraper.py
```

4. 查看所有可用目標

```bash
python run_scraper.py --list
```

## 可用目標

- `precision-field`：目前最適合作為日常執行版本
- `monitor`：資料監控用途

## 主要檔案

- `run_scraper.py`：統一啟動入口
- `tixcraft_precision_field_scraper.py`：建議主版本
- `tixcraft_monitor.py`：監控工具
- `README_爬蟲使用說明.md`：欄位爬取細節說明

## 輸出與暫存

- `tixcraft_activities.json`：主要資料檔
- `.gitignore` 已加入常見快取、虛擬環境、暫存檔忽略規則

## 免責聲明

本專案僅供學習與研究用途，請務必遵守目標網站服務條款與相關法規。