#!/usr/bin/env python3
"""Build the Best Picks static site into dist/."""

from __future__ import annotations

import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
DATA_PATH = ROOT / "data" / "products.json"
CONFIG_PATH = ROOT / "site-config.json"
CSS_PATH = ROOT / "src" / "site.css"
FAVICON_PATH = ROOT / "src" / "favicon.svg"

DISCLOSURE = "As an Amazon Associate I earn from qualifying purchases."
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
TAG_RE = re.compile(r"^[A-Za-z0-9-]{2,40}$")
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]")
DOT = "∯"
PRICE_OR_SCORE_RE = re.compile(
    r"(\$\s?\d|\b\d\.\d\s*/\s*5\b|\b\d\s+stars?\b|\breview count\b|\bout of 5\b)",
    re.IGNORECASE,
)
SITE_ORIGIN = "https://ironpirate83.github.io/best-picks"

ICONS = {
    "scanners": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><rect x="7" y="8" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M11 14h6M11 18h4M20 13v6" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>""",
    "diecast": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M6 18h20l-2-5H10L6 18z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M6 18v3h20v-3M10 21v2M22 21v2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>""",
    "fan-gear": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M8 5v22" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><path d="M8 6h14l-2.2 4 2.2 4H8z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>""",
    "dashcams": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><rect x="5" y="11" width="16" height="11" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M21 15l6-3v9l-6-3" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>""",
    "creator-gear": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><rect x="13" y="6" width="6" height="12" rx="3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M10 14a6 6 0 0 0 12 0M16 20v4M12 26h8" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>""",
    "home-kitchen": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><path d="M8 13h16v10a4 4 0 0 1-4 4h-8a4 4 0 0 1-4-4V13z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 13V10a4 4 0 0 1 8 0v3M6 16h2M24 16h2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>""",
    "outdoor-lake": """<svg class="icon" viewBox="0 0 32 32" aria-hidden="true"><circle cx="22" cy="9" r="3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M4 20c2.5-2 4.5-2 7 0s4.5 2 7 0 4.5-2 7 0M4 25c2.5-2 4.5-2 7 0s4.5 2 7 0 4.5-2 7 0" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>""",
}


def fail(message: str) -> None:
    print(f"build failed: {message}", file=sys.stderr)
    sys.exit(1)


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def split_sentences(text: str) -> list[str]:
    """Split on sentence punctuation without breaking decimals or initials."""
    protected = re.sub(r"(\d)\.(\d)", rf"\1{DOT}\2", text.strip())
    protected = re.sub(r"\b(?:No|Mr|Mrs|Ms|Dr|vs)\.", lambda m: m.group(0).replace(".", DOT), protected)
    protected = re.sub(r"\b([A-Z])\.", rf"\1{DOT}", protected)
    parts = SENTENCE_RE.findall(protected)
    restored = [part.replace(DOT, ".") for part in parts]
    if "".join(restored) != text.strip():
        return []
    return restored


def load() -> tuple[str, dict]:
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"could not read source files ({exc.__class__.__name__})")
    tag = str(config.get("associatesTag", "")).strip()
    if not TAG_RE.fullmatch(tag):
        fail("associatesTag in site-config.json is missing or not a single token")
    if set(config) != {"associatesTag"}:
        fail("site-config.json must contain only associatesTag")
    return tag, data


def amazon_url(asin: str, tag: str) -> str:
    return f"https://www.amazon.com/dp/{asin}/?tag={tag}"


def validate(data: dict, tag: str) -> None:
    if data.get("siteName") != "Best Picks":
        fail("siteName must be Best Picks")
    categories = data.get("categories")
    if not isinstance(categories, list) or not 1 <= len(categories) <= 8:
        fail("categories must be a short list")
    seen: set[str] = set()
    for category in categories:
        slug = category.get("slug", "")
        if slug not in ICONS:
            fail(f"unknown category slug {slug!r}")
        products = category.get("products")
        if category.get("group") not in ("primary", "secondary"):
            fail(f"{slug} needs a primary or secondary group")
        if not isinstance(products, list) or not 4 <= len(products) <= 8:
            fail(f"{slug} needs 4 to 8 products")
        for field in ("name", "summary", "intro"):
            if not str(category.get(field, "")).strip():
                fail(f"{slug} is missing {field}")
        for product in products:
            asin = product.get("asin", "")
            if not ASIN_RE.fullmatch(asin):
                fail(f"bad ASIN in {slug}")
            if asin in seen:
                fail(f"duplicate ASIN {asin}")
            seen.add(asin)
            for field in ("brand", "name", "blurb"):
                if not str(product.get(field, "")).strip():
                    fail(f"{asin} is missing {field}")
            blurb = product["blurb"].strip()
            sentences = split_sentences(blurb)
            if not 1 <= len(sentences) <= 2:
                fail(f"{asin} blurb must be 1 or 2 sentences")
            if PRICE_OR_SCORE_RE.search(blurb) or PRICE_OR_SCORE_RE.search(product["name"]):
                fail(f"{asin} includes a price or score")
            url = amazon_url(asin, tag)
            if not url.startswith("https://www.amazon.com/dp/"):
                fail(f"{asin} link is not a direct Amazon page")


def nav(current: str | None, categories: list[dict], prefix: str) -> str:
    items = []
    for category in categories:
        href = f"{prefix}{category['slug']}/"
        current_attr = ' aria-current="page"' if category["slug"] == current else ""
        label = category.get("navLabel") or category["name"]
        extra = ' class="nav-more"' if category.get("group") == "secondary" else ""
        items.append(f'<li><a href="{esc(href)}"{current_attr}{extra}>{esc(label)}</a></li>')
    return "<nav aria-label=\"Categories\"><ul>" + "".join(items) + "</ul></nav>"


def footer() -> str:
    return f"""<footer class="site-footer">
  <div class="wrap">
    <p class="again">{esc(DISCLOSURE)}</p>
    <p>Best Picks is an independent guide. The brands named here have not endorsed this site, and Amazon has not endorsed it either. Notes are written for this site from public product pages and roundups. They are not quotes and not a claim that we tested the item.</p>
    <p>These pages are static files. Best Picks does not ask you to sign in, does not run a cart, and does not set analytics cookies. A product link leaves this site for Amazon, which has its own privacy policy.</p>
  </div>
</footer>"""


def shell(title: str, description: str, canonical: str, prefix: str, body_attr: str, nav_html: str, main: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="{esc(prefix)}favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="{esc(prefix)}site.css">
</head>
<body{body_attr}>
  <a class="skip" href="#content">Skip to content</a>
  <header class="site-header">
    <div class="wrap header-row">
      <a class="wordmark" href="{esc(prefix or './')}">Best Picks</a>
      {nav_html}
    </div>
  </header>
  <p class="disclosure" role="note">{esc(DISCLOSURE)}</p>
  <main id="content">
{main}
  </main>
  {footer()}
</body>
</html>
"""


def shelf_html(category: dict) -> str:
    names = []
    for product in category["products"]:
        href = f"{category['slug']}/#{product['asin']}"
        names.append(f'<li><a href="{esc(href)}">{esc(product["name"])}</a></li>')
    count = len(category["products"])
    return f"""<li class="shelf" data-cat="{esc(category['slug'])}">
        <div class="shelf-head">
          {ICONS[category['slug']]}
          <div>
            <h2><a href="{esc(category['slug'] + '/')}">{esc(category['name'])}</a></h2>
            <p class="count">{count} picks</p>
          </div>
        </div>
        <p class="summary">{esc(category['summary'])}</p>
        <ul class="names">{''.join(names)}</ul>
      </li>"""


def render_home(data: dict, tag: str) -> str:
    categories = data["categories"]
    primary = [c for c in categories if c.get("group") != "secondary"]
    secondary = [c for c in categories if c.get("group") == "secondary"]
    main = f"""    <div class="checker" aria-hidden="true"></div>
    <section class="hero-band">
      <div class="hero wrap">
        <p class="kicker">NASCAR first</p>
        <h1>The race weekend, from the scanner to the camera.</h1>
        <p class="lede">A short list for a NASCAR link in bio: what to listen on, what to put on a shelf, what to sit on, a camera for the drive, and the kit for filming it. Kitchen and lake gear sit below the racing shelves. Open the Amazon page for the size, the color, and whatever it costs today.</p>
        <p class="checked">Listings checked {esc(data['checked'])}.</p>
      </div>
    </section>
    <div class="checker" aria-hidden="true"></div>
    <ol class="shelves wrap">
      {''.join(shelf_html(c) for c in primary)}
    </ol>
    <section class="also wrap">
      <h2>Also on the shelf</h2>
      <p>Kitchen tools and lake gear, for the weeks that are not a race weekend.</p>
    </section>
    <ol class="shelves wrap">
      {''.join(shelf_html(c) for c in secondary)}
    </ol>
    <section class="method wrap">
      <h2>How these lists are chosen</h2>
      <p>Each pick was still for sale on Amazon when this list was checked. Scanners, cameras, and kitchen tools are here because they have a long public record. Die-cast cars are the official Lionel replicas of a specific scheme, and those listings turn over fast, so read the driver and the year. The notes are our words. Prices and scores are not printed here.</p>
    </section>"""
    return shell(
        title="Best Picks",
        description="NASCAR-first picks for scanners, diecast, fan gear, dash cams, and creator gear, with a kitchen shelf and a lake shelf.",
        canonical=f"{SITE_ORIGIN}/",
        prefix="",
        body_attr=' data-group="primary"',
        nav_html=nav(None, categories, ""),
        main=main,
    )


def render_category(data: dict, category: dict, tag: str) -> str:
    cards = []
    for product in category["products"]:
        url = amazon_url(product["asin"], tag)
        cards.append(
            f"""<li>
      <article id="{esc(product['asin'])}">
        <p class="brand">{esc(product['brand'])}</p>
        <h2>{esc(product['name'])}</h2>
        <p class="blurb">{esc(product['blurb'])}</p>
        <a class="amazon" href="{esc(url)}" rel="sponsored nofollow noopener" target="_blank"><span class="amazon-label">View on Amazon</span><span class="amazon-url">{esc(url)}</span></a>
      </article>
    </li>"""
        )
    kicker = "NASCAR" if category.get("group") != "secondary" else "Also on the shelf"
    group = category.get("group") or "primary"
    main = f"""    <div class="checker" aria-hidden="true"></div>
    <header class="page-head wrap">
      <p class="kicker">{esc(kicker)}</p>
      <h1>{esc(category['name'])}</h1>
      <p class="intro">{esc(category['intro'])}</p>
    </header>
    <ol class="picks wrap">
      {''.join(cards)}
    </ol>"""
    return shell(
        title=f"{category['name']} · Best Picks",
        description=category["summary"],
        canonical=f"{SITE_ORIGIN}/{category['slug']}/",
        prefix="../",
        body_attr=f' data-cat="{esc(category["slug"])}" data-group="{esc(group)}"',
        nav_html=nav(category["slug"], data["categories"], "../"),
        main=main,
    )


def check_output(tag: str, pages: list[Path]) -> int:
    link_re = re.compile(
        r'<a class="amazon" href="(https://www\.amazon\.com/dp/([A-Z0-9]{10})/\?tag=([^"]+))" rel="sponsored nofollow noopener" target="_blank">'
    )
    count = 0
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if text.count(DISCLOSURE) < 2:
            fail(f"{page.name} is missing the disclosure")
        if "<img" in text.lower():
            fail("pages must not include images")
        if "amazon.com/images" in text or "logo" in text.lower() and "amazon" in text.lower():
            # "Amazon" appears in disclosure and links. Reject logo markup specifically.
            if re.search(r"amazon[^\"']{0,40}logo|logo[^\"']{0,40}amazon", text, re.I):
                fail("Amazon logo markup is not allowed")
        links = link_re.findall(text)
        if page.parent != DIST and not links:
            fail(f"{page} has no product links")
        for href, asin, found_tag in links:
            expected = amazon_url(asin, tag)
            if href != expected or found_tag != tag:
                fail(f"link mismatch for {asin}")
            if not href.startswith("https://www.amazon.com/dp/"):
                fail(f"cloaked or off-site link for {asin}")
            count += 1
        if re.search(r"amzn\.to|bit\.ly|tinyurl|amazon\.com/gp/redirect", text, re.I):
            fail("shortened or redirecting link found")
    if count < 18:
        fail("expected a product link on every pick")
    return count


def main() -> None:
    tag, data = load()
    validate(data, tag)
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copyfile(CSS_PATH, DIST / "site.css")
    shutil.copyfile(FAVICON_PATH, DIST / "favicon.svg")
    pages = [DIST / "index.html"]
    pages[0].write_text(render_home(data, tag), encoding="utf-8")
    for category in data["categories"]:
        folder = DIST / category["slug"]
        folder.mkdir()
        page = folder / "index.html"
        page.write_text(render_category(data, category, tag), encoding="utf-8")
        pages.append(page)
    link_count = check_output(tag, pages)
    product_count = sum(len(category["products"]) for category in data["categories"])
    if link_count != product_count:
        fail("link count does not match product count")
    print(f"Built {len(pages)} pages, {product_count} products, {link_count} Amazon links.")


if __name__ == "__main__":
    main()
