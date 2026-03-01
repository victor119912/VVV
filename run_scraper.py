#!/usr/bin/env python3
"""統一啟動入口：用一個指令啟動不同爬蟲版本。"""

from __future__ import annotations

import argparse
import importlib
import sys


SCRIPT_MAP: dict[str, tuple[str, str]] = {
    "precision-field": ("tixcraft_precision_field_scraper", "精準欄位版（建議）"),
    "monitor": ("tixcraft_monitor", "監控工具"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tixcraft 專案統一啟動器",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=sorted(SCRIPT_MAP.keys()),
        default="precision-field",
        help=(
            "要執行的目標腳本（預設: precision-field）\n\n"
            + "可選項目：\n"
            + "\n".join(
                f"  - {key:17s} {desc}" for key, (_, desc) in sorted(SCRIPT_MAP.items())
            )
        ),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="只列出可執行目標，不實際執行",
    )
    return parser


def list_targets() -> None:
    print("可執行目標：")
    for key, (module_name, desc) in sorted(SCRIPT_MAP.items()):
        print(f"- {key:17s} {module_name:35s} {desc}")


def run_target(target: str) -> int:
    module_name, desc = SCRIPT_MAP[target]
    print(f"🚀 啟動目標：{target} ({desc})")
    try:
        module = importlib.import_module(module_name)
    except Exception as error:
        print(f"❌ 無法載入模組 {module_name}: {error}")
        return 1

    main_func = getattr(module, "main", None)
    if not callable(main_func):
        print(f"❌ 模組 {module_name} 沒有可呼叫的 main()")
        return 1

    try:
        main_func()
    except KeyboardInterrupt:
        print("\n⚠️ 使用者中斷執行")
        return 130
    except Exception as error:
        print(f"❌ 執行失敗: {error}")
        return 1

    return 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        list_targets()
        return 0

    return run_target(args.target)


if __name__ == "__main__":
    sys.exit(main())
