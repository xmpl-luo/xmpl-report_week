import hashlib
import json
import time
import calendar
from datetime import datetime, timezone
from urllib.parse import urlsplit

from common.http import request
from common.periods import SHANGHAI
from common.settings import CODE, RUNTIME, read_json, write_json
from .parsers import Page, feed_entries, normalize_url, sitemap_links, sitemap_items


def collect(start, end, *, selected=None, max_pages=180, refresh=False):
    sources = read_json(CODE / "config/sources.json")
    articles, audit = {}, []
    for source in sources:
        if selected and source["id"] not in selected:
            continue
        print(f"正在采集：{source['name']}", flush=True)
        record = {"source": source["name"], "errors": [], "discovered": 0, "included": 0, "unknown_date": 0}
        audit.append(record)
        if source.get("manual_only"):
            record["status"] = "requires_specific_publication_or_manual_evidence"
            continue
        candidates = {}
        hosts = set(source.get("allowed_hosts", [])) | {urlsplit(source["page"]).hostname}

        def allowed(url):
            parts = urlsplit(url)
            return (parts.scheme == "https" and parts.hostname in hosts
                    and not parts.path.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf", ".zip")))

        def fetch(url):
            cache = RUNTIME / "http" / (hashlib.sha256(url.encode()).hexdigest() + ".json")
            cached = read_json(cache)
            if cached and not refresh and time.time() - cache.stat().st_mtime < 21600:
                return cached["body"]
            time.sleep(0.3)
            body = request(url, timeout=18, retries=1)
            write_json(cache, {"url": url, "body": body})
            return body

        feeds = list(source.get("feeds", []))
        # Public publication archives preserve original post dates beyond RSS.
        if source.get("archive_api_enabled") and source["id"] == "naavik":
            origin = "https://naavik.substack.com"
            for offset in range(0, 151, 50):
                try:
                    posts = json.loads(fetch(f"{origin}/api/v1/archive?sort=new&search=&offset={offset}&limit=50"))
                    if not isinstance(posts, list) or not posts:
                        break
                    for post in posts:
                        from .parsers import published_day
                        day = published_day(post.get("post_date"))
                        link = post.get("canonical_url") or f"{origin}/p/{post['slug']}"
                        if day and start.isoformat() <= day <= end.isoformat() and allowed(link):
                            candidates[normalize_url(link)] = {"url":link, "published":day, "title":post.get("title", "")}
                    if min((str(p.get("post_date", "9999"))[:10] for p in posts), default="9999") < start.isoformat():
                        break
                except Exception as error:
                    record["errors"].append({"stage":"archive", "type":type(error).__name__})
                    break
        if source["id"] == "dof":
            try:
                listing = json.loads(fetch(source["page"] + "?format=json"))
                for post in listing.get("items", []):
                    stamp = post.get("publishOn", post.get("addedOn"))
                    day = datetime.fromtimestamp(stamp / 1000, timezone.utc).astimezone(SHANGHAI).date().isoformat() if stamp else None
                    link = "https://www.deconstructoroffun.com" + post.get("fullUrl", "")
                    if day and allowed(link):
                        candidates[normalize_url(link)] = {"url":link, "published":day, "title":post.get("title", ""), "text":"\n".join(Page(post.get("body", "")).parts)}
            except Exception as error:
                record["errors"].append({"stage":"archive", "type":type(error).__name__})
        months = {(start.year, start.month), (end.year, end.month)}
        for template in source.get("archives", []):
            feeds.extend(template.format(year=y, month=f"{m:02d}") for y, m in months)
        for url in feeds:
            try:
                for item in feed_entries(fetch(url), url):
                    if allowed(item["url"]):
                        candidates[normalize_url(item["url"])] = item
            except Exception as error:
                record["errors"].append({"stage": "feed", "url": url, "type": type(error).__name__})
        for url in [source["page"], *source.get("discovery_pages", [])]:
            try:
                for link in Page(fetch(url), url).links:
                    path = urlsplit(link).path
                    if allowed(link) and len(path.strip("/")) > 15 and not any(x in path for x in ("/tag/", "/category/", "/author/")):
                        candidates.setdefault(normalize_url(link), {"url": link})
            except Exception as error:
                record["errors"].append({"stage": "listing", "url": url, "type": type(error).__name__})
        queue = list(source.get("sitemaps", []))
        for template in source.get("archive_sitemaps", []):
            queue.extend(template.format(year=y, month=calendar.month_name[m].lower()) for y,m in months)
        visited = set()
        while queue and len(visited) < 12:
            url = queue.pop(0)
            if url in visited or not allowed(url):
                continue
            visited.add(url)
            try:
                nested, links = sitemap_links(fetch(url))
                if nested:
                    # Content sitemaps before taxonomy and product sitemaps.
                    queue.extend(sorted(links, key=lambda x: ("post" not in x and "blog" not in x, x)))
                else:
                    for item in sitemap_items(fetch(url)):
                        link = item["url"]
                        if allowed(link):
                            existing = candidates.setdefault(normalize_url(link), item)
                            existing.setdefault("date_hint", item["date_hint"])
            except Exception as error:
                record["errors"].append({"stage": "sitemap", "url": url, "type": type(error).__name__})
        record["discovered"] = len(candidates)
        # Known dates in range first, then URL-dated articles in range, then undated.
        def priority(item):
            day = item.get("published", "") or ""
            url = item["url"]
            month_hit = any(f"/{y}/{m}/" in url or f"/{y}/{m:02d}/" in url for y, m in months)
            hint = item.get("date_hint", "")
            hint_hit = start.isoformat() <= hint <= end.isoformat()
            return (0 if start.isoformat() <= day <= end.isoformat() else 1 if month_hit or hint_hit else 2)
        pending = sorted(candidates.values(), key=priority)
        record["candidate_limit"] = max_pages
        record["truncated"] = len(pending) > max_pages
        for item in pending[:max_pages]:
            day = item.get("published")
            if day and not start.isoformat() <= day <= end.isoformat():
                continue
            try:
                page = Page(fetch(item["url"]), item["url"]).article()
                day = page["published"] or day
                if not day:
                    record["unknown_date"] += 1
                    continue
                if not start.isoformat() <= day <= end.isoformat():
                    continue
                text = page["text"] if len(page["text"]) > len(item.get("text", "")) else item["text"]
                if len(text) < 150:
                    record["errors"].append({"stage":"body", "url":item["url"], "type":"InsufficientText"})
                    continue
                article = {**page, "published": day, "source": source["name"], "source_id": source["id"], "text": text, "scope": source["scope"]}
                articles[normalize_url(item["url"])] = article
                record["included"] += 1
            except Exception as error:
                record["errors"].append({"stage": "article", "url": item["url"], "type": type(error).__name__})
        record["status"] = "collected_with_limits" if record["errors"] or record["truncated"] else "collected"
        write_json(RUNTIME / "collection" / (source["id"] + ".latest.json"), {"articles":[a for a in articles.values() if a["source_id"] == source["id"]], "audit":record})
    return list(articles.values()), audit

