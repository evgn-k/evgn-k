#!/usr/bin/env python3
"""Подставляет свежие посты из RSS блога в README между маркерами BLOG:START/END.

Только стандартная библиотека. При любой сетевой или парсерной проблеме
скрипт молча выходит с кодом 0 и не трогает README: вчерашняя лента постов
лучше, чем пустая. Отсутствие маркеров — ошибка конфигурации, exit 1.
"""

import html
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from pathlib import Path

FEED_URL = os.environ.get("FEED_URL", "https://kushnaren.co/index.xml")
README = Path(__file__).resolve().parent.parent / "README.md"
MAX_POSTS = 5
START = "<!-- BLOG:START -->"
END = "<!-- BLOG:END -->"
USER_AGENT = "evgn-k-readme-updater (+https://github.com/evgn-k/evgn-k)"


def fetch_feed(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def parse_items(raw):
    root = ET.fromstring(raw)
    items = []
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        items.append((title, link, format_date(item.findtext("pubDate"))))
    return items


def format_date(pub_date):
    if not pub_date:
        return ""
    try:
        return parsedate_to_datetime(pub_date.strip()).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def render(items):
    lines = []
    for title, link, date in items[:MAX_POSTS]:
        # Заголовки приходят с эмодзи и HTML-сущностями; скобки ломают markdown-ссылку.
        text = html.unescape(title).replace("[", "\\[").replace("]", "\\]")
        suffix = f" — {date}" if date else ""
        lines.append(f"- [{text}]({link}){suffix}")
    return "\n".join(lines)


def main():
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        print(f"маркеры {START}/{END} не найдены в {README}", file=sys.stderr)
        return 1

    try:
        items = parse_items(fetch_feed(FEED_URL))
    except (urllib.error.URLError, OSError, ET.ParseError) as err:
        print(f"фид {FEED_URL} недоступен или не разобран: {err}", file=sys.stderr)
        return 0

    if not items:
        print(f"в фиде {FEED_URL} нет записей — README оставлен без изменений", file=sys.stderr)
        return 0

    block = f"{START}\n{render(items)}\n{END}"
    updated = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _: block,
        readme,
        count=1,
        flags=re.DOTALL,
    )

    if updated == readme:
        print("изменений нет")
        return 0

    README.write_text(updated, encoding="utf-8")
    print(f"README обновлён: {min(len(items), MAX_POSTS)} постов")
    return 0


if __name__ == "__main__":
    sys.exit(main())
