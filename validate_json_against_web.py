#!/usr/bin/env python3
import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


IGNORE_VALUES = {"", "未找到", "提取失敗", "錯誤", "N/A", None}


def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_compare(text):
    text = normalize_text(text).lower()
    text = re.sub(r"[\s\u3000]", "", text)
    return text


def split_segments(value):
    if value in IGNORE_VALUES:
        return []
    segments = [normalize_text(s) for s in str(value).split(";")]
    return [s for s in segments if s and s not in IGNORE_VALUES]


def similarity(a, b):
    a_norm = normalize_for_compare(a)
    b_norm = normalize_for_compare(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    a_set = set(a_norm)
    b_set = set(b_norm)
    inter = len(a_set & b_set)
    union = len(a_set | b_set)
    if union == 0:
        return 0.0
    return inter / union


@dataclass
class FieldCheck:
    status: str
    reason: str
    matched: list
    candidates: list


def check_field(json_value, candidates, page_text):
    segments = split_segments(json_value)
    if not segments:
        if candidates:
            return FieldCheck(
                status="warning",
                reason="JSON為未找到，但網頁有可疑候選值",
                matched=[],
                candidates=candidates[:5],
            )
        return FieldCheck(status="ok", reason="JSON與網頁皆無明確值", matched=[], candidates=[])

    page_norm = normalize_for_compare(page_text)
    matched = []
    unmatched = []
    for seg in segments:
        seg_norm = normalize_for_compare(seg)
        direct_hit = seg_norm and seg_norm in page_norm
        candidate_hit = False
        for cand in candidates:
            if similarity(seg, cand) >= 0.68:
                candidate_hit = True
                break

        if direct_hit or candidate_hit:
            matched.append(seg)
        else:
            unmatched.append(seg)

    if not unmatched:
        return FieldCheck(status="ok", reason="欄位值可在網頁找到", matched=matched, candidates=candidates[:5])

    if matched:
        return FieldCheck(
            status="warning",
            reason=f"部分欄位片段無法在網頁找到：{unmatched[:2]}",
            matched=matched,
            candidates=candidates[:5],
        )

    return FieldCheck(
        status="mismatch",
        reason=f"欄位值與網頁內容不符：{unmatched[:2]}",
        matched=[],
        candidates=candidates[:5],
    )


def setup_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1366,768")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Runtime.evaluate",
        {"expression": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def wait_for_meaningful_page(driver, wait_sec):
    def has_meaningful_text(_):
        try:
            body_text = driver.find_element(By.TAG_NAME, "body").text
            return len(normalize_text(body_text)) >= 200
        except Exception:
            return False

    WebDriverWait(driver, wait_sec).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    WebDriverWait(driver, wait_sec).until(has_meaningful_text)


def extract_page_signals(driver):
    title_text = ""
    try:
        title_text = normalize_text(driver.find_element(By.ID, "synopsisEventTitle").text)
    except NoSuchElementException:
        try:
            title_text = normalize_text(driver.find_element(By.TAG_NAME, "h1").text)
        except NoSuchElementException:
            title_text = normalize_text(driver.title)

    intro_text = ""
    try:
        intro_text = normalize_text(driver.find_element(By.ID, "intro").text)
    except NoSuchElementException:
        intro_text = ""

    body_text = normalize_text(driver.find_element(By.TAG_NAME, "body").text)
    merged_text = "\n".join([t for t in [title_text, intro_text, body_text] if t])

    lines = [normalize_text(line) for line in merged_text.split("\n") if normalize_text(line)]

    location_candidates = []
    price_candidates = []
    sale_candidates = []
    event_info_candidates = []

    location_keywords = [
        "地點", "venue", "場地", "體育館", "巨蛋", "中心", "legacy", "zepp", "arena", "hall", "dome",
        "演出地點", "活動地點", "駁二", "新北市", "台北", "高雄", "台中", "台南", "新竹",
    ]
    sale_keywords = ["售票", "開賣", "預售", "啟售", "發售", "優先購", "on sale", "presale"]

    for line in lines:
        l_line = line.lower()

        if any(keyword in l_line for keyword in location_keywords):
            location_candidates.append(line)

        if re.search(r"nt\$\s?[\d,]+|[\d,]+\s*元|\$\s?[\d,]+", l_line):
            if any(k in l_line for k in ["票價", "price", "vip", "vvip", "票"]):
                price_candidates.append(line)

        if any(keyword in l_line for keyword in sale_keywords):
            if re.search(r"\d{4}[\./-]\d{1,2}[\./-]\d{1,2}|\d{1,2}:\d{2}|\d{1,2}月\d{1,2}日", l_line):
                sale_candidates.append(line)

        if re.search(r"\d{4}[\./-]\d{1,2}[\./-]\d{1,2}|\d{1,2}:\d{2}|\d{1,2}月\d{1,2}日", l_line):
            event_info_candidates.append(line)

    return {
        "page_title": title_text,
        "page_text": merged_text,
        "location_candidates": location_candidates[:20],
        "price_candidates": price_candidates[:20],
        "sale_candidates": sale_candidates[:20],
        "event_info_candidates": event_info_candidates[:20],
    }


def has_valid_signals(signals):
    page_title = normalize_text(signals.get("page_title", ""))
    page_text = normalize_text(signals.get("page_text", ""))
    candidate_total = sum(
        len(signals.get(key, []))
        for key in ["location_candidates", "price_candidates", "sale_candidates", "event_info_candidates"]
    )
    return bool(page_title) and len(page_text) >= 200 and candidate_total > 0


def validate_event(driver, event, wait_sec):
    url = event.get("url", "")
    result = {
        "index": event.get("index"),
        "title": event.get("title", ""),
        "url": url,
        "status": "ok",
        "errors": [],
        "warnings": [],
        "checks": {},
        "page_title": "",
    }

    signals = None
    last_error = None
    for attempt in range(3):
        try:
            driver.get(url)
            wait_for_meaningful_page(driver, wait_sec)
            time.sleep(0.6 + attempt * 0.6)
            signals = extract_page_signals(driver)
            if has_valid_signals(signals):
                break
        except TimeoutException:
            last_error = "頁面載入逾時或內容尚未完整呈現"
        except Exception as error:
            last_error = f"頁面載入失敗: {error}"

    if not signals or not has_valid_signals(signals):
        result["status"] = "mismatch"
        result["errors"].append(last_error or "頁面內容不足，重試後仍無法完成比對")
        return result

    result["page_title"] = signals["page_title"]

    field_map = {
        "event_info": signals["event_info_candidates"],
        "location": signals["location_candidates"],
        "price": signals["price_candidates"],
        "sale_time": signals["sale_candidates"],
    }

    for field_name, candidates in field_map.items():
        check = check_field(event.get(field_name), candidates, signals["page_text"])
        result["checks"][field_name] = {
            "status": check.status,
            "reason": check.reason,
            "matched": check.matched,
            "candidates": check.candidates,
            "json_value": event.get(field_name),
        }

        if check.status == "mismatch":
            result["errors"].append(f"{field_name}: {check.reason}")
        elif check.status == "warning":
            result["warnings"].append(f"{field_name}: {check.reason}")

    if result["errors"]:
        result["status"] = "mismatch"
    elif result["warnings"]:
        result["status"] = "warning"
    else:
        result["status"] = "ok"

    return result


def build_markdown_report(report_data, output_md):
    lines = []
    lines.append("# JSON 與網頁比對報告")
    lines.append("")
    lines.append(f"- 產生時間：{report_data['generated_at']}")
    lines.append(f"- 總活動數：{report_data['summary']['total']}")
    lines.append(f"- 完全一致：{report_data['summary']['ok']}")
    lines.append(f"- 警告：{report_data['summary']['warning']}")
    lines.append(f"- 不一致：{report_data['summary']['mismatch']}")
    lines.append("")

    if report_data["summary"]["warning"] == 0 and report_data["summary"]["mismatch"] == 0:
        lines.append("✅ 所有項目皆通過比對。")
    else:
        lines.append("## 需人工確認項目")
        lines.append("")
        for item in report_data["results"]:
            if item["status"] == "ok":
                continue
            lines.append(f"### #{item['index']} {item['title']}")
            lines.append(f"- URL: {item['url']}")
            if item["errors"]:
                for error in item["errors"]:
                    lines.append(f"- ❌ {error}")
            if item["warnings"]:
                for warning in item["warnings"]:
                    lines.append(f"- ⚠️ {warning}")
            lines.append("")

    with open(output_md, "w", encoding="utf-8") as file:
        file.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="比對 tixcraft_activities.json 與網頁內容")
    parser.add_argument("--input", default="tixcraft_activities.json", help="輸入 JSON 檔案")
    parser.add_argument("--limit", type=int, default=0, help="只比對前 N 筆，0 表示全部")
    parser.add_argument("--wait", type=int, default=12, help="每頁等待秒數")
    parser.add_argument("--sleep", type=float, default=0.2, help="每筆比對後額外等待秒數")
    parser.add_argument("--output-json", default="validation_report.json", help="輸出報告 JSON")
    parser.add_argument("--output-md", default="validation_report.md", help="輸出報告 Markdown")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as file:
        data = json.load(file)

    events = data.get("events", [])
    if args.limit and args.limit > 0:
        events = events[: args.limit]

    if not events:
        print("沒有可比對的活動資料")
        return

    print(f"開始比對：{len(events)} 筆活動")
    driver = setup_driver()
    results = []
    try:
        for idx, event in enumerate(events, 1):
            print(f"[{idx}/{len(events)}] 比對 {event.get('title', 'N/A')} ...")
            result = validate_event(driver, event, args.wait)
            results.append(result)
            time.sleep(args.sleep)
    finally:
        driver.quit()

    summary = {
        "total": len(results),
        "ok": sum(1 for item in results if item["status"] == "ok"),
        "warning": sum(1 for item in results if item["status"] == "warning"),
        "mismatch": sum(1 for item in results if item["status"] == "mismatch"),
    }

    report_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": args.input,
        "summary": summary,
        "results": results,
    }

    with open(args.output_json, "w", encoding="utf-8") as file:
        json.dump(report_data, file, ensure_ascii=False, indent=2)

    build_markdown_report(report_data, args.output_md)

    print("比對完成")
    print(f"- 完全一致: {summary['ok']}")
    print(f"- 警告: {summary['warning']}")
    print(f"- 不一致: {summary['mismatch']}")
    print(f"- JSON 報告: {args.output_json}")
    print(f"- Markdown 報告: {args.output_md}")


if __name__ == "__main__":
    main()
