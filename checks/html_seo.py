from __future__ import annotations

import concurrent.futures
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


def _fetch(session: requests.Session, url: str, timeout: int) -> requests.Response:
    return session.get(url, timeout=timeout, allow_redirects=True)


def _link_status(session: requests.Session, url: str, timeout: int) -> tuple[str, int | None]:
    try:
        r = session.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code in {403, 405} or r.status_code >= 500:
            r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
        return url, r.status_code
    except Exception:
        try:
            r = session.get(url, timeout=timeout, allow_redirects=True, stream=True)
            return url, r.status_code
        except Exception:
            return url, None


def run(url: str, config: dict[str, Any]) -> dict[str, Any]:
    settings = config["settings"]
    timeout = int(settings.get("request_timeout_seconds", 15))
    max_links = int(settings.get("max_internal_links", 30))
    headers = {"User-Agent": settings.get("user_agent", "Mozilla/5.0")}
    session = requests.Session()
    session.headers.update(headers)
    try:
        r = _fetch(session, url, timeout)
        html = r.text
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        meta_desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
        canonical = soup.find("link", rel=lambda x: x and "canonical" in [i.lower() for i in (x if isinstance(x, list) else [x])])
        canonical_href = canonical.get("href", "").strip() if canonical else ""
        h1s = soup.find_all("h1")
        headings = [tag.name for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
        images = soup.find_all("img")
        missing_alt = sum(1 for img in images if img.get("alt") is None)
        og_tags = len(soup.find_all("meta", attrs={"property": lambda x: x and x.startswith("og:")}))
        twitter_tags = len(soup.find_all("meta", attrs={"name": lambda x: x and x.startswith("twitter:")}))
        jsonld_types: list[str] = []
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            text = tag.string or tag.get_text(" ", strip=True)
            for known in ["Product", "Organization", "BreadcrumbList", "WebSite", "LocalBusiness"]:
                if known in text and known not in jsonld_types:
                    jsonld_types.append(known)
        viewport = bool(soup.find("meta", attrs={"name": lambda x: x and x.lower() == "viewport"}))
        base = r.url
        host = urlparse(base).netloc
        internal: list[str] = []
        for a in soup.find_all("a", href=True):
            target = urljoin(base, a["href"].strip())
            p = urlparse(target)
            if p.scheme in {"http", "https"} and p.netloc == host:
                clean = target.split("#", 1)[0]
                if clean not in internal:
                    internal.append(clean)
            if len(internal) >= max_links:
                break
        broken: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, max(1, len(internal)))) as ex:
            for link, status in ex.map(lambda u: _link_status(session, u, timeout), internal):
                if status is None or status >= 400:
                    broken.append({"url": link, "status": status})

        robots_url = urljoin(base, "/robots.txt")
        sitemap_url = urljoin(base, "/sitemap.xml")
        try:
            rr = session.get(robots_url, timeout=timeout)
            robots_ok = rr.status_code < 400 and bool(rr.text.strip())
        except Exception:
            robots_ok = False
        try:
            sr = session.get(sitemap_url, timeout=timeout)
            sitemap_ok = sr.status_code < 400 and ("<urlset" in sr.text or "<sitemapindex" in sr.text)
        except Exception:
            sitemap_ok = False

        http_url = "http://" + urlparse(base).netloc + urlparse(base).path
        try:
            hr = session.get(http_url, timeout=timeout, allow_redirects=True)
            http_to_https = urlparse(hr.url).scheme == "https"
            redirect_chain_length = len(hr.history)
        except Exception:
            http_to_https = None
            redirect_chain_length = None

        return {
            "status": "ok",
            "final_url": r.url,
            "http_status": r.status_code,
            "page_size_bytes": len(r.content),
            "title": title,
            "title_length": len(title),
            "title_missing": not bool(title),
            "meta_description": meta_desc,
            "meta_description_length": len(meta_desc),
            "meta_description_missing": not bool(meta_desc),
            "canonical": canonical_href,
            "canonical_missing": not bool(canonical_href),
            "h1_count": len(h1s),
            "heading_sequence": headings[:50],
            "image_count": len(images),
            "images_missing_alt": missing_alt,
            "open_graph_tags": og_tags,
            "twitter_tags": twitter_tags,
            "jsonld_types": jsonld_types,
            "viewport": viewport,
            "robots_txt": robots_ok,
            "sitemap_xml": sitemap_ok,
            "sampled_internal_links": len(internal),
            "broken_internal_links": broken,
            "broken_internal_link_count": len(broken),
            "http_to_https": http_to_https,
            "redirect_chain_length": redirect_chain_length,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        session.close()
