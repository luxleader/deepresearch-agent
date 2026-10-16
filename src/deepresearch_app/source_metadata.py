"""Read page-declared metadata without treating it as independent verification."""
import json
import re
from datetime import date, datetime
from html.parser import HTMLParser


def declared_date(value):
    if not isinstance(value, str):
        return None
    value = value.strip()
    try:
        if re.fullmatch(r"\d{4}[-/]\d{2}[-/]\d{2}", value):
            return date.fromisoformat(value.replace("/", "-")).isoformat()
        if re.match(r"^\d{4}-\d{2}-\d{2}T", value):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    return None


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.head = False
        self.hidden = 0
        self.in_title = False
        self.script = None
        self.script_parts = []
        self.title_parts = []
        self.og_title = None
        self.parts = []
        self.published = []
        self.modified = []

    def add_date(self, collection, value, basis):
        parsed = declared_date(value)
        if parsed:
            collection.append((parsed, basis))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "head":
            self.head = True
        if tag == "title":
            self.in_title = True
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag == "script":
            self.script = attrs.get("type", "").lower()
            self.script_parts = []
        if tag == "meta":
            name = (attrs.get("property") or attrs.get("name") or attrs.get("itemprop") or "").lower()
            value = attrs.get("content", "")
            if name in {"article:published_time", "citation_publication_date", "datepublished"}:
                self.add_date(self.published, value, "meta:" + name)
            if name in {"article:modified_time", "datemodified"}:
                self.add_date(self.modified, value, "meta:" + name)
            if name == "og:title" and value.strip():
                self.og_title = value.strip()
        if tag == "time":
            prop = attrs.get("itemprop", "").lower()
            if prop == "datepublished":
                self.add_date(self.published, attrs.get("datetime"), "time:datePublished")
            elif prop == "datemodified":
                self.add_date(self.modified, attrs.get("datetime"), "time:dateModified")

    def jsonld(self, item):
        if isinstance(item, list):
            for child in item:
                self.jsonld(child)
        elif isinstance(item, dict):
            types = item.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if isinstance(types, list) and any(t in {"Article", "TechArticle", "ScholarlyArticle", "NewsArticle", "BlogPosting", "Report", "WebPage"} for t in types if isinstance(t, str)):
                self.add_date(self.published, item.get("datePublished"), "jsonld:datePublished")
                self.add_date(self.modified, item.get("dateModified"), "jsonld:dateModified")
            self.jsonld(item.get("@graph"))

    def handle_endtag(self, tag):
        if tag == "head":
            self.head = False
        if tag == "title":
            self.in_title = False
        if tag == "script":
            if self.script == "application/ld+json":
                try:
                    self.jsonld(json.loads("".join(self.script_parts)))
                except (ValueError, TypeError, RecursionError):
                    pass
            self.script = None
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
        if self.script == "application/ld+json":
            self.script_parts.append(data)
        if not self.hidden and not self.head and not self.in_title and data.strip():
            self.parts.append(data.strip())

    def result(self, fallback_title):
        published = set(d for d, _ in self.published)
        modified = set(d for d, _ in self.modified)
        warnings = []
        if len(published) > 1:
            warnings.append("站点声明的发布日期冲突，时间适用性保持未知")
        if len(modified) > 1:
            warnings.append("站点声明的修改日期冲突，修改日期保持未知")
        if published or modified:
            warnings.append("日期来自站点元数据，未独立核对历史版本；修改时间不代表发布时间")
        return {"title": self.og_title or " ".join("".join(self.title_parts).split()) or fallback_title,
                "raw_content": "\n".join(self.parts)[:100000],
                "published_at": next(iter(published)) if len(published) == 1 else None,
                "modified_at": next(iter(modified)) if len(modified) == 1 else None,
                "date_basis": self.published[0][1] if len(published) == 1 else None,
                "metadata_warnings": warnings}


def parse_html(content, fallback_title):
    parser = DocumentParser()
    parser.feed(content)
    return parser.result(fallback_title)
