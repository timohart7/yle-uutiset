"""Yle uutiset podcast-syötteinä, yksi tiedosto per Ylen RSS.

python main.py                 päivitä kaikki
python main.py kotimaa urheilu päivitä vain nämä
"""

import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

UA = "yle-uutiset"
COVER = "https://yle.fi/ukko/assets/img/yle-logo-180.png"
AUDIO = re.compile(r'"audioContent"\s*:\s*(\{[^{}]*\})')
IMAGE = re.compile(r'<meta property="og:image" content="([^"]+)"')
ITEM = re.compile(r"<item>.*?</item>", re.DOTALL)
GUID = re.compile(r"<guid>([^<]+)</guid>")

# Nimi tiedostossa -> (otsikko, Ylen RSS). Lista: https://yle.fi/rss
FEEDS = {
    "tuoreimmat": ("Tuoreimmat", "https://yle.fi/rss/uutiset/tuoreimmat"),
    "paauutiset": ("Pääuutiset", "https://yle.fi/rss/uutiset/paauutiset"),
    "luetuimmat": ("Luetuimmat", "https://yle.fi/rss/uutiset/luetuimmat"),

    "kotimaa": ("Kotimaa", "https://yle.fi/rss/t/18-34837/fi"),
    "ulkomaat": ("Ulkomaat", "https://yle.fi/rss/t/18-34953/fi"),
    "talous": ("Talous", "https://yle.fi/rss/t/18-19274/fi"),
    "politiikka": ("Politiikka", "https://yle.fi/rss/t/18-38033/fi"),
    "kulttuuri": ("Kulttuuri", "https://yle.fi/rss/t/18-150067/fi"),
    "viihde": ("Viihde", "https://yle.fi/rss/t/18-36066/fi"),
    "tiede": ("Tiede", "https://yle.fi/rss/t/18-819/fi"),
    "luonto": ("Luonto", "https://yle.fi/rss/t/18-35354/fi"),
    "terveys": ("Terveys", "https://yle.fi/rss/t/18-35138/fi"),
    "liikenne": ("Liikenne", "https://yle.fi/rss/t/18-12/fi"),
    "kolumnit": ("Kolumnit", "https://yle.fi/rss/t/18-215844/fi"),
    "urheilu": ("Urheilu", "https://yle.fi/rss/urheilu"),

    "etela-karjala": ("Etelä-Karjala", "https://yle.fi/rss/t/18-141372/fi"),
    "etela-pohjanmaa": ("Etelä-Pohjanmaa", "https://yle.fi/rss/t/18-146311/fi"),
    "etela-savo": ("Etelä-Savo", "https://yle.fi/rss/t/18-141852/fi"),
    "kainuu": ("Kainuu", "https://yle.fi/rss/t/18-141399/fi"),
    "kanta-hame": ("Kanta-Häme", "https://yle.fi/rss/t/18-138727/fi"),
    "keski-pohjanmaa": ("Keski-Pohjanmaa", "https://yle.fi/rss/t/18-135629/fi"),
    "keski-suomi": ("Keski-Suomi", "https://yle.fi/rss/t/18-148148/fi"),
    "kymenlaakso": ("Kymenlaakso", "https://yle.fi/rss/t/18-131408/fi"),
    "lappi": ("Lappi", "https://yle.fi/rss/t/18-139752/fi"),
    "pirkanmaa": ("Pirkanmaa", "https://yle.fi/rss/t/18-146831/fi"),
    "pohjanmaa": ("Pohjanmaa", "https://yle.fi/rss/t/18-148149/fi"),
    "pohjois-karjala": ("Pohjois-Karjala", "https://yle.fi/rss/t/18-141936/fi"),
    "pohjois-pohjanmaa": ("Pohjois-Pohjanmaa", "https://yle.fi/rss/t/18-148154/fi"),
    "pohjois-savo": ("Pohjois-Savo", "https://yle.fi/rss/t/18-141764/fi"),
    "paijat-hame": ("Päijät-Häme", "https://yle.fi/rss/t/18-141401/fi"),
    "satakunta": ("Satakunta", "https://yle.fi/rss/t/18-139772/fi"),
    "uusimaa": ("Uusimaa", "https://yle.fi/rss/t/18-147345/fi"),
    "varsinais-suomi": ("Varsinais-Suomi", "https://yle.fi/rss/t/18-135507/fi"),
}

_media: dict[str, tuple[str | None, str | None, int]] = {}


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.read()


def load_items(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [match.group(0) for match in ITEM.finditer(path.read_text(encoding="utf-8"))]


def parse_duration(value: str) -> int:
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part) if part else 0 for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def item_xml(
    title: str,
    link: str,
    published: str,
    description: str,
    audio: str,
    image: str | None,
    duration: int,
) -> str:
    lines = [
        "<item>",
        f"  <title>{escape(title)}</title>",
        f"  <link>{escape(link)}</link>",
        f"  <guid>{escape(link)}</guid>",
        f"  <pubDate>{escape(published)}</pubDate>",
        f"  <description>{escape(description)}</description>",
        f'  <enclosure url="{escape(audio)}" length="0" type="audio/mpeg"/>',
    ]
    if duration:
        lines.append(f"  <itunes:duration>{format_duration(duration)}</itunes:duration>")
    if image:
        lines.append(f"  <itunes:image href={quoteattr(image)}/>")
    lines.append("</item>")
    return "\n".join(lines)


def article_media(link: str) -> tuple[str | None, str | None, int]:
    if link not in _media:
        html = get(link).decode("utf-8", "replace")
        match = AUDIO.search(html)
        payload: dict = {}
        if match:
            try:
                payload = json.loads(match.group(1))
            except json.JSONDecodeError:
                payload = {}
        image = IMAGE.search(html)
        _media[link] = (
            payload.get("url") or None,
            image.group(1) if image else None,
            parse_duration(str(payload.get("duration") or "")),
        )
    return _media[link]


def new_items(rss_url: str, known: set[str]) -> list[str]:
    channel = ET.fromstring(get(rss_url)).find("channel")
    items = []
    for item in channel.findall("item"):
        link = (item.findtext("guid") or item.findtext("link") or "").split("?", 1)[0]
        title = (item.findtext("title") or "").strip()
        if not link.startswith("http") or not title or link in known:
            continue
        audio, image, duration = article_media(link)
        if not audio:
            continue
        items.append(
            item_xml(
                title,
                link,
                item.findtext("pubDate") or "",
                item.findtext("description") or "",
                audio,
                image,
                duration,
            )
        )
        known.add(link)
    return items


def write_feed(path: Path, title: str, items: list[str]) -> None:
    body = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">',
            "<channel>",
            f"<title>Yle.fi | {escape(title)}</title>",
            "<link>https://yle.fi/uutiset</link>",
            f"<description>Ylen {escape(title)} kuunneltavina juttuina.</description>",
            "<language>fi</language>",
            f"<itunes:image href={quoteattr(COVER)}/>",
            *items,
            "</channel>",
            "</rss>",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def update(name: str) -> None:
    title, rss_url = FEEDS[name]
    path = Path("rss") / f"{name}.xml"
    old = load_items(path)
    known = {match.group(1) for block in old if (match := GUID.search(block))}
    fresh = new_items(rss_url, known)
    write_feed(path, title, fresh + old)
    print(f"{name}: {len(fresh)} uutta, {len(fresh) + len(old)} yhteensä")


if __name__ == "__main__":
    names = sys.argv[1:] or list(FEEDS)
    unknown = [name for name in names if name not in FEEDS]
    if unknown:
        raise SystemExit(f"Tuntematon syöte: {', '.join(unknown)}")
    for name in names:
        update(name)
