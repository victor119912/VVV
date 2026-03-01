#!/usr/bin/env python3
import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="根據 validation_report 產生修正後預覽 JSON")
    parser.add_argument("--source", default="tixcraft_activities.json", help="原始活動 JSON")
    parser.add_argument("--report", default="validation_report.json", help="驗證報告 JSON")
    parser.add_argument("--output", default="tixcraft_activities_corrected_preview.json", help="輸出預覽 JSON")
    parser.add_argument("--apply-warning", action="store_true", help="是否連 warning 也套用候選值")
    args = parser.parse_args()

    with open(args.source, "r", encoding="utf-8") as file:
        source_data = json.load(file)
    with open(args.report, "r", encoding="utf-8") as file:
        report_data = json.load(file)

    events = source_data.get("events", [])
    by_url = {event.get("url"): event for event in events}

    fixed_count = 0
    field_fixed_count = {"event_info": 0, "location": 0, "price": 0, "sale_time": 0}

    for item in report_data.get("results", []):
        url = item.get("url")
        event = by_url.get(url)
        if not event:
            continue

        changed = False
        checks = item.get("checks", {})
        for field_name in ["event_info", "location", "price", "sale_time"]:
            check = checks.get(field_name, {})
            status = check.get("status")
            candidates = check.get("candidates", [])
            if not candidates:
                continue

            can_apply = status == "mismatch" or (args.apply_warning and status == "warning")
            if not can_apply:
                continue

            new_value = candidates[0]
            if new_value and event.get(field_name) != new_value:
                event[field_name] = new_value
                field_fixed_count[field_name] += 1
                changed = True

        if changed:
            fixed_count += 1

    with open(args.output, "w", encoding="utf-8") as file:
        json.dump(source_data, file, ensure_ascii=False, indent=2)

    print("預覽檔已產生")
    print(f"- 修正活動數: {fixed_count}")
    print(f"- event_info 修正: {field_fixed_count['event_info']}")
    print(f"- location 修正: {field_fixed_count['location']}")
    print(f"- price 修正: {field_fixed_count['price']}")
    print(f"- sale_time 修正: {field_fixed_count['sale_time']}")
    print(f"- 輸出檔案: {args.output}")


if __name__ == "__main__":
    main()
