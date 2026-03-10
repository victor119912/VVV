from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


HOME_URL = "https://tixcraft.com/activity"
DETAIL_LINK_PATTERN = "/activity/detail/"
MONEY_RE = re.compile(r"(?:NT\$|\$)\s*[\d,]+(?:\s*元)?|[\d,]{3,}\s*元")
DATE_RE = re.compile(
    r"\d{4}[./-]\d{1,2}[./-]\d{1,2}|\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?|\d{1,2}:\d{2}"
)
ADDRESS_RE = re.compile(r"(?:市|縣|區|鄉|鎮|里|路|街|段|巷|弄|號|樓)")
PLACEHOLDERS = {"", "未找到", "提取失敗", "N/A"}
DECORATION_RE = re.compile(r"^[\s•▪※◆◇★☆▶►▸👉🎫📍⏰🎭💎❋❖❗️‼️\-]+")
GENERIC_ARTIST_KEYWORDS = ("festival", "音樂祭", "音樂節", "博覽會", "展覽")
VENUE_KEYWORDS = (
    "巨蛋",
    "小巨蛋",
    "流行音樂中心",
    "體育館",
    "展覽中心",
    "Legacy",
    "Zepp",
    "Arena",
    "Hall",
    "Stadium",
    "Dome",
    "劇院",
    "中心",
)


@dataclass
class ScraperConfig:
    output_path: Path = Path("tixcraft_activities.json")
    limit: int | None = None
    headless: bool = True
    timeout_seconds: int = 20
    settle_seconds: float = 4.0


class TixcraftPrecisionFieldScraper:
    def __init__(self, config: ScraperConfig | None = None):
        self.config = config or ScraperConfig()
        self.logger = self._build_logger()
        self.driver: webdriver.Chrome | None = None

    def _build_logger(self) -> logging.Logger:
        logger = logging.getLogger("tixcraft_precision_field_scraper")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()

        log_path = Path(__file__).with_name("tixcraft_precision_field.log")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        return logger

    def _build_driver(self) -> webdriver.Chrome:
        options = Options()
        if self.config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1440,1400")
        options.add_argument("--lang=zh-TW")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        )
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'languages', {get: () => ['zh-TW', 'zh', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                window.chrome = { runtime: {} };
                """,
            },
        )
        return driver

    def _ensure_driver(self) -> webdriver.Chrome:
        if self.driver is None:
            self.driver = self._build_driver()
        return self.driver

    def close(self) -> None:
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _wait_for_page_ready(self, driver: webdriver.Chrome) -> None:
        WebDriverWait(driver, self.config.timeout_seconds).until(
            lambda current: current.execute_script("return document.readyState") == "complete"
        )
        time.sleep(self.config.settle_seconds)

    def _load_listing_page(self) -> list[str]:
        driver = self._ensure_driver()
        driver.get(HOME_URL)
        self._wait_for_page_ready(driver)
        WebDriverWait(driver, self.config.timeout_seconds).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.thumbnails a"))
        )

        links = driver.execute_script(
            """
            return [...document.querySelectorAll('div.thumbnails a[href*="/activity/detail/"]')]
                .map((node) => node.href)
                .filter(Boolean);
            """
        )

        unique_links: list[str] = []
        seen: set[str] = set()
        for link in links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        if self.config.limit:
            unique_links = unique_links[: self.config.limit]

        self.logger.info("活動列表載入完成，共 %s 筆", len(unique_links))
        return unique_links

    def _fetch_payload(self, url: str) -> dict[str, Any]:
        driver = self._ensure_driver()
        driver.get(url)
        self._wait_for_page_ready(driver)
        WebDriverWait(driver, self.config.timeout_seconds).until(
            lambda current: current.execute_script(
                "return Boolean(document.querySelector('#synopsisEventTitle') || document.querySelector('#intro'));"
            )
        )

        payload = driver.execute_script(
            """
            const q = (selector) => document.querySelector(selector)?.innerText || '';
            const detail = Array.isArray(window.dataLayer)
                ? window.dataLayer.find((item) => item && item.event === 'EnterActivityDetail') || {}
                : {};
            return {
                title: q('#synopsisEventTitle'),
                intro: q('#intro'),
                pageTitle: document.title || '',
                dataLayer: detail,
                currentUrl: window.location.href
            };
            """
        )
        return payload

    def _clean_text(self, text: str | None) -> str:
        if not text:
            return ""
        cleaned = text.replace("\u00a0", " ").replace("\u3000", " ").replace("\ufeff", "")
        cleaned = DECORATION_RE.sub("", cleaned.strip())
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\s*\n\s*", "\n", cleaned)
        return cleaned.strip()

    def _normalize_value(self, value: str | None) -> str | None:
        cleaned = self._clean_text(value)
        if not cleaned or cleaned in PLACEHOLDERS:
            return None
        return cleaned

    def _split_intro_lines(self, intro: str) -> list[str]:
        lines: list[str] = []
        for raw_line in intro.splitlines():
            line = self._clean_text(raw_line)
            if not line:
                continue
            if "示意圖僅供參考示意" in line:
                continue
            lines.append(line)
        return lines

    def _match_label(self, line: str) -> tuple[str | None, str]:
        patterns = {
            "event_time": (
                r"^(?:演出時間|活動時間|活動日期|演出日期|日期|Date)\s*[：:]\s*(.*)$",
                r"^(?:加場)\s*[：:]\s*(.*)$",
            ),
            "sale_time": (
                r"^(?:售票時間|售票日期|開賣時間|開賣日期|一般售票日期|一般售票|會員售票時間|"
                r"會員抽選登記|會員抽選結果|官方預售開賣時間|普通銷售開賣時間|"
                r"Ticket Sales Schedule|Ticket Open|Public on sale|Presale|Pre-sale)\s*[：:]\s*(.*)$",
            ),
            "price": (
                r"^(?:演出票價|活動票價|票價|票　　價|Ticket Prices|Ticket Price|PRICE|Price)\s*[：:]\s*(.*)$",
            ),
            "location": (
                r"^(?:演出地點|活動地點|地點|會場|Venue|VENUE|Location|地址)\s*[：:]\s*(.*)$",
            ),
        }

        for field, field_patterns in patterns.items():
            for pattern in field_patterns:
                match = re.match(pattern, line, flags=re.IGNORECASE)
                if match:
                    return field, self._clean_text(match.group(1))
        return None, line

    def _is_continuation(self, field: str, line: str) -> bool:
        if "http" in line.lower():
            return False
        if field == "event_time":
            return bool(DATE_RE.search(line)) and "售票" not in line
        if field == "sale_time":
            return bool(DATE_RE.search(line)) or any(
                token in line.lower()
                for token in ("預售", "售票", "開賣", "presale", "sale", "會員")
            )
        if field == "price":
            return bool(MONEY_RE.search(line)) and "服務費" not in line
        if field == "location":
            return not bool(MONEY_RE.search(line)) and "售票" not in line and len(line) <= 80
        return False

    def _extract_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections = {
            "event_time": [],
            "sale_time": [],
            "price": [],
            "location": [],
        }
        current_field: str | None = None

        for line in lines:
            field, content = self._match_label(line)
            if field:
                current_field = field
                if content:
                    sections[field].append(content)
                continue
            if current_field and self._is_continuation(current_field, line):
                sections[current_field].append(line)
            else:
                current_field = None

        return {field: self._dedupe(values) for field, values in sections.items()}

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            normalized = self._clean_text(value)
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(normalized)
        return unique

    def _strip_field_prefix(self, text: str) -> str:
        stripped = re.sub(
            r"^(?:演出時間|活動時間|活動日期|演出日期|日期|售票時間|售票日期|開賣時間|開賣日期|"
            r"一般售票日期|一般售票|會員售票時間|會員抽選登記|會員抽選結果|官方預售開賣時間|"
            r"普通銷售開賣時間|演出票價|活動票價|票價|票　　價|演出地點|活動地點|地點|會場|"
            r"Venue|VENUE|Location|地址|Date|Ticket Sales Schedule|Ticket Open|Public on sale|"
            r"Presale|Pre-sale|Ticket Prices|Ticket Price|PRICE|Price|加場)\s*[：:]\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return self._clean_text(stripped)

    def _format_time_field(self, values: list[str], sale_mode: bool = False) -> str | None:
        normalized: list[str] = []
        for value in values:
            cleaned = self._strip_field_prefix(value)
            if not cleaned:
                continue
            if sale_mode and not (
                DATE_RE.search(cleaned)
                or any(token in cleaned.lower() for token in ("預售", "售票", "開賣", "presale", "sale"))
            ):
                continue
            if not sale_mode and not DATE_RE.search(cleaned):
                continue
            normalized.append(cleaned)
        normalized = self._dedupe(normalized)
        return " / ".join(normalized) if normalized else None

    def _normalize_price(self, raw_price: str) -> str:
        digits_match = re.search(r"[\d,]+", raw_price)
        if not digits_match:
            return self._clean_text(raw_price)
        digits = digits_match.group()
        if "$" in raw_price or "NT$" in raw_price.upper():
            return f"NT${digits}"
        if "元" in raw_price:
            return f"{digits}元"
        return digits

    def _cleanup_ticket_type(self, raw_type: str) -> str | None:
        cleaned = self._clean_text(raw_type)
        cleaned = re.sub(r"[（(].*?[)）]", "", cleaned)
        cleaned = re.sub(
            r"^(?:演出票價|活動票價|票價|票　　價|Ticket Prices|Ticket Price|PRICE|Price)\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip(" :：-/")
        if not cleaned or len(cleaned) > 24:
            return None
        return cleaned

    def _parse_ticket_entries(self, line: str) -> list[tuple[str | None, str]]:
        segments = re.split(r"[／/;｜|]+", line)
        entries: list[tuple[str | None, str]] = []

        for segment in segments:
            cleaned = self._strip_field_prefix(segment)
            if not cleaned or "服務費" in cleaned:
                continue
            price_match = MONEY_RE.search(cleaned)
            if not price_match:
                continue

            before = cleaned[: price_match.start()]
            after = cleaned[price_match.end() :]
            ticket_type = self._cleanup_ticket_type(before)
            if not ticket_type:
                ticket_type = self._cleanup_ticket_type(after)

            price_value = self._normalize_price(price_match.group())
            entries.append((ticket_type, price_value))

        return entries

    def _extract_ticket_data(self, sections: dict[str, list[str]]) -> tuple[str | None, str | None]:
        price_lines: list[str] = []
        for line in sections["price"]:
            cleaned = self._strip_field_prefix(line)
            if not cleaned:
                continue
            if "票價說明" in cleaned and not MONEY_RE.search(cleaned):
                continue
            if "服務費" in cleaned and not MONEY_RE.search(cleaned):
                continue
            price_lines.append(cleaned)

        if not price_lines:
            return None, None

        entries: list[tuple[str | None, str]] = []
        for line in price_lines:
            entries.extend(self._parse_ticket_entries(line))
        entries = list(dict.fromkeys(entries))

        explicit_types = self._dedupe([ticket_type for ticket_type, _ in entries if ticket_type])
        typed_ratio = len(explicit_types) / len(entries) if entries else 0

        ticket_types = " / ".join(explicit_types) if explicit_types else None
        if entries and typed_ratio >= 0.6:
            normalized_entries = []
            for ticket_type, price in entries:
                normalized_entries.append(f"{ticket_type} {price}" if ticket_type else price)
            ticket_price = " / ".join(self._dedupe(normalized_entries))
        elif entries:
            ticket_price = " / ".join(self._dedupe(price_lines))
        else:
            ticket_price = " / ".join(self._dedupe(price_lines))

        return ticket_price, ticket_types

    def _looks_like_address(self, text: str) -> bool:
        return bool(ADDRESS_RE.search(text))

    def _looks_like_venue(self, text: str) -> bool:
        return any(keyword.lower() in text.lower() for keyword in VENUE_KEYWORDS)

    def _extract_location(self, sections: dict[str, list[str]]) -> tuple[str | None, str | None]:
        venue_candidates: list[str] = []
        address_candidates: list[str] = []

        for raw_line in sections["location"]:
            line = self._strip_field_prefix(raw_line)
            if not line:
                continue

            bracket_match = re.match(r"(.+?)[（(]([^()（）]*?(?:市|縣|區|鄉|鎮|里|路|街|段|巷|弄|號|樓).*?)[）)]$", line)
            if bracket_match:
                venue_candidates.append(self._clean_text(bracket_match.group(1)))
                address_candidates.append(self._clean_text(bracket_match.group(2)))
                continue

            if self._looks_like_address(line) and not self._looks_like_venue(line):
                address_candidates.append(line)
                continue

            venue_candidates.append(line)

        venue_name = self._pick_best_venue(venue_candidates)
        address = self._pick_best_address(address_candidates)
        return venue_name, address

    def _pick_best_venue(self, candidates: list[str]) -> str | None:
        candidates = self._dedupe([candidate for candidate in candidates if candidate and "http" not in candidate.lower()])
        if not candidates:
            return None
        chinese_first = sorted(
            candidates,
            key=lambda candidate: (
                0 if re.search(r"[\u4e00-\u9fff]", candidate) else 1,
                0 if self._looks_like_venue(candidate) else 1,
                len(candidate),
            ),
        )
        return chinese_first[0]

    def _pick_best_address(self, candidates: list[str]) -> str | None:
        candidates = self._dedupe([candidate for candidate in candidates if candidate and "http" not in candidate.lower()])
        if not candidates:
            return None
        ordered = sorted(candidates, key=lambda candidate: (0 if self._looks_like_address(candidate) else 1, len(candidate)))
        return ordered[0]

    def _simplify_page_title(self, page_title: str) -> str | None:
        title = self._clean_text(page_title)
        title = re.sub(r"\s*\|\s*tixcraft.*$", "", title, flags=re.IGNORECASE)
        title = re.sub(r"\s*@\s*.+$", "", title)
        return self._normalize_value(title)

    def _extract_event_name(self, payload: dict[str, Any]) -> str:
        title = self._normalize_value(payload.get("title"))
        if title:
            return title

        page_title = self._simplify_page_title(payload.get("pageTitle", ""))
        if page_title:
            return page_title

        data_layer = payload.get("dataLayer") or {}
        artist_name = self._normalize_value(data_layer.get("artistName"))
        if artist_name:
            return artist_name

        return "未找到"

    def _guess_artist_from_title(self, title: str) -> str | None:
        if not title:
            return None

        keyword_pattern = re.compile(
            r"\b(?:tour|fan meeting|concert|live|showcase|party|encore)\b",
            flags=re.IGNORECASE,
        )
        if keyword_pattern.search(title):
            match = re.split(r"\b(?:tour|fan meeting|concert|live|showcase|party|encore)\b", title, maxsplit=1, flags=re.IGNORECASE)
            candidate = self._normalize_value(match[0]) if match else None
            if candidate and len(candidate) <= 40:
                return candidate

        if len(title) <= 30 and not any(keyword in title.lower() for keyword in GENERIC_ARTIST_KEYWORDS):
            return title

        return None

    def _extract_artist_name(self, payload: dict[str, Any], event_name: str) -> str | None:
        data_layer = payload.get("dataLayer") or {}
        category_name = self._clean_text(data_layer.get("childCategoryName", ""))
        if "音樂節" in category_name:
            return None

        artist_name = self._normalize_value(data_layer.get("artistName"))
        if artist_name:
            lowered = artist_name.lower()
            if not any(keyword in lowered for keyword in GENERIC_ARTIST_KEYWORDS):
                return artist_name

        return self._guess_artist_from_title(event_name)

    def _build_event_record(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        intro_lines = self._split_intro_lines(payload.get("intro", ""))
        sections = self._extract_sections(intro_lines)

        event_name = self._extract_event_name(payload)
        event_time = self._format_time_field(sections["event_time"], sale_mode=False)
        sale_time = self._format_time_field(sections["sale_time"], sale_mode=True)
        ticket_price, ticket_types = self._extract_ticket_data(sections)
        venue_name, address = self._extract_location(sections)
        artist_name = self._extract_artist_name(payload, event_name)

        record: dict[str, Any] = {
            "event_name": event_name,
            "event_link": url,
        }

        optional_fields = {
            "ticket_price": ticket_price,
            "ticket_types": ticket_types,
            "event_time": event_time,
            "sale_time": sale_time,
            "venue_name": venue_name,
            "address": address,
            "artist_name": artist_name,
        }
        for key, value in optional_fields.items():
            normalized = self._normalize_value(value)
            if normalized:
                record[key] = normalized

        return record

    def _write_output(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        result = {
            "scrape_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_events": len(records),
            "fields": [
                "event_name",
                "ticket_price",
                "ticket_types",
                "event_time",
                "sale_time",
                "event_link",
                "venue_name",
                "address",
                "artist_name",
            ],
            "events": records,
        }
        self.config.output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def scrape_all_events(self, limit: int | None = None) -> dict[str, Any]:
        if limit is not None:
            self.config.limit = limit

        try:
            links = self._load_listing_page()
            records: list[dict[str, Any]] = []

            for index, url in enumerate(links, 1):
                self.logger.info("處理第 %s/%s 筆：%s", index, len(links), url)
                payload = self._fetch_payload(url)
                record = self._build_event_record(url, payload)
                records.append(record)

            result = self._write_output(records)
            self.logger.info("輸出完成：%s", self.config.output_path)
            return result
        finally:
            self.close()


def main(limit: int | None = None, output_path: str = "tixcraft_activities.json", headless: bool = True) -> dict[str, Any]:
    scraper = TixcraftPrecisionFieldScraper(
        ScraperConfig(
            output_path=Path(output_path),
            limit=limit,
            headless=headless,
        )
    )
    return scraper.scrape_all_events(limit=limit)


if __name__ == "__main__":
    main()
