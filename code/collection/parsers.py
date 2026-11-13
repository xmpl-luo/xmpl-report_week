import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from html import unescape
from urllib.parse import urljoin, urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from common.periods import SHANGHAI


def normalize_url(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def published_day(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = parsedate_to_datetime(str(value))
        except (ValueError, TypeError):
            return None
    return (dt.astimezone(SHANGHAI) if dt.tzinfo else dt).date().isoformat()


class Page(HTMLParser):
    def __init__(self, html, url=""):
        super().__init__(convert_charrefs=True)
        self.url, self.links, self.feeds, self.meta, self.jsonld = url, [], [], {}, []
        self.parts, self.main_parts, self.title_parts = [], [], []
        self.stack, self.script = [], []
        self.in_json = False
        self.in_date, self.display_date = False, []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "p" and (attrs.get("data-testid") == "contributors-date" or "Contributors-Date" in attrs.get("class", "").split()):
            self.in_date = True
        if tag == "a" and attrs.get("href"):
            self.links.append(urljoin(self.url, attrs["href"]))
        if tag == "link" and "rss" in attrs.get("type", ""):
            self.feeds.append(urljoin(self.url, attrs.get("href", "")))
        if tag == "meta":
            self.meta[attrs.get("property", attrs.get("name", ""))] = attrs.get("content", "")
        if tag == "script":
            self.in_json = attrs.get("type") == "application/ld+json"
            self.script = []
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "p":
            self.in_date = False
        if tag == "script" and self.in_json:
            try:
                self.jsonld.append(json.loads("".join(self.script)))
            except json.JSONDecodeError:
                pass
            self.in_json = False
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if self.in_date:
            self.display_date.append(data)
        if self.in_json:
            self.script.append(data)
        if any(t in self.stack for t in ("script", "style", "nav", "footer", "header", "noscript")):
            return
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text)
            if "article" in self.stack or "main" in self.stack:
                self.main_parts.append(text)
            if "title" in self.stack:
                self.title_parts.append(text)

    def article(self):
        def walk(obj):
            if isinstance(obj, dict):
                yield obj
                for value in obj.values():
                    yield from walk(value)
            elif isinstance(obj, list):
                for value in obj:
                    yield from walk(value)
        nodes = [n for obj in self.jsonld for n in walk(obj)
                 if any(t in str(n.get("@type", "")) for t in ("Article", "BlogPosting", "NewsArticle"))]
        node = nodes[0] if nodes else {}
        # Game Developer podcast pages put their date in a dedicated contributor
        # header, without Article JSON-LD. Do not search arbitrary body dates.
        header_date = None
        if urlsplit(self.url).hostname == "www.gamedeveloper.com" and self.display_date:
            try:
                header_date = datetime.strptime("".join(self.display_date).strip(), "%B %d, %Y").date().isoformat()
            except ValueError:
                pass
        return {"title": unescape(node.get("headline") or self.meta.get("og:title") or " ".join(self.title_parts)),
                "published": published_day(node.get("datePublished") or self.meta.get("article:published_time") or self.meta.get("date")) or header_date,
                "text": node.get("articleBody") or "\n".join(self.main_parts or self.parts),
                "url": self.url}


def feed_entries(xml, base):
    root = ET.fromstring(xml)
    items = []
    for node in root.iter():
        if node.tag.split("}")[-1] not in ("item", "entry"):
            continue
        fields = {child.tag.split("}")[-1]: child for child in node}
        def value(key):
            return "".join(fields[key].itertext()).strip() if key in fields else ""
        link = value("link")
        if not link and "link" in fields:
            link = fields["link"].get("href", "")
        if not link:
            continue
        body = value("encoded") or value("content") or value("description") or value("summary")
        items.append({"title": value("title"), "url": urljoin(base, link),
                      "published": published_day(value("pubDate") or value("published")),
                      "text": "\n".join(Page(body).parts)})
    return items


def sitemap_links(xml):
    root = ET.fromstring(xml)
    nested = root.tag.split("}")[-1] == "sitemapindex"
    links = [n.text for child in root for n in child if n.tag.split("}")[-1] == "loc" and n.text]
    return nested, links


def sitemap_items(xml):
    root = ET.fromstring(xml)
    items = []
    for child in root:
        fields = {n.tag.split("}")[-1]:n.text for n in child}
        if fields.get("loc"):
            items.append({"url":fields["loc"], "date_hint":(fields.get("lastmod") or "")[:10]})
    return items

