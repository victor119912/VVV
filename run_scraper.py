from __future__ import annotations

import argparse
import json
import sys

from tixcraft_precision_field_scraper import main as run_precision_scraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Tixcraft activity scraper.")
    parser.add_argument("--limit", type=int, default=None, help="Only scrape the first N activity pages.")
    parser.add_argument(
        "--output",
        default="tixcraft_activities.json",
        help="Path to the output JSON file.",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Run Chrome with a visible window instead of headless mode.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    result = run_precision_scraper(
        limit=args.limit,
        output_path=args.output,
        headless=not args.visible,
    )
    print(json.dumps({"output": args.output, "total_events": result["total_events"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
