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
DATE_RE = re.compile(
    r"(?:\d{4}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{1,2}"
    r"|\d{4}年\s*\d{1,2}月\s*\d{1,2}日"
    r"|\d{1,2}\s*[./-]\s*\d{1,2}(?:\s*[./-]\s*\d{2,4})?)"
)
TIME_RE = re.compile(r"\d{1,2}:\d{2}(?:\s*[AP]M)?", re.IGNORECASE)
PRICE_RE = re.compile(r"(?:NT\$|\$)\s*\d[\d,]*|\d[\d,]*(?:\s*元)")
BARE_PRICE_RE = re.compile(r"(?<!\d)(\d{3,5}(?:,\d{3})*)(?!\d)")
ADDRESS_RE = re.compile(
    r"(?:"
    r"[台臺新北桃竹苗中彰雲嘉南高屏宜花東澎金馬][^ \n]{0,12}[市縣]"
    r"|[^\n]{0,12}[市縣][^\n]{0,12}(?:區|鄉|鎮|市)"
    r"|[^\n]{0,20}(?:路|街|大道|巷|弄)(?:[^\n]{0,10}\d+號)?"
    r"|[^\d\n]{1,20}\d+F"
    r"|[^\n]{1,12}町"
    r")"
)
GENERIC_ARTIST_KEYWORDS = (
    "festival",
    "音樂節",
    "音乐节",
    "嘉年華",
    "嘉年华",
    "開唱",
    "开唱",
    "樂祭",
    "乐祭",
    "祭",
)
GENERIC_ARTIST_TITLE_KEYWORDS = (
    "主場賽事",
    "主场赛事",
    "季套票",
    "套票專區",
    "套票专区",
    "門票",
    "门票",
    "售票",
    "票券",
    "票務",
    "票务",
    "聯票",
    "联票",
    "限定",
    "聯名",
    "联名",
    "銀行",
    "银行",
    "專區",
    "专区",
)
ARTIST_EVENT_KEYWORDS = (
    "年度專場",
    "專場",
    "专场",
    "演唱會",
    "演唱会",
    "巡迴",
    "巡回",
    "見面會",
    "见面会",
    "音樂會",
    "音乐会",
    "fancon",
    "fan meeting",
    "world tour",
    "asia tour",
    "tour",
    "concert",
    "live",
    "showcase",
    "encore",
)
EXPLICIT_ARTIST_LABELS = (
    "藝人",
    "艺人",
    "藝人名稱",
    "艺人名称",
    "演出藝人",
    "演出艺人",
    "演出者",
    "出演",
    "演出單位",
    "演出单位",
    "表演嘉賓",
    "表演嘉宾",
    "artist",
    "artists",
    "lineup",
    "performer",
    "performers",
)
TITLE_BRAND_MARKERS = (
    " x ",
    " × ",
    "合作",
    "限定",
    "聯名",
    "联名",
    "銀行",
    "银行",
    "presented by",
    "sponsored by",
)
SPORT_CATEGORY_KEYWORDS = (
    "sports",
    "sport",
    "籃球",
    "篮球",
    "棒球",
    "足球",
    "排球",
    "網球",
    "网球",
    "羽球",
    "羽毛球",
    "電競",
    "电竞",
    "賽車",
    "赛车",
)
VENUE_KEYWORDS = (
    "arena",
    "hall",
    "stadium",
    "dome",
    "center",
    "centre",
    "legacy",
    "zepp",
    "theater",
    "theatre",
    "小巨蛋",
    "巨蛋",
    "體育館",
    "体育馆",
    "展演",
    "展覽館",
    "展览馆",
    "音樂中心",
    "音乐中心",
    "流行音樂中心",
    "流行音乐中心",
    "場館",
    "场馆",
    "會館",
    "会馆",
)
PLACEHOLDERS = {"", "n/a", "none", "null"}
SECTION_FIELDS = ("event_time", "sale_time", "price", "location")


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

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        log_path = Path(__file__).with_name("tixcraft_precision_field.log")

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
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
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
            if DETAIL_LINK_PATTERN not in link or link in seen:
                continue
            seen.add(link)
            unique_links.append(link)

        if self.config.limit:
            unique_links = unique_links[: self.config.limit]

        self.logger.info("Collected %s activity links", len(unique_links))
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

        return driver.execute_script(
            """
            const readText = (selector) => document.querySelector(selector)?.innerText || '';
            const detail = Array.isArray(window.dataLayer)
                ? window.dataLayer.find((item) => item && item.event === 'EnterActivityDetail') || {}
                : {};
            return {
                title: readText('#synopsisEventTitle'),
                intro: readText('#intro'),
                pageTitle: document.title || '',
                currentUrl: window.location.href,
                dataLayer: detail,
            };
            """
        )

    def _clean_text(self, text: str | None) -> str:
        if not text:
            return ""
        cleaned = text.replace("\u00a0", " ").replace("\u3000", " ").replace("\ufeff", "")
        cleaned = cleaned.replace("｜", ":").replace("：", ":").replace("﹕", ":").replace("／", "/")
        cleaned = cleaned.replace("\r", "\n")
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        cleaned = re.sub(r"\n{2,}", "\n", cleaned)
        return cleaned.strip()

    def _normalize_value(self, value: str | None) -> str | None:
        cleaned = self._clean_text(value)
        if not cleaned:
            return None
        if cleaned.lower() in PLACEHOLDERS:
            return None
        return cleaned

    def _contains_generic_artist_keyword(self, text: str) -> bool:
        lowered = self._clean_text(text).lower()
        return any(keyword in lowered for keyword in GENERIC_ARTIST_KEYWORDS)

    def _contains_generic_artist_title_keyword(self, text: str) -> bool:
        lowered = self._clean_text(text).lower()
        return any(keyword in lowered for keyword in GENERIC_ARTIST_TITLE_KEYWORDS)

    def _is_sports_category(self, *values: str | None) -> bool:
        lowered_values = [self._clean_text(value).lower() for value in values if value]
        return any(any(keyword in value for keyword in SPORT_CATEGORY_KEYWORDS) for value in lowered_values)

    def _contains_artist_event_keyword(self, text: str) -> bool:
        lowered = self._clean_text(text).lower()
        return any(keyword in lowered for keyword in ARTIST_EVENT_KEYWORDS)

    def _strip_event_title_prefixes(self, title: str) -> str:
        cleaned = self._clean_text(title)
        cleaned = re.sub(r"^【[^】]+】\s*", "", cleaned)
        cleaned = re.sub(r"^\d{4}(?:-\d{2})?\s*", "", cleaned)
        return cleaned.strip()

    def _contains_brand_marker(self, text: str) -> bool:
        lowered = self._clean_text(text).lower()
        compact = self._compact(text).lower()
        return (
            any(marker in lowered for marker in TITLE_BRAND_MARKERS)
            or bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9][x×][\u4e00-\u9fffA-Za-z0-9]", self._clean_text(text)))
            or any(
            keyword in compact for keyword in GENERIC_ARTIST_TITLE_KEYWORDS
        )
        )

    def _clean_artist_candidate(self, value: str | None) -> str | None:
        cleaned = self._normalize_value(value)
        if not cleaned:
            return None
        cleaned = re.sub(r"^【[^】]+】\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:/")
        if not cleaned:
            return None
        return cleaned

    def _has_structured_title_artist_signal(self, event_name: str, candidate: str | None) -> bool:
        title = self._strip_event_title_prefixes(event_name)
        cleaned_candidate = self._clean_artist_candidate(candidate)
        if not title or not cleaned_candidate:
            return False

        title_lower = title.lower()
        candidate_lower = cleaned_candidate.lower()
        if not title_lower.startswith(candidate_lower):
            return False

        suffix = title[len(cleaned_candidate) :].strip()
        if not suffix:
            return False
        if self._contains_artist_event_keyword(suffix):
            return True
        if re.search(r"[《〈＜「『].+[》〉＞」』]", title) and re.search(
            r"(\bin\b\s+[A-Za-z][A-Za-z ]+|台北站|臺北站|高雄站|台中站|臺中站|桃園站|台南站|臺南站|TAIPEI|KAOHSIUNG|TAICHUNG|TAINAN|TAOYUAN)\s*$",
            title,
            flags=re.IGNORECASE,
        ):
            return True
        if re.search(r"(粉絲見面會|粉丝见面会|fan meeting|tour|concert|live)", suffix, flags=re.IGNORECASE):
            return True
        return False

    def _looks_like_valid_artist_candidate(
        self,
        candidate: str | None,
        event_name: str,
        category_values: set[str],
        require_title_support: bool,
    ) -> bool:
        cleaned = self._clean_artist_candidate(candidate)
        if not cleaned:
            return False

        lowered = cleaned.lower()
        if len(cleaned) < 2 or len(cleaned) > 40:
            return False
        if lowered in category_values:
            return False
        if DATE_RE.search(cleaned) or TIME_RE.search(cleaned) or PRICE_RE.search(cleaned):
            return False
        if self._contains_generic_artist_keyword(cleaned) or self._contains_generic_artist_title_keyword(cleaned):
            return False
        if self._contains_brand_marker(cleaned):
            return False

        if not require_title_support:
            return True

        normalized_title = self._strip_event_title_prefixes(event_name)
        normalized_title_lower = normalized_title.lower()

        if normalized_title_lower == lowered:
            return True
        if self._has_structured_title_artist_signal(normalized_title, cleaned):
            return True
        if self._contains_brand_marker(normalized_title) and not self._contains_artist_event_keyword(normalized_title):
            return False

        if lowered in normalized_title_lower:
            suffix = normalized_title_lower.split(lowered, 1)[1].strip(" :-:：")
            if suffix and self._contains_artist_event_keyword(suffix):
                return True
            if suffix and not self._contains_brand_marker(suffix) and not self._contains_generic_artist_keyword(suffix):
                return len(suffix) <= 30

        return self._contains_artist_event_keyword(normalized_title) and not self._contains_brand_marker(normalized_title)

    def _extract_explicit_artist_name(self, intro_lines: list[str], event_name: str, category_values: set[str]) -> str | None:
        candidates: list[str] = []
        explicit_labels = {self._compact(item).lower() for item in EXPLICIT_ARTIST_LABELS}
        for line in intro_lines:
            stripped = self._strip_bullet_prefix(line)
            if ":" not in stripped:
                continue
            raw_label, raw_content = stripped.split(":", 1)
            label = self._compact(raw_label).lower()
            if label not in explicit_labels:
                continue
            candidate = self._clean_artist_candidate(raw_content)
            if self._looks_like_valid_artist_candidate(candidate, event_name, category_values, require_title_support=False):
                candidates.append(candidate)

        deduped = self._dedupe(candidates)
        return " / ".join(deduped) if deduped else None

    def _compact(self, text: str) -> str:
        return re.sub(r"\s+", "", self._clean_text(text))

    def _strip_bullet_prefix(self, text: str) -> str:
        return re.sub(r"^[\s\-*•●◆■□※【】]+", "", self._clean_text(text)).strip()

    def _split_intro_lines(self, intro: str) -> list[str]:
        lines: list[str] = []
        for raw_line in self._clean_text(intro).splitlines():
            line = self._strip_bullet_prefix(raw_line)
            if not line:
                continue
            lines.append(line)
        return lines

    def _is_generic_sale_heading(self, text: str) -> bool:
        compact = self._compact(text).lower()
        return compact in {"售票階段及說明", "售票資訊", "售票方式", "ticketsalesschedule"}

    def _has_date_or_time(self, text: str) -> bool:
        return bool(DATE_RE.search(text) or TIME_RE.search(text))

    def _looks_like_price_context(self, text: str) -> bool:
        compact = self._compact(text).lower()
        return any(
            keyword in compact
            for keyword in ("票價", "活動票價", "演出票價", "ticketprice", "ticketprices", "price")
        )

    def _match_label(self, line: str) -> tuple[str | None, str]:
        stripped = self._strip_bullet_prefix(line)
        if ":" not in stripped:
            return None, stripped

        raw_label, raw_content = stripped.split(":", 1)
        label = self._compact(raw_label).lower()
        content = self._clean_text(raw_content)

        sale_aliases = (
            "售票時間",
            "開賣時間",
            "售票日期",
            "預售時間",
            "publiconsale",
            "ticketsalesschedule",
            "onsale",
            "presale",
            "pre-sale",
            "售票階段及說明",
        )
        event_aliases = (
            "演出日期",
            "演出時間",
            "活動日期",
            "活動時間",
            "日期",
            "時間",
            "date",
            "time",
        )
        price_aliases = ("活動票價", "演出票價", "票價", "票價資訊", "ticketprice", "ticketprices", "price")
        location_aliases = ("演出地點", "活動地點", "地點", "venue", "location")

        if any(alias in label for alias in sale_aliases):
            return "sale_time", content
        if label in location_aliases:
            return "location", content
        if label in price_aliases:
            return "price", content
        if label in event_aliases:
            return "event_time", content
        return None, stripped

    def _is_sale_stage_heading(self, line: str) -> bool:
        compact = self._compact(line).lower()
        if self._is_generic_sale_heading(line):
            return True
        if any(
            noise in compact
            for noise in (
                "資格",
                "限量發送",
                "請詳",
                "詳見",
                "更多資訊",
                "主辦保留",
                "verification",
                "cardholder",
                "information",
                "email",
                "successful",
                "registrant",
                "accesscode",
                "receive",
            )
        ):
            return False
        if self._has_date_or_time(line) or PRICE_RE.search(line):
            return False
        keywords = (
            "預售",
            "預購",
            "開賣",
            "公售",
            "抽選",
            "登記",
            "onsale",
            "publiconsale",
            "presale",
            "pre-sale",
            "mastercard",
            "會員購",
            "會員預售",
            "會員預購",
            "卡友預售",
        )
        return any(keyword in compact for keyword in keywords)

    def _is_time_label_only(self, line: str) -> bool:
        stripped = self._strip_bullet_prefix(line)
        if ":" not in stripped:
            return False
        label = self._compact(stripped.split(":", 1)[0]).lower()
        return label in {"時間", "日期", "time", "date"}

    def _is_continuation(self, field: str, line: str) -> bool:
        if "http" in line.lower():
            return False
        if field == "event_time":
            return self._has_date_or_time(line) and not self._is_sale_stage_heading(line) and not PRICE_RE.search(line)
        if field == "sale_time":
            return self._has_date_or_time(line) or self._is_sale_stage_heading(line)
        if field == "price":
            return self._looks_like_price_line(line)
        if field == "location":
            return not PRICE_RE.search(line) and not self._has_date_or_time(line) and len(line) <= 100
        return False

    def _extract_sections(self, lines: list[str]) -> dict[str, list[str]]:
        sections = {field: [] for field in SECTION_FIELDS}
        current_field: str | None = None

        for line in lines:
            if current_field == "sale_time" and self._is_time_label_only(line):
                sections["sale_time"].append(self._clean_text(line.split(":", 1)[1]))
                continue

            if current_field == "event_time" and self._is_time_label_only(line):
                sections["event_time"].append(self._clean_text(line.split(":", 1)[1]))
                continue

            field, content = self._match_label(line)
            if field:
                current_field = field
                if content:
                    sections[field].append(content)
                elif field == "sale_time" and self._is_sale_stage_heading(line) and not self._is_generic_sale_heading(line):
                    sections[field].append(self._strip_bullet_prefix(line).rstrip(":"))
                continue

            if self._is_sale_stage_heading(line):
                current_field = "sale_time"
                if not self._is_generic_sale_heading(line):
                    sections["sale_time"].append(self._strip_bullet_prefix(line).rstrip(":"))
                continue

            if current_field and self._is_continuation(current_field, line):
                sections[current_field].append(line)
                continue

            if self._looks_like_price_line(line):
                sections["price"].append(line)
                current_field = "price"
                continue

            current_field = None

        return {field: self._dedupe(values) for field, values in sections.items()}

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique: list[str] = []
        for value in values:
            cleaned = self._clean_text(value)
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            unique.append(cleaned)
        return unique

    def _normalize_datetime_text(self, text: str) -> str:
        normalized = self._clean_text(text)
        normalized = re.sub(r"(?<=\d)\s*/\s*(?=\d)", "/", normalized)
        normalized = re.sub(r"(?<=\d)\s*-\s*(?=\d)", "-", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"(\d)\s*:\s*(\d)", r"\1:\2", normalized)
        normalized = re.sub(r"\s*([AaPp][Mm])", r" \1", normalized)
        return normalized.strip(" /")

    def _format_event_time(self, values: list[str]) -> str | None:
        normalized = [self._normalize_datetime_text(value) for value in values if self._has_date_or_time(value)]
        normalized = self._dedupe(normalized)
        if not normalized:
            return None

        result: list[str] = []
        pending_date: str | None = None
        for value in normalized:
            has_date = bool(DATE_RE.search(value))
            has_time = bool(TIME_RE.search(value))
            if has_date and not has_time:
                if pending_date:
                    result.append(pending_date)
                pending_date = value
                continue
            if has_time and not has_date and pending_date:
                result.append(f"{pending_date} {value}")
                pending_date = None
                continue
            if pending_date:
                result.append(pending_date)
                pending_date = None
            result.append(value)
        if pending_date:
            result.append(pending_date)

        return " / ".join(self._dedupe(result)) if result else None

    def _format_sale_time(self, values: list[str]) -> str | None:
        cleaned_values = [self._normalize_datetime_text(value) for value in values]
        cleaned_values = self._dedupe(cleaned_values)
        if not cleaned_values:
            return None

        result: list[str] = []
        current_heading: str | None = None

        for value in cleaned_values:
            if self._is_generic_sale_heading(value):
                continue
            if self._is_sale_stage_heading(value) and not self._has_date_or_time(value):
                current_heading = value.rstrip(":")
                continue
            if self._has_date_or_time(value):
                if current_heading:
                    result.append(f"{current_heading} {value}")
                    current_heading = None
                else:
                    result.append(value)
                continue

        return " / ".join(self._dedupe(result)) if result else None

    def _trim_price_noise(self, text: str) -> str:
        cleaned = self._clean_text(text)
        for keyword in (
            "以上票價需",
            "系統服務費",
            "服務費另計",
            "system fee",
            "福利抽獎券",
            "關於福利抽選",
            "購票請洽",
            "更多資訊",
            "主辦單位",
            "演出長度",
            "拓元註冊",
            "每個帳號",
            "工作人員",
            "依現場",
        ):
            if keyword in cleaned:
                cleaned = cleaned.split(keyword, 1)[0]
        return cleaned.strip(" /")

    def _looks_like_price_line(self, text: str) -> bool:
        compact = self._compact(text).lower()
        if any(keyword in compact for keyword in ("服務費", "加購資格", "福利抽獎券")) and not self._looks_like_price_context(text):
            return False
        if self._has_date_or_time(text) and not self._looks_like_price_context(text) and not re.search(r"(?:NT\$|\$|\d+\s*元)", text):
            return False
        return bool(PRICE_RE.search(text) or self._looks_like_price_context(text))

    def _extract_price_tokens(self, text: str, allow_bare: bool) -> list[str]:
        tokens = [match.group(0) for match in PRICE_RE.finditer(text)]
        if tokens:
            return tokens
        if not allow_bare:
            return []
        return [match.group(1) for match in BARE_PRICE_RE.finditer(text)]

    def _normalize_price(self, raw_price: str) -> str:
        digits = re.search(r"\d[\d,]*", raw_price)
        if not digits:
            return self._clean_text(raw_price)
        value = int(digits.group(0).replace(",", ""))
        return f"NT${value:,}"

    def _price_amount(self, price: str) -> int | None:
        digits = re.search(r"\d[\d,]*", price)
        if not digits:
            return None
        return int(digits.group(0).replace(",", ""))

    def _cleanup_ticket_type(self, text: str) -> str | None:
        cleaned = self._clean_text(text)
        cleaned = re.sub(
            r"^(?:活動票價|演出票價|票\s*價|price|ticket\s*price)\s*:\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"^[❋✦▪️■□◆•*]+", "", cleaned)
        cleaned = re.sub(r"\bNT\.?\$?\s*$", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"^[\[\(（【]+|[\]\)）】]+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = cleaned.strip(" :/;-")
        if not cleaned:
            return None
        return cleaned

    def _looks_like_ticket_type(self, text: str) -> bool:
        candidate = self._cleanup_ticket_type(text)
        if not candidate:
            return False
        if len(candidate) > 40:
            return False
        lowered = candidate.lower()
        if lowered in {"票價", "price", "ticket price"}:
            return False
        if any(noise in lowered for noise in ("售票", "活動", "演出", "主辦", "購票", "服務費", "時間", "地點")):
            return False
        keywords = (
            "vip",
            "vvip",
            "package",
            "cat",
            "ga",
            "pass",
            "席",
            "區",
            "票",
            "站",
            "座",
            "身障",
            "輪椅",
            "wheelchair",
        )
        if any(keyword in lowered for keyword in keywords):
            return True
        if re.fullmatch(r"[A-Z0-9][A-Z0-9 .&+-]{0,12}", candidate):
            return True
        if re.fullmatch(r"\dF(?:站區|座位|座席|區)?", candidate, flags=re.IGNORECASE):
            return True
        return False

    def _parse_ticket_segment(self, segment: str, allow_bare: bool) -> tuple[str | None, str] | None:
        cleaned = self._trim_price_noise(segment)
        if not cleaned:
            return None

        tokens = self._extract_price_tokens(cleaned, allow_bare=allow_bare)
        if not tokens:
            return None

        first_token = tokens[0]
        match = re.search(re.escape(first_token), cleaned)
        if not match:
            return None

        ticket_type: str | None = None
        before = self._cleanup_ticket_type(cleaned[: match.start()])
        after = self._cleanup_ticket_type(cleaned[match.end() :])

        if before and self._looks_like_ticket_type(before):
            ticket_type = before
        elif after:
            trailing = re.split(r"[，。,/]", after, maxsplit=1)[0]
            trailing = self._cleanup_ticket_type(trailing)
            if trailing and self._looks_like_ticket_type(trailing):
                ticket_type = trailing

        return ticket_type, self._normalize_price(first_token)

    def _extract_ticket_data(self, sections: dict[str, list[str]], intro_lines: list[str]) -> tuple[str | None, str | None]:
        price_lines: list[str] = []
        for line in sections["price"]:
            cleaned = self._trim_price_noise(line)
            if cleaned:
                price_lines.append(cleaned)

        for line in intro_lines:
            if not self._looks_like_price_line(line):
                continue
            cleaned = self._trim_price_noise(line)
            if cleaned:
                price_lines.append(cleaned)

        price_lines = self._dedupe(price_lines)
        if not price_lines:
            return None, None

        typed_entries: list[tuple[str, str]] = []
        raw_prices: list[str] = []

        for line in price_lines:
            allow_bare = bool(re.search(r"(?:NT\$|\$|\d+\s*元)", line) or self._looks_like_price_context(line))
            parts = re.split(r"\s*/\s*", line)
            if len(parts) == 1:
                parts = [line]

            for part in parts:
                parsed = self._parse_ticket_segment(part, allow_bare=allow_bare)
                if not parsed:
                    for raw_price in self._extract_price_tokens(part, allow_bare=allow_bare):
                        raw_prices.append(self._normalize_price(raw_price))
                    continue

                ticket_type, price = parsed
                raw_prices.append(price)
                if ticket_type:
                    typed_entries.append((ticket_type, price))

        raw_prices = self._dedupe(raw_prices)
        unique_typed_entries = list(dict.fromkeys(typed_entries))
        ticket_types = self._dedupe([ticket_type for ticket_type, _ in unique_typed_entries])

        price_amounts = [amount for amount in (self._price_amount(price) for price in raw_prices) if amount is not None]
        if price_amounts and max(price_amounts) >= 1000:
            raw_prices = [price for price in raw_prices if (self._price_amount(price) or 0) >= 300]
            unique_typed_entries = [
                entry for entry in unique_typed_entries if (self._price_amount(entry[1]) or 0) >= 300
            ]
            ticket_types = self._dedupe([ticket_type for ticket_type, _ in unique_typed_entries])

        if unique_typed_entries:
            typed_prices = [price for _, price in unique_typed_entries]
            if len(ticket_types) >= 2 or len(unique_typed_entries) == len(raw_prices):
                return " / ".join(typed_prices), " / ".join(ticket_types)

        if raw_prices:
            partial_types = " / ".join(ticket_types) if ticket_types else None
            return " / ".join(raw_prices), partial_types

        return None, None

    def _looks_like_address(self, text: str) -> bool:
        if self._looks_like_ticket_type(text):
            return False
        return bool(ADDRESS_RE.search(text))

    def _is_reasonable_address_candidate(self, text: str) -> bool:
        cleaned = self._clean_text(text)
        if not cleaned or len(cleaned) > 40 or "。" in cleaned or "http" in cleaned.lower():
            return False
        if any(
            keyword in cleaned
            for keyword in ("排隊", "進場", "限購", "帳號", "工作人員", "註冊", "開賣", "售票", "序號", "抽選")
        ):
            return False
        return self._looks_like_address(cleaned)

    def _looks_like_venue(self, text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in VENUE_KEYWORDS)

    def _pick_best_venue(self, candidates: list[str]) -> str | None:
        cleaned_candidates = self._dedupe(
            [candidate for candidate in candidates if candidate and "http" not in candidate.lower()]
        )
        if not cleaned_candidates:
            return None
        ordered = sorted(
            cleaned_candidates,
            key=lambda value: (
                0 if self._looks_like_venue(value) else 1,
                0 if re.search(r"[\u4e00-\u9fff]", value) else 1,
                len(value),
            ),
        )
        return ordered[0]

    def _pick_best_address(self, candidates: list[str]) -> str | None:
        cleaned_candidates = self._dedupe(
            [candidate for candidate in candidates if candidate and "http" not in candidate.lower()]
        )
        if not cleaned_candidates:
            return None
        ordered = sorted(cleaned_candidates, key=lambda value: (0 if self._looks_like_address(value) else 1, len(value)))
        return ordered[0]

    def _extract_location(self, sections: dict[str, list[str]], intro_lines: list[str]) -> tuple[str | None, str | None]:
        venue_candidates: list[str] = []
        address_candidates: list[str] = []

        for raw_line in sections["location"]:
            line = self._clean_text(raw_line)
            if not line:
                continue

            bracket_match = re.match(r"(.+?)[(（]([^()（）]+)[)）]$", line)
            if bracket_match:
                outer = self._clean_text(bracket_match.group(1))
                inner = self._clean_text(bracket_match.group(2))
                if self._looks_like_address(inner):
                    venue_candidates.append(outer)
                    address_candidates.append(inner)
                    continue
                venue_candidates.append(line)
                continue

            if self._is_reasonable_address_candidate(line) and not self._looks_like_venue(line):
                address_candidates.append(line)
                continue

            venue_candidates.append(line)

        if not address_candidates:
            for line in intro_lines:
                if (
                    self._is_reasonable_address_candidate(line)
                    and not self._has_date_or_time(line)
                    and not self._looks_like_price_line(line)
                ):
                    address_candidates.append(line)

        venue_name = self._pick_best_venue(venue_candidates)
        address = self._pick_best_address(address_candidates)

        if not venue_name and address:
            return None, address
        return venue_name, address

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

        return "Unknown Event"

    def _guess_artist_from_title(self, event_name: str, category_values: set[str]) -> str | None:
        working = self._strip_event_title_prefixes(event_name)
        if not working:
            return None

        if self._contains_generic_artist_keyword(working) or self._contains_generic_artist_title_keyword(working):
            return None
        if not self._contains_artist_event_keyword(working):
            return None

        candidate: str | None = None
        match = re.search(
            r"(年度專場|專場|专场|演唱會|演唱会|巡迴|巡回|見面會|见面会|音樂會|音乐会|FANCON|FAN MEETING|WORLD TOUR|ASIA TOUR|TOUR|CONCERT|LIVE|SHOWCASE|ENCORE)",
            working,
            flags=re.IGNORECASE,
        )
        if match:
            candidate = self._clean_artist_candidate(working[: match.start()])

        if not candidate and ("：" in working or ":" in working):
            separator = "：" if "：" in working else ":"
            candidate = self._clean_artist_candidate(working.split(separator, 1)[0])

        if not candidate and re.search(r"\b20\d{2}\b", working):
            candidate = self._clean_artist_candidate(re.split(r"\b20\d{2}\b", working, maxsplit=1)[0])

        if self._looks_like_valid_artist_candidate(candidate, event_name, category_values, require_title_support=True):
            return candidate
        return None

    def _extract_artist_name(self, payload: dict[str, Any], event_name: str, intro_lines: list[str]) -> str | None:
        data_layer = payload.get("dataLayer") or {}
        artist_name = self._normalize_value(data_layer.get("artistName"))
        artist_name_en = self._normalize_value(data_layer.get("artistNameEn"))
        child_category = self._normalize_value(data_layer.get("childCategoryName"))
        child_category_en = self._normalize_value(data_layer.get("childCategoryNameEn"))
        parent_category = self._normalize_value(data_layer.get("parentCategoryName"))
        parent_category_en = self._normalize_value(data_layer.get("parentCategoryNameEn"))

        if self._is_sports_category(child_category, child_category_en, parent_category, parent_category_en):
            return None

        category_values = {
            value.lower()
            for value in (child_category, child_category_en, parent_category, parent_category_en)
            if value
        }

        explicit_artist = self._extract_explicit_artist_name(intro_lines, event_name, category_values)
        if explicit_artist:
            return explicit_artist

        for candidate in (artist_name, artist_name_en):
            if self._looks_like_valid_artist_candidate(candidate, event_name, category_values, require_title_support=True):
                return self._clean_artist_candidate(candidate)

        return self._guess_artist_from_title(event_name, category_values)

    def _build_event_record(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        intro_lines = self._split_intro_lines(payload.get("intro", ""))
        sections = self._extract_sections(intro_lines)

        event_name = self._extract_event_name(payload)
        ticket_price, ticket_types = self._extract_ticket_data(sections, intro_lines)
        event_time = self._format_event_time(sections["event_time"])
        sale_time = self._format_sale_time(sections["sale_time"])
        venue_name, address = self._extract_location(sections, intro_lines)
        artist_name = self._extract_artist_name(payload, event_name, intro_lines)

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
                self.logger.info("Scraping %s/%s %s", index, len(links), url)
                payload = self._fetch_payload(url)
                records.append(self._build_event_record(url, payload))

            result = self._write_output(records)
            self.logger.info("Saved results to %s", self.config.output_path)
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
