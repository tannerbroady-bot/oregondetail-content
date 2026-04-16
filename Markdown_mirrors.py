
#!/usr/bin/env python3
"""
generate_markdown_mirrors.py
Fetches every page from oregondetail.com, strips navigation/scripts/widgets,
converts to clean markdown, and writes each page to markdown_mirrors/{slug}/index.md
with YAML frontmatter. Re-runnable — overwrites existing files on each run.
"""

import os
import re
import requests
from datetime import date
from bs4 import BeautifulSoup
from markdownify import markdownify as md

# ── Configuration ──────────────────────────────────────────────────────────────

BASE_URL = "https://oregondetail.com"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "markdown_mirrors")
TODAY = date.today().isoformat()

PAGES = [
    {"slug": "home",                      "url": "/"},
    {"slug": "service-menu",              "url": "/service-menu"},
    {"slug": "ceramic-coating",           "url": "/ceramic-coating"},
    {"slug": "auto-detailing",            "url": "/auto-detailing"},
    {"slug": "glassparency-protection",   "url": "/glassparency-protection"},
    {"slug": "rv-services",               "url": "/rv-services"},
    {"slug": "classics",                  "url": "/classics"},
    {"slug": "faqs",                      "url": "/faqs"},
    {"slug": "springfield",               "url": "/auto-detailing-springfield-oregon"},
    {"slug": "blog",                      "url": "/blog"},
    {"slug": "blog-ceramic-coating",      "url": "/blog/ceramic-coating-eugene-oregon"},
    {"slug": "blog-ppf-vs-ceramic",       "url": "/blog/ppf-vs-ceramic-coating-eugene-oregon"},
]

# Elements to strip entirely before conversion
STRIP_TAGS = [
    "nav", "footer", "script", "style", "noscript",
    "iframe", "header", "svg", "link", "meta"
]

# CSS class fragments that indicate elements to remove
STRIP_CLASS_PATTERNS = [
    "nav", "footer", "cta-split", "ghl", "announcement",
    "cookie", "chat", "widget", "popup", "overlay",
    "mobile-bar", "Mobile-bar", "Mobile-overlay",
    "Cart", "sqs-announcement", "Header"
]


def should_strip_by_class(tag):
    classes = tag.get("class", [])
    for cls in classes:
        for pattern in STRIP_CLASS_PATTERNS:
            if pattern.lower() in cls.lower():
                return True
    return False


def fetch_page(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MarkdownMirror/1.0)"}
    resp = requests.get(BASE_URL + url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text


def extract_meta(soup, full_url):
    title = ""
    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text(strip=True)
        # Strip Squarespace site suffix like " — Oregon Detail"
        title = re.sub(r"\s+[—–-]\s+Oregon Detail.*$", "", raw).strip()

    description = ""
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag:
        description = desc_tag.get("content", "").strip()

    canonical = full_url
    canon_tag = soup.find("link", attrs={"rel": "canonical"})
    if canon_tag:
        canonical = canon_tag.get("href", full_url).strip()

    return title, description, canonical


def clean_soup(soup):
    # Remove strip tags
    for tag in STRIP_TAGS:
        for el in soup.find_all(tag):
            el.decompose()

    # Remove elements by class pattern
    for el in soup.find_all(True):
        if should_strip_by_class(el):
            el.decompose()

    # Remove empty divs and spans
    changed = True
    while changed:
        changed = False
        for el in soup.find_all(["div", "span", "section", "p"]):
            if not el.get_text(strip=True) and not el.find("img"):
                el.decompose()
                changed = True

    return soup


def clean_markdown(text):
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Remove standalone step numbers like "01\n" or "02\n"
    text = re.sub(r"^\s*\d{2}\s*$", "", text, flags=re.MULTILINE)
    # Remove bullet separator characters
    text = re.sub(r"^\s*[•·▪▸►▶◆■□]\s*$", "", text, flags=re.MULTILINE)
    # Remove empty image alt tags: ![](...) 
    text = re.sub(r"!\[\]\([^)]*\)", "", text)
    # Remove lines that are just whitespace
    text = re.sub(r"^\s+$", "", text, flags=re.MULTILINE)
    # Strip Squarespace CSS block remnants
    text = re.sub(r"#block-[a-z0-9_]+\s*\{[^}]*\}", "", text)
    # Remove leftover CSS variable lines
    text = re.sub(r"--[a-z-]+:\s*[^;]+;", "", text)
    # Final trim
    text = text.strip()
    return text


def build_frontmatter(title, description, canonical):
    # Escape any quotes in title/description
    title = title.replace('"', "'")
    description = description.replace('"', "'")
    return f"""---
title: "{title}"
description: "{description}"
url: "{canonical}"
last_updated: "{TODAY}"
---

"""


def generate_mirror(page):
    slug = page["slug"]
    url = page["url"]
    full_url = BASE_URL + url

    print(f"  Fetching /{slug} ...", end=" ")

    try:
        html = fetch_page(url)
    except Exception as e:
        print(f"FAILED ({e})")
        return False

    soup = BeautifulSoup(html, "html.parser")
    title, description, canonical = extract_meta(soup, full_url)

    # Work on main content area only
    main = soup.find("main") or soup.find("body")
    if not main:
        print("SKIPPED (no main/body)")
        return False

    main = clean_soup(main)

    # Convert to markdown
    raw_md = md(str(main), heading_style="ATX", bullets="-", strip=["a"])
    clean_md = clean_markdown(raw_md)

    if not clean_md:
        print("SKIPPED (empty content)")
        return False

    # Build output
    frontmatter = build_frontmatter(title, description, canonical)
    output = frontmatter + clean_md

    # Write file
    out_dir = os.path.join(OUTPUT_DIR, slug)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.md")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)

    word_count = len(clean_md.split())
    print(f"OK ({word_count} words → {out_path.replace(OUTPUT_DIR, 'markdown_mirrors')})")
    return True


def main():
    print(f"\n{'='*60}")
    print(f"  Oregon Detail Co — Markdown Mirror Generator")
    print(f"  {TODAY}")
    print(f"{'='*60}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    success = 0
    failed = 0

    for page in PAGES:
        result = generate_mirror(page)
        if result:
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Done. {success} pages generated, {failed} failed.")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
