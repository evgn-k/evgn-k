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
from urllib.parse import urlparse

FEED_URL = os.environ.get("FEED_URL", "https://kushnaren.co/index.xml")
# Фид отдаёт не только статьи: там же фотопосты и служебные /search/ и /404.html.
POSTS_PREFIX = os.environ.get("POSTS_PREFIX", "/posts/")
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
    total = 0
    for item in root.findall("./channel/item"):
        total += 1
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        # Сравниваем именно путь: подстрока совпала бы и на хосте posts.example.com.
        if not urlparse(link).path.startswith(POSTS_PREFIX):
            continue
        items.append((title, link, format_date(item.findtext("pubDate"))))
    return items, total


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
        items, total = parse_items(fetch_feed(FEED_URL))
    except (urllib.error.URLError, OSError, ET.ParseError) as err:
        print(f"фид {FEED_URL} недоступен или не разобран: {err}", file=sys.stderr)
        return 0

    if not total:
        print(f"в фиде {FEED_URL} нет записей — README оставлен без изменений", file=sys.stderr)
        return 0

    if not items:
        # Скорее всего сменилась схема URL. Замереть на вчерашней ленте лучше,
        # чем стереть секцию, поэтому это не ошибка сборки.
        print(
            f"ни одна из {total} записей фида не подходит под префикс {POSTS_PREFIX} — "
            "README оставлен без изменений",
            file=sys.stderr,
        )
        return 0

    print(f"в фиде {total} записей, под {POSTS_PREFIX} подходит {len(items)}", file=sys.stderr)

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
