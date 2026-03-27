"""
lyrics/scraper.py
Playwright-based lyrics scraper per docs/scrapping.md.

Strategy:
  1. Clean YouTube boilerplate from title (strip "Artist - " prefix, "(Official Video)" etc).
  2. Search DuckDuckGo HTML (no JS, no bot detection) with site:letras.mus.br query.
  3. Filter + score candidates by URL slug similarity — not DDG text.
  4. Navigate to the chosen letras.mus.br page to extract lyrics.
  5. Fetch the PT-BR translation page (<base_url>traducao.html).
"""
from __future__ import annotations

import asyncio
import random
import re
import urllib.parse
from typing import Optional

from rapidfuzz import fuzz
from playwright.async_api import async_playwright, Page

from utils.logger import get_logger, log_structured
from utils.paths import BROWSER_DATA_DIR

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DDG_SEARCH = "https://html.duckduckgo.com/html/?q={query}"

# First path segment blocklist (letras.mus.br sections that are never song pages)
BLOCKED_FIRST_SEGMENTS = {
    "academy", "mais-acessadas", "topo", "playlists",
    "lancamentos", "news", "blogs",
}

# Second path segment blocklist (artist sub-sections, never a song page)
BLOCKED_SECOND_SEGMENTS = {
    "discografia", "videos", "albuns", "fotos", "bio", "historia",
    "noticias", "notícias", "letras", "cifras", "discography",
    "gallery", "comments", "videos-musicais",
}

BLOCKED_TERMS = {"significado", "tradução", "traducao"}
BLOCKED_SUFFIXES = ("/aprenda.html", "/traducao.html")

LYRICS_SELECTORS = [
    ".lyric-original",
    "article .lyric-original",
    ".cnt-letra p",
]

# Human-like delays (seconds)
DELAY_AFTER_SEARCH   = (2.0, 4.5)
DELAY_BEFORE_PTBR    = (1.5, 3.0)

# Retry config
MAX_RETRIES   = 3
RETRY_BACKOFF = [0, 1, 2]   # seconds before each attempt


# ---------------------------------------------------------------------------
# YouTube title cleaning
# ---------------------------------------------------------------------------

_ARTIST_PREFIX_RE_CACHE: dict[str, re.Pattern] = {}

# Patterns to strip from the end of YouTube video titles
_YT_NOISE = re.compile(
    r'\s*[\(\[]\s*(?:'
    r'official\s+(?:music\s+)?(?:video|audio|hd\s+video|lyric\s+video|visualizer|clip)|'
    r'oficial|lyric(?:s)?\s+video|lyric\s+video|audio\s+only|'
    r'official|music\s+video|hd|4k|\d{3,4}k|'
    r'remaster(?:ed)?(?:\s+\d{4})?|live(?:\s+version)?|'
    r'(?:ft|feat)\.?\s+[^)\]]+'
    r')\s*[\)\]]\s*$',
    re.IGNORECASE,
)


def _clean_title(raw_title: str, artist: str) -> str:
    """
    Strip YouTube boilerplate from a video title to get a clean song name.

    Examples:
      "Audioslave - Like a Stone (Official Video)" + "Audioslave" → "Like a Stone"
      "Foo Fighters - Everlong (Official HD Video)" + "Foo Fighters" → "Everlong"
      "Nirvana - Smells Like Teen Spirit [Remastered 2021]" + "Nirvana" → "Smells Like Teen Spirit"
    """
    t = raw_title.strip()

    # Strip "Artist - " prefix (most common YouTube convention)
    if artist:
        # Build/cache regex per artist
        if artist not in _ARTIST_PREFIX_RE_CACHE:
            _ARTIST_PREFIX_RE_CACHE[artist] = re.compile(
                rf'^{re.escape(artist.strip())}\s*[-–]\s*',
                re.IGNORECASE,
            )
        t = _ARTIST_PREFIX_RE_CACHE[artist].sub('', t)

    # Strip YouTube boilerplate suffixes in parentheses/brackets (up to 4 passes)
    for _ in range(4):
        cleaned = _YT_NOISE.sub('', t).strip(' -|')
        if cleaned == t:
            break
        t = cleaned

    t = t.strip()
    # Guard: if cleaning ate the whole title, fall back to the raw title
    if not t or len(t) < 2:
        return raw_title.strip()
    return t


# ---------------------------------------------------------------------------
# URL slug helpers
# ---------------------------------------------------------------------------

_ACCENT_MAP = str.maketrans(
    "áàãâäéèêëíìîïóòõôöúùûüýçñ",
    "aaaaaeeeeiiiiooooouuuuycn",
)


def _slugify(s: str) -> str:
    """Convert a string to a letras.mus.br-style URL slug."""
    s = s.lower().translate(_ACCENT_MAP)
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"[\s]+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


# ---------------------------------------------------------------------------
# Top-level async entrypoint
# ---------------------------------------------------------------------------

async def scrape_lyrics(title: str, artist: str) -> dict:
    """
    Full scraping pipeline for one track.

    Returns:
        {original_text, ptbr_text, original_url, ptbr_url,
         has_original, has_ptbr, failure_reason}
    """
    result: dict = {
        "original_text": None,
        "ptbr_text": None,
        "original_url": None,
        "ptbr_url": None,
        "has_original": False,
        "has_ptbr": False,
        "failure_reason": None,
    }

    title = _normalize(title)
    artist = _normalize(artist)

    if not title:
        result["failure_reason"] = "missing_title"
        return result

    # Step: clean yt-dlp title before building the query
    clean_t = _clean_title(title, artist)
    log.debug("Title cleaning: %r → %r", title, clean_t)

    query = f"site:letras.mus.br {clean_t} {artist}".strip()
    encoded = urllib.parse.quote_plus(query)
    search_url = DDG_SEARCH.format(query=encoded)

    log.debug("Scraping | query=%r | url=%s", query, search_url)
    log_structured("lyrics_scrape_start", query=query, search_url=search_url)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_DATA_DIR),
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.pages[0] if context.pages else await context.new_page()

        try:
            candidates = await _ddg_search(page, search_url)
            log.debug("DDG candidates: %d", len(candidates))

            if not candidates:
                result["failure_reason"] = "ddg_no_candidates"
                return result

            filtered = _filter_candidates(candidates)
            log.debug("Filtered candidates: %d", len(filtered))
            _log_top_candidates(filtered)

            if not filtered:
                result["failure_reason"] = "all_candidates_filtered"
                return result

            chosen_url = _choose_candidate(filtered, clean_t, artist)
            log.debug("Chosen URL: %s", chosen_url)
            result["original_url"] = chosen_url

            # Navigate to song page
            await _human_delay(*DELAY_AFTER_SEARCH)
            original_text = await _extract_lyrics_with_retry(page, chosen_url)
            if original_text:
                result["original_text"] = original_text
                result["has_original"] = True

            # PT-BR translation page: <base_url>traducao.html
            base = chosen_url.rstrip("/")
            ptbr_url = base + "/traducao.html"
            result["ptbr_url"] = ptbr_url

            await _human_delay(*DELAY_BEFORE_PTBR)
            ptbr_text = await _extract_lyrics_with_retry(page, ptbr_url, is_translation=True)
            if ptbr_text:
                result["ptbr_text"] = ptbr_text
                result["has_ptbr"] = True

        except Exception as exc:
            log.warning("Scraper unexpected error: %s", exc)
            result["failure_reason"] = str(exc)
        finally:
            await context.close()

    log_structured(
        "lyrics_scrape_end",
        query=query,
        chosen_url=result["original_url"],
        has_original=result["has_original"],
        has_ptbr=result["has_ptbr"],
        failure_reason=result["failure_reason"],
    )
    return result


# ---------------------------------------------------------------------------
# DuckDuckGo search
# ---------------------------------------------------------------------------

async def _ddg_search(page: Page, search_url: str) -> list[dict]:
    try:
        await page.goto(search_url, wait_until="domcontentloaded")
    except Exception as exc:
        log.warning("DDG navigation failed: %s", exc)
        return []

    await _human_delay(1.5, 3.0)

    raw: list[dict] = []
    for node in await page.query_selector_all("a.result__url"):
        href = await node.get_attribute("href") or ""
        text = (await node.inner_text()).strip()

        # Unwrap DDG redirect
        if "duckduckgo.com/l/?uddg=" in href:
            try:
                href = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
            except IndexError:
                continue

        if "letras.mus.br" in href and href.startswith("http"):
            # Normalize: strip query params and fragments
            parsed = urllib.parse.urlparse(href)
            href = urllib.parse.urlunparse(parsed._replace(query="", fragment=""))
            raw.append({"url": href, "text": text})

    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[dict] = []
    for c in raw:
        key = c["url"].lower()
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    log.debug("DDG raw=%d deduped=%d", len(raw), len(deduped))
    return deduped


# ---------------------------------------------------------------------------
# Candidate filtering
# ---------------------------------------------------------------------------

def _filter_candidates(candidates: list[dict]) -> list[dict]:
    filtered = []
    for c in candidates:
        url: str = c["url"]

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc not in ("www.letras.mus.br", "letras.mus.br"):
            continue

        segments = [s for s in parsed.path.strip("/").split("/") if s]

        # Must have at least artist + song
        if len(segments) < 2:
            continue

        # First segment: never a site section
        if segments[0] in BLOCKED_FIRST_SEGMENTS:
            continue

        # Second segment: never an artist sub-page category
        if segments[1] in BLOCKED_SECOND_SEGMENTS:
            continue

        # Non-canonical subpage suffixes
        if any(url.endswith(s) for s in BLOCKED_SUFFIXES):
            continue

        # Title/URL must not contain blocked terms
        combined = (c["text"] + " " + url).lower()
        if any(bt in combined for bt in BLOCKED_TERMS):
            continue

        filtered.append(c)

    return filtered


# ---------------------------------------------------------------------------
# Candidate selection — slug-based scoring
# ---------------------------------------------------------------------------

def _choose_candidate(candidates: list[dict], clean_title: str, artist: str) -> str:
    """
    Score each candidate by how well its URL path segments match
    the expected letras.mus.br slug for the song and artist.

    letras URLs follow:
      /artist-slug/song-slug/       (best case)
      /artist-slug/numeric-id/      (legacy)
    """
    title_slug  = _slugify(clean_title)
    artist_slug = _slugify(artist)

    log.debug("Slug targets: title=%r artist=%r", title_slug, artist_slug)

    best_url   = candidates[0]["url"]
    best_score = -1.0

    for c in candidates:
        parsed   = urllib.parse.urlparse(c["url"])
        segments = [s for s in parsed.path.strip("/").split("/") if s]
        if len(segments) < 2:
            continue

        seg_artist = segments[0]  # e.g. "audioslave"
        seg_song   = segments[1]  # e.g. "like-a-stone" or "69438"

        artist_score = fuzz.ratio(artist_slug, seg_artist) / 100.0

        if seg_song.isdigit():
            # Numeric IDs: we can't match by title, score purely on artist
            # and give a base bonus for being a concrete song ID
            score = artist_score * 0.5 + 0.2
        else:
            title_score = fuzz.ratio(title_slug, seg_song) / 100.0
            # Weight: song slug match is the primary signal (60%), artist secondary (40%)
            score = title_score * 0.6 + artist_score * 0.4

        log.debug(
            "Candidate score=%.2f  seg_artist=%r  seg_song=%r  url=%s",
            score, seg_artist, seg_song, c["url"],
        )

        if score > best_score:
            best_score = score
            best_url   = c["url"]

    log.debug("Winner: score=%.2f  url=%s", best_score, best_url)
    return best_url


# ---------------------------------------------------------------------------
# Lyrics extraction
# ---------------------------------------------------------------------------

async def _extract_lyrics_with_retry(
    page: Page,
    url: str,
    is_translation: bool = False,
) -> Optional[str]:
    for attempt in range(MAX_RETRIES):
        wait = RETRY_BACKOFF[attempt]
        if wait:
            await asyncio.sleep(wait)

        try:
            response = await page.goto(url, wait_until="domcontentloaded")
            status = response.status if response else 0

            if status == 404:
                log.debug("404 on %s — unavailable", url)
                return None

            if status in (403, 429):
                log.warning("HTTP %d on %s — retrying (attempt %d)", status, url, attempt + 1)
                continue

            await asyncio.sleep(1.5)  # let JS hydrate
            text = await _try_selectors(page)

            if text:
                log.debug("Extracted %d chars from %s", len(text), url)
                return text

            log.debug("No selector matched on %s", url)
            if not is_translation:
                log_structured("lyrics_selector_miss", url=url)
            return None

        except Exception as exc:
            log.warning("Error fetching %s (attempt %d): %s", url, attempt + 1, exc)

    log.warning("Exhausted retries for %s", url)
    return None


async def _try_selectors(page: Page) -> Optional[str]:
    for sel in LYRICS_SELECTORS:
        nodes = await page.query_selector_all(sel)
        if not nodes:
            continue
        fragments = []
        for node in nodes:
            txt = (await node.inner_text()).strip()
            if txt:
                fragments.append(txt)
        if fragments:
            return "\n\n".join(fragments)
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    return re.sub(r" {2,}", " ", s.strip())


def _log_top_candidates(candidates: list[dict], n: int = 5) -> None:
    for i, c in enumerate(candidates[:n]):
        log.debug("  Candidate[%d]: %s", i, c["url"])


async def _human_delay(lo: float, hi: float) -> None:
    delay = random.uniform(lo, hi)
    log.debug("Human delay: %.2fs", delay)
    await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Sync wrapper for worker thread
# ---------------------------------------------------------------------------

def scrape_lyrics_sync(title: str, artist: str) -> dict:
    """Synchronous wrapper — runs the async scraper in a fresh event loop."""
    return asyncio.run(scrape_lyrics(title, artist))
