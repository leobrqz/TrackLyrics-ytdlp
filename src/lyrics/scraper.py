"""
lyrics/scraper.py
HTTP-first lyrics scraper (curl_cffi browser impersonation) per docs/scrapping.md.

Strategy:
  1. Clean YouTube boilerplate from title.
  2. Discover letras.mus.br URLs via DuckDuckGo HTML, then Bing HTML fallback.
  3. Filter + score candidates by URL slug similarity (RapidFuzz).
  4. GET letras pages and parse lyrics with BeautifulSoup (same CSS selectors).
"""
from __future__ import annotations

import asyncio
import base64
import html as html_module
import random
import re
import sys
import urllib.parse
from typing import Any, Optional

from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from rapidfuzz import fuzz

from utils.logger import get_logger, log_structured

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DDG_SEARCH = "https://html.duckduckgo.com/html/?q={query}"
DDG_HTML_FORM = "https://html.duckduckgo.com/html/"
BING_SEARCH = "https://www.bing.com/search?q={query}"

# curl_cffi impersonation targets (pinned for reproducibility; see curl_cffi docs)
IMPERSONATE_ORDER = ("chrome120", "chrome116", "edge101")

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

# letras traducao.html uses translation-specific blocks first
LYRICS_SELECTORS_TRANSLATION = [
    ".lyric-translation",
    "article .lyric-translation",
    ".lyric-original",
    "article .lyric-original",
    ".cnt-letra p",
]

DELAY_AFTER_SEARCH = (2.0, 4.5)
DELAY_BEFORE_PTBR = (1.5, 3.0)

MAX_RETRIES = 3
RETRY_BACKOFF = [0, 1, 2]

# ---------------------------------------------------------------------------
# YouTube title cleaning
# ---------------------------------------------------------------------------

_ARTIST_PREFIX_RE_CACHE: dict[str, re.Pattern] = {}

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

# Strip " | music video" style channel/upload descriptors (not part of song title).
_YT_PIPE_TRAILER = re.compile(
    r"\s*\|\s*"
    r"(?:music\s+video|lyric\s+video|official\s+video|official\s+audio|"
    r"visualizer|audio\s+only|clip|shorts)\s*$",
    re.IGNORECASE,
)

_TITLE_ARTIST_SPLIT = re.compile(r"^(.+?)\s*[-–]\s+(.+)$")


def _clean_track_segment(segment: str) -> str:
    """Apply YouTube suffix noise removal to the song segment only."""
    t = segment.strip()
    for _ in range(4):
        cleaned = _YT_NOISE.sub("", t).strip(" -|")
        if cleaned == t:
            break
        t = cleaned
    t = t.strip()
    return t if len(t) >= 2 else segment.strip()


def _clean_title(raw_title: str, artist: str) -> str:
    t = raw_title.strip()

    if artist:
        if artist not in _ARTIST_PREFIX_RE_CACHE:
            _ARTIST_PREFIX_RE_CACHE[artist] = re.compile(
                rf'^{re.escape(artist.strip())}\s*[-–]\s*',
                re.IGNORECASE,
            )
        t = _ARTIST_PREFIX_RE_CACHE[artist].sub('', t)

    for _ in range(4):
        cleaned = _YT_NOISE.sub('', t).strip(' -|')
        if cleaned == t:
            break
        t = cleaned

    t = t.strip()
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
    s = s.lower().translate(_ACCENT_MAP)
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"[\s]+", "-", s.strip())
    s = re.sub(r"-+", "-", s)
    return s


def _discovery_credits(raw_title: str, meta_artist: str) -> tuple[str, str]:
    """
    yt-dlp often sets artist to the YouTube channel, not the credited performer.
    When the title looks like 'Performer - Song', use that for search + direct slug
    if channel slugs do not match the opening credits.
    """
    t0 = _YT_PIPE_TRAILER.sub("", raw_title.strip()).strip()
    ma = meta_artist.strip()
    m = _TITLE_ARTIST_SPLIT.match(t0)
    if not m:
        ct = _clean_title(raw_title, ma)
        return (ma, ct) if ma else ("", ct)

    left, right = m.group(1).strip(), m.group(2).strip()
    track = _clean_track_segment(right)
    if not track or len(track) < 2:
        track = _clean_title(raw_title, ma)

    if not ma:
        return (left, track)

    sl_m, sl_l = _slugify(ma), _slugify(left)
    if not sl_l:
        return (ma, _clean_title(raw_title, ma))
    if not sl_m:
        return (left, track)

    pr = fuzz.partial_ratio(sl_m, sl_l)
    if pr >= 85 or sl_m == sl_l or (len(sl_m) >= 4 and sl_l.startswith(sl_m + "-")):
        return (ma, track)
    return (left, track)


# ---------------------------------------------------------------------------
# HTTP + anti-bot helpers
# ---------------------------------------------------------------------------

def _response_byte_length(text: str) -> int:
    return len(text.encode("utf-8", errors="replace"))


async def _http_get(
    session: AsyncSession,
    url: str,
    *,
    label: str,
) -> tuple[Optional[Any], str]:
    """
    GET url rotating impersonate profiles on 403/429 only.
    Returns (response, impersonate_used). response is None if all profiles failed.
    """
    last_imp = IMPERSONATE_ORDER[-1]
    for imp in IMPERSONATE_ORDER:
        last_imp = imp
        try:
            r = await session.get(url, impersonate=imp, timeout=45)
            text = r.text or ""
            nbytes = _response_byte_length(text)
            final_u = str(getattr(r, "url", "") or url)
            log.debug(
                "%s GET status=%s bytes=%d impersonate=%s url=%s final_url=%s",
                label,
                r.status_code,
                nbytes,
                imp,
                url[:120],
                final_u[:120],
            )

            if r.status_code == 404:
                return r, imp

            if r.status_code in (403, 429):
                log.debug("%s retry next impersonate after HTTP %s", label, r.status_code)
                continue

            if r.status_code not in (200, 202):
                return r, imp

            return r, imp
        except Exception as exc:
            log.warning("%s GET error impersonate=%s: %s", label, imp, exc)
            continue

    return None, last_imp


async def _http_post_form(
    session: AsyncSession,
    url: str,
    form: dict[str, str],
    *,
    label: str,
) -> tuple[Optional[Any], str]:
    """POST application/x-www-form-urlencoded; same impersonation rotation as GET."""
    last_imp = IMPERSONATE_ORDER[-1]
    for imp in IMPERSONATE_ORDER:
        last_imp = imp
        try:
            r = await session.post(url, data=form, impersonate=imp, timeout=45)
            text = r.text or ""
            nbytes = _response_byte_length(text)
            final_u = str(getattr(r, "url", "") or url)
            log.debug(
                "%s POST status=%s bytes=%d impersonate=%s final_url=%s",
                label,
                r.status_code,
                nbytes,
                imp,
                final_u[:120],
            )

            if r.status_code == 404:
                return r, imp

            if r.status_code in (403, 429):
                log.debug("%s POST retry next impersonate after HTTP %s", label, r.status_code)
                continue

            if r.status_code not in (200, 202):
                return r, imp

            return r, imp
        except Exception as exc:
            log.warning("%s POST error impersonate=%s: %s", label, imp, exc)
            continue

    return None, last_imp


# ---------------------------------------------------------------------------
# SERP parsing
# ---------------------------------------------------------------------------

def _unwrap_ddg_href(href: str) -> str:
    if "duckduckgo.com/l/?uddg=" in href or "uddg=" in href:
        try:
            part = href.split("uddg=")[1].split("&")[0]
            return urllib.parse.unquote(part)
        except IndexError:
            return href
    return href


def _normalize_letras_url(href: str) -> Optional[str]:
    href = href.strip()
    if not href.startswith("http"):
        return None
    if "letras.mus.br" not in href:
        return None
    parsed = urllib.parse.urlparse(href)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc not in ("www.letras.mus.br", "letras.mus.br"):
        return None
    return urllib.parse.urlunparse(parsed._replace(query="", fragment=""))


def _dedupe_candidates(raw: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for c in raw:
        key = c["url"].lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _parse_ddg_result_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    raw: list[dict] = []
    nodes = soup.select("a.result__url")
    if not nodes:
        nodes = soup.select("a.result__a")
    log.debug(
        "DDG parser: result anchors count=%d (result__url/result__a) html_len=%d",
        len(nodes),
        len(html),
    )

    for a in nodes:
        href = (a.get("href") or "").strip()
        text = a.get_text(strip=True)
        href = _unwrap_ddg_href(href)
        norm = _normalize_letras_url(href)
        if norm:
            raw.append({"url": norm, "text": text})

    if not raw:
        for a in soup.select('a[href*="letras.mus.br"]'):
            href = _unwrap_ddg_href((a.get("href") or "").strip())
            norm = _normalize_letras_url(href)
            if norm:
                raw.append({"url": norm, "text": a.get_text(strip=True)})

    if not raw:
        raw = _bing_regex_letras_urls(html)
        log.debug("DDG regex fallback extracted=%d", len(raw))

    deduped = _dedupe_candidates(raw)
    log.debug("DDG raw=%d deduped=%d", len(raw), len(deduped))
    return deduped


def _unwrap_bing_href(href: str) -> str:
    if "bing.com/ck/a" not in href and "/ck/a?" not in href:
        return href
    parsed = urllib.parse.urlparse(href)
    qs = urllib.parse.parse_qs(parsed.query)
    for key in ("u", "p"):
        vals = qs.get(key)
        if not vals:
            continue
        v = vals[0]
        try:
            if v.startswith("a1"):
                pad = "=" * (-len(v[2:]) % 4)
                dec = base64.urlsafe_b64decode(v[2:] + pad).decode("utf-8", errors="replace")
                if dec.startswith("http"):
                    return dec
        except Exception:
            pass
        dec2 = urllib.parse.unquote(v)
        if "letras.mus.br" in dec2:
            return dec2
    return href


_BING_LETRAS_HREF_RE = re.compile(
    r'https?://(?:www\.)?letras\.mus\.br/[^"\'\s<>]+/[^"\'\s<>]+/?',
    re.IGNORECASE,
)


def _html_for_url_regex(html: str) -> str:
    """Normalize JSON-escaped URLs and HTML entities so regex can match."""
    t = html.replace(r"\/", "/")
    t = html_module.unescape(t)
    return t


def _bing_regex_letras_urls(html: str) -> list[dict]:
    raw: list[dict] = []
    hay = _html_for_url_regex(html)
    for m in _BING_LETRAS_HREF_RE.finditer(hay):
        u = m.group(0).rstrip("/").split("?")[0]
        if u.lower().endswith((".png", ".jpg", ".gif", ".js", ".css")):
            continue
        norm = _normalize_letras_url(u)
        if norm:
            raw.append({"url": norm, "text": ""})
    return raw


def _parse_bing_result_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    raw: list[dict] = []
    items = soup.select("li.b_algo")
    if not items:
        items = soup.select("div.b_algo")
    log.debug(
        "Bing parser: b_algo count=%d (li+div) html_len=%d",
        len(items),
        len(html),
    )

    for li in items:
        href = ""
        text = ""
        h2a = li.select_one("h2 a")
        if h2a and h2a.get("href"):
            href = _unwrap_bing_href((h2a.get("href") or "").strip())
            text = h2a.get_text(strip=True)
        if not href or "letras.mus.br" not in href:
            for a in li.select("a[href*='letras.mus.br']"):
                cand = _unwrap_bing_href((a.get("href") or "").strip())
                if "bing.com/ck" in cand and "letras.mus.br" not in cand:
                    continue
                if "letras.mus.br" in cand:
                    href = cand
                    text = text or a.get_text(strip=True)
                    break
        if not href or "letras.mus.br" not in href:
            cite = li.select_one("cite")
            if cite:
                c = cite.get_text(strip=True)
                if "letras.mus.br" in c:
                    c = c.split()[0]
                    if not c.startswith("http"):
                        href = "https://" + c.lstrip("/")
                    else:
                        href = c
                    text = text or href

        href = _unwrap_bing_href(href)
        norm = _normalize_letras_url(href)
        if norm:
            raw.append({"url": norm, "text": text})

    if not raw:
        raw = _bing_regex_letras_urls(html)
        log.debug("Bing regex fallback extracted=%d", len(raw))

    deduped = _dedupe_candidates(raw)
    log.debug("Bing raw=%d deduped=%d", len(raw), len(deduped))
    return deduped


async def _direct_letras_slug_probe(
    session: AsyncSession,
    artist: str,
    clean_title: str,
) -> list[dict]:
    """
    When SERPs return no links (blocked/rate-limited), probe the canonical
    https://www.letras.mus.br/<artist-slug>/<title-slug>/ URL built the same
    way as _choose_candidate scoring expects.
    """
    a = _slugify(artist)
    t = _slugify(clean_title)
    if len(a) < 2 or len(t) < 2:
        return []

    url = f"https://www.letras.mus.br/{a}/{t}/"
    log.debug("discover_direct probing %s", url)
    r, imp = await _http_get(session, url, label="discover_direct")
    log.debug("discover_direct status=%s impersonate=%s", getattr(r, "status_code", None), imp)

    if r is None or r.status_code != 200:
        return []

    body = (r.text or "").lower()
    if "lyric-original" not in body and "cnt-letra" not in body:
        return []

    final_u = str(getattr(r, "url", "") or url).strip()
    norm = _normalize_letras_url(final_u) or _normalize_letras_url(url)
    if not norm:
        return []
    return [{"url": norm, "text": clean_title}]


async def _discover_candidates_http(
    session: AsyncSession,
    query: str,
    ddg_search_url: str,
    *,
    artist: str,
    clean_title: str,
) -> tuple[list[dict], dict]:
    """
    Returns (candidates, meta) where meta holds discover_backend, statuses, counts, etc.
    """
    meta: dict = {
        "discover_backend": None,
        "discover_http_status": None,
        "response_bytes": 0,
        "impersonate_used": None,
        "bing_fallback_used": False,
        "raw_candidate_count": 0,
    }

    await _human_delay(1.5, 3.0)

    r, imp = await _http_get(session, ddg_search_url, label="discover_ddg_get")
    meta["impersonate_used"] = imp

    candidates: list[dict] = []
    if r is not None:
        text = r.text or ""
        meta["discover_http_status"] = r.status_code
        meta["response_bytes"] = _response_byte_length(text)
        if r.status_code in (200, 202):
            candidates = _parse_ddg_result_html(text)
            meta["discover_backend"] = "ddg"
            meta["raw_candidate_count"] = len(candidates)

    if not candidates:
        log.debug("DDG GET yielded no candidates; trying DDG HTML POST (form q=)")
        rp, imp_post = await _http_post_form(
            session,
            DDG_HTML_FORM,
            {"q": query},
            label="discover_ddg_post",
        )
        meta["impersonate_used"] = imp_post
        if rp is not None:
            textp = rp.text or ""
            meta["discover_http_status"] = rp.status_code
            meta["response_bytes"] = _response_byte_length(textp)
            if rp.status_code in (200, 202):
                candidates = _parse_ddg_result_html(textp)
                meta["discover_backend"] = "ddg"
                meta["raw_candidate_count"] = len(candidates)
                log.debug(
                    "DDG POST status=%s result_anchors_parsed -> raw_candidates=%d",
                    rp.status_code,
                    len(candidates),
                )

    if candidates:
        log.info(
            "Lyrics discover backend=ddg status=%s raw_candidates=%d impersonate=%s",
            meta["discover_http_status"],
            len(candidates),
            meta["impersonate_used"],
        )
        return candidates, meta

    meta["bing_fallback_used"] = True
    bing_q = urllib.parse.quote_plus(query)
    bing_url = BING_SEARCH.format(query=bing_q)
    log.debug("Discover fallback to Bing url=%s", bing_url[:100])

    await _human_delay(1.0, 2.0)

    r2, imp2 = await _http_get(session, bing_url, label="discover_bing")
    meta["impersonate_used"] = imp2

    if r2 is not None:
        text2 = r2.text or ""
        meta["discover_http_status"] = r2.status_code
        meta["response_bytes"] = _response_byte_length(text2)
        if r2.status_code in (200, 202):
            candidates = _parse_bing_result_html(text2)
            meta["discover_backend"] = "bing"
            meta["raw_candidate_count"] = len(candidates)

    if not candidates:
        log.debug("SERP empty; probing direct letras slug URL")
        direct = await _direct_letras_slug_probe(session, artist, clean_title)
        if direct:
            candidates = direct
            meta["discover_backend"] = "direct_slug"
            meta["discover_http_status"] = 200
            meta["response_bytes"] = 0
            meta["raw_candidate_count"] = len(direct)
            meta["bing_fallback_used"] = True

    log.info(
        "Lyrics discover backend=%s status=%s raw_candidates=%d bing_fallback=%s impersonate=%s",
        meta["discover_backend"],
        meta["discover_http_status"],
        len(candidates),
        meta["bing_fallback_used"],
        meta["impersonate_used"],
    )
    return candidates, meta


# ---------------------------------------------------------------------------
# Candidate filtering + scoring
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

        if len(segments) < 2:
            continue

        if segments[0] in BLOCKED_FIRST_SEGMENTS:
            continue

        if segments[1] in BLOCKED_SECOND_SEGMENTS:
            continue

        if any(url.endswith(s) for s in BLOCKED_SUFFIXES):
            continue

        combined = (c["text"] + " " + url).lower()
        if any(bt in combined for bt in BLOCKED_TERMS):
            continue

        filtered.append(c)

    return filtered


def _choose_candidate(candidates: list[dict], clean_title: str, artist: str) -> str:
    title_slug = _slugify(clean_title)
    artist_slug = _slugify(artist)

    log.debug("Slug targets: title=%r artist=%r", title_slug, artist_slug)

    best_url = candidates[0]["url"]
    best_score = -1.0

    for c in candidates:
        parsed = urllib.parse.urlparse(c["url"])
        segments = [s for s in parsed.path.strip("/").split("/") if s]
        if len(segments) < 2:
            continue

        seg_artist = segments[0]
        seg_song = segments[1]

        artist_score = fuzz.ratio(artist_slug, seg_artist) / 100.0

        if seg_song.isdigit():
            score = artist_score * 0.5 + 0.2
        else:
            title_score = fuzz.ratio(title_slug, seg_song) / 100.0
            score = title_score * 0.6 + artist_score * 0.4

        log.debug(
            "Candidate score=%.2f  seg_artist=%r  seg_song=%r  url=%s",
            score, seg_artist, seg_song, c["url"],
        )

        if score > best_score:
            best_score = score
            best_url = c["url"]

    log.debug("Winner: score=%.2f  url=%s", best_score, best_url)
    return best_url


# ---------------------------------------------------------------------------
# Lyrics extraction (HTML)
# ---------------------------------------------------------------------------

def _try_selectors_bs(
    soup: BeautifulSoup,
    selectors: Optional[list[str]] = None,
) -> tuple[Optional[str], Optional[str]]:
    sels = selectors if selectors is not None else LYRICS_SELECTORS
    for sel in sels:
        nodes = soup.select(sel)
        if not nodes:
            continue
        fragments = []
        for node in nodes:
            txt = node.get_text("\n", strip=True)
            if txt:
                fragments.append(txt)
        if fragments:
            text = "\n\n".join(fragments)
            text = html_module.unescape(text)
            return text, sel
    return None, None


async def _extract_lyrics_http_with_retry(
    session: AsyncSession,
    url: str,
    *,
    is_translation: bool = False,
) -> tuple[Optional[str], dict]:
    meta: dict = {
        "http_status": None,
        "selector": None,
        "chars": 0,
        "impersonate_used": None,
    }

    for attempt in range(MAX_RETRIES):
        wait = RETRY_BACKOFF[attempt]
        if wait:
            await asyncio.sleep(wait)

        try:
            r, imp = await _http_get(session, url, label="lyrics")
            meta["impersonate_used"] = imp

            if r is None:
                log.warning("Lyrics GET exhausted impersonations %s attempt=%d", url, attempt + 1)
                continue

            meta["http_status"] = r.status_code

            if r.status_code == 404:
                log.debug("404 on %s — unavailable", url)
                return None, meta

            if r.status_code in (403, 429):
                log.warning("HTTP %d on %s — retrying (attempt %d)", r.status_code, url, attempt + 1)
                continue

            if r.status_code not in (200, 202):
                log.debug("HTTP %s on %s", r.status_code, url)
                if not is_translation:
                    log_structured("lyrics_selector_miss", url=url)
                return None, meta

            await asyncio.sleep(0.5)
            soup = BeautifulSoup(r.text or "", "html.parser")
            sels = LYRICS_SELECTORS_TRANSLATION if is_translation else LYRICS_SELECTORS
            text, sel = _try_selectors_bs(soup, sels)

            if text:
                meta["selector"] = sel
                meta["chars"] = len(text)
                log.debug("Extracted %d chars from %s selector=%s", len(text), url, sel)
                return text, meta

            log.debug("No selector matched on %s", url)
            if not is_translation:
                log_structured("lyrics_selector_miss", url=url)
            return None, meta

        except Exception as exc:
            log.warning("Error fetching %s (attempt %d): %s", url, attempt + 1, exc)

    log.warning("Exhausted retries for %s", url)
    return None, meta


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
# Top-level async entrypoint
# ---------------------------------------------------------------------------

async def scrape_lyrics(title: str, artist: str) -> dict:
    result: dict = {
        "original_text": None,
        "ptbr_text": None,
        "original_url": None,
        "ptbr_url": None,
        "has_original": False,
        "has_ptbr": False,
        "failure_reason": None,
    }

    scrape_meta: dict = {
        "discover_backend": None,
        "discover_http_status": None,
        "response_bytes": 0,
        "impersonate_used": None,
        "raw_candidate_count": 0,
        "filtered_candidate_count": 0,
        "bing_fallback_used": False,
        "lyrics_http_status": None,
        "lyrics_selector": None,
        "lyrics_chars": 0,
        "lyrics_ptbr_http_status": None,
        "lyrics_ptbr_selector": None,
        "lyrics_ptbr_chars": 0,
        "failure_stage": None,
    }

    title = _normalize(title)
    artist = _normalize(artist)

    if not title:
        result["failure_reason"] = "missing_title"
        scrape_meta["failure_stage"] = "validate"
        log_structured(
            "lyrics_scrape_end",
            query="",
            search_url="",
            chosen_url=None,
            has_original=False,
            has_ptbr=False,
            failure_reason="missing_title",
            **scrape_meta,
        )
        return result

    discover_a, clean_t = _discovery_credits(title, artist)
    log.debug(
        "Discovery credits: performer=%r track=%r (metadata_artist=%r)",
        discover_a,
        clean_t,
        artist,
    )

    query = f"site:letras.mus.br {clean_t} {discover_a}".strip()
    encoded = urllib.parse.quote_plus(query)
    search_url = DDG_SEARCH.format(query=encoded)

    log.debug("Scraping | query=%r | url=%s", query, search_url)
    log_structured("lyrics_scrape_start", query=query, search_url=search_url)

    try:
        async with AsyncSession() as session:
            candidates, dmeta = await _discover_candidates_http(
                session,
                query,
                search_url,
                artist=discover_a,
                clean_title=clean_t,
            )
            scrape_meta.update(
                discover_backend=dmeta.get("discover_backend"),
                discover_http_status=dmeta.get("discover_http_status"),
                response_bytes=dmeta.get("response_bytes", 0),
                impersonate_used=dmeta.get("impersonate_used"),
                raw_candidate_count=dmeta.get("raw_candidate_count", 0),
                bing_fallback_used=dmeta.get("bing_fallback_used", False),
            )

            if not candidates:
                result["failure_reason"] = "discover_no_candidates"
                scrape_meta["failure_stage"] = "discover"
                log.info("Lyrics scrape failed: discover_no_candidates query=%r", query)
                log_structured(
                    "lyrics_scrape_end",
                    query=query,
                    search_url=search_url,
                    chosen_url=None,
                    has_original=False,
                    has_ptbr=False,
                    failure_reason=result["failure_reason"],
                    **scrape_meta,
                )
                return result

            filtered = _filter_candidates(candidates)
            scrape_meta["filtered_candidate_count"] = len(filtered)
            log.debug("Filtered candidates: %d", len(filtered))
            _log_top_candidates(filtered)

            if not filtered:
                result["failure_reason"] = "all_candidates_filtered"
                scrape_meta["failure_stage"] = "filter"
                log.info("Lyrics scrape failed: all_candidates_filtered query=%r", query)
                log_structured(
                    "lyrics_scrape_end",
                    query=query,
                    search_url=search_url,
                    chosen_url=None,
                    has_original=False,
                    has_ptbr=False,
                    failure_reason=result["failure_reason"],
                    **scrape_meta,
                )
                return result

            chosen_url = _choose_candidate(filtered, clean_t, discover_a)
            result["original_url"] = chosen_url

            await _human_delay(*DELAY_AFTER_SEARCH)
            orig_text, om = await _extract_lyrics_http_with_retry(session, chosen_url)
            scrape_meta["lyrics_http_status"] = om.get("http_status")
            scrape_meta["lyrics_selector"] = om.get("selector")
            scrape_meta["lyrics_chars"] = om.get("chars", 0)
            if orig_text:
                result["original_text"] = orig_text
                result["has_original"] = True

            base = chosen_url.rstrip("/")
            ptbr_url = base + "/traducao.html"
            result["ptbr_url"] = ptbr_url

            await _human_delay(*DELAY_BEFORE_PTBR)
            ptbr_text, pm = await _extract_lyrics_http_with_retry(
                session, ptbr_url, is_translation=True
            )
            scrape_meta["lyrics_ptbr_http_status"] = pm.get("http_status")
            scrape_meta["lyrics_ptbr_selector"] = pm.get("selector")
            scrape_meta["lyrics_ptbr_chars"] = pm.get("chars", 0)
            if ptbr_text:
                result["ptbr_text"] = ptbr_text
                result["has_ptbr"] = True

    except Exception as exc:
        log.warning("Scraper unexpected error: %s", exc)
        result["failure_reason"] = str(exc)
        scrape_meta["failure_stage"] = "exception"

    log_structured(
        "lyrics_scrape_end",
        query=query,
        search_url=search_url,
        chosen_url=result["original_url"],
        has_original=result["has_original"],
        has_ptbr=result["has_ptbr"],
        failure_reason=result["failure_reason"],
        **scrape_meta,
    )

    if result["failure_reason"]:
        log.info(
            "Lyrics scrape done failure=%s discover=%s filtered=%d",
            result["failure_reason"],
            scrape_meta.get("discover_backend"),
            scrape_meta.get("filtered_candidate_count", 0),
        )
    else:
        log.info(
            "Lyrics scrape OK discover=%s original_chars=%d ptbr_chars=%d",
            scrape_meta.get("discover_backend"),
            scrape_meta.get("lyrics_chars", 0),
            scrape_meta.get("lyrics_ptbr_chars", 0),
        )

    return result


def scrape_lyrics_sync(title: str, artist: str) -> dict:
    """Synchronous wrapper — runs the async scraper in a fresh event loop."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(scrape_lyrics(title, artist))
