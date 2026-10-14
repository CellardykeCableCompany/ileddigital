"""
Update publications.html from Jon's two Pure research portals.

Runs once a week on GitHub (see .github/workflows/publications.yml),
or by hand with:  python3 tools/update_publications.py

What it does:
  1. Reads the publication feeds from Northumbria and Dundee. Each feed
     only lists work done at that university.
  2. Merges them, dropping anything that appears in both.
  3. Looks up DOIs in OpenAlex (an open research database), so titles
     can link to the published paper. If that lookup fails, titles link
     to the Pure record instead.
  4. Rewrites the list between the START and END markers in
     publications.html, newest first. Nothing else on the page changes.

If either feed can't be read, it stops without touching the page, so a
bad week never wipes the list.

Uses only Python's standard library: there's nothing to install.
"""

import html
import json
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

FEEDS = [
    "https://researchportal.northumbria.ac.uk/en/persons/jon-rogers/publications/?format=rss",
    "https://discovery.dundee.ac.uk/en/persons/jon-rogers/publications/?format=rss",
]
ORCID = "0000-0002-9735-3675"
PAGE = Path(__file__).resolve().parent.parent / "publications.html"
START = "<!-- PUBLICATIONS START -->"
END = "<!-- PUBLICATIONS END -->"
AGENT = "ileddigital.net publications updater (https://www.ileddigital.net)"
DC = "{http://purl.org/dc/elements/1.1/}"


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def key(title):
    """A rough fingerprint of a title, for spotting the same work twice."""
    return re.sub(r"[^a-z0-9]", "", title.lower())[:60]


class Rendering(HTMLParser):
    """Pulls the parts out of one Pure entry: title, link, authors,
    date and the details after the date (venue, pages, publisher)."""

    def __init__(self):
        super().__init__()
        self.title, self.link, self.date = "", "", ""
        self.before, self.after = [], []
        self.in_title = self.in_date = self.in_type = self.in_translation = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        cls = attrs.get("class", "")
        if tag == "h3":
            self.in_title = True
        elif self.in_title and tag == "a" and not self.link:
            self.link = attrs.get("href", "")
        elif tag == "span" and cls == "date":
            self.in_date = True
        elif tag == "span" and "translated_title" in cls:
            self.in_translation = True   # skip Pure's "Translated title" line
        elif tag == "p" and "type" in cls:
            self.in_type = True

    def handle_endtag(self, tag):
        if tag == "h3":
            self.in_title = False
        elif tag == "span" and self.in_translation:
            self.in_translation = False
        elif tag == "span" and self.in_date:
            self.in_date = False
        elif tag == "p":
            self.in_type = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.in_date:
            self.date += data
        elif self.in_type or self.in_translation:
            pass
        elif self.date:
            self.after.append(data)
        else:
            self.before.append(data)


def tidy(text):
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+,", ",", text)          # "Marshall , J." -> "Marshall, J."
    return text.strip(" ,")


def full_stop(text):
    """End with a full stop, unless it already ends with . ? or !"""
    return text if text.endswith((".", "?", "!")) else text + "."


def read_feed(url):
    root = ET.fromstring(fetch(url))
    items = []
    for item in root.iter("item"):
        part = Rendering()
        part.feed(item.findtext("description") or "")
        title = tidy(part.title or item.findtext("title") or "")
        if not title:
            continue
        sort_date = (item.findtext(DC + "date") or "")[:10]
        items.append({
            "title": title,
            "link": part.link or item.findtext("link") or "",
            "authors": tidy("".join(part.before)),
            "date": tidy(part.date),
            "details": tidy("".join(part.after)),
            "sort": sort_date,
            "year": sort_date[:4],
        })
    return items


def doi_lookup():
    """Title fingerprint -> DOI address, from OpenAlex. Empty if it fails."""
    found, cursor = {}, "*"
    try:
        while cursor:
            url = ("https://api.openalex.org/works?per-page=100&cursor=" + cursor +
                   "&filter=author.orcid:" + ORCID)
            data = json.loads(fetch(url))
            for work in data["results"]:
                if work.get("doi") and work.get("title"):
                    found.setdefault(key(work["title"]), work["doi"])
            cursor = data["meta"].get("next_cursor") if data["results"] else None
    except Exception as problem:
        print("OpenAlex lookup skipped:", problem)
    return found


def entry_html(p):
    e = html.escape
    title = '<a href="%s">%s</a>' % (e(p["href"], quote=True), e(p["title"]))
    parts = [e(p["authors"]) + ("," if p["authors"] else ""), full_stop(e(p["date"])),
             title + ("" if p["title"].endswith((".", "?", "!")) else ".")]
    if p["details"]:
        parts.append(full_stop(e(p["details"])))
    text = " ".join(x for x in parts if x.strip(" ,."))
    return ('        <li><span class="when">%s</span><span class="what">%s</span></li>'
            % (e(p["year"]), text))


def main():
    works = {}
    for url in FEEDS:
        try:
            items = read_feed(url)
        except Exception as problem:
            sys.exit("Stopping, page unchanged. Could not read %s: %s" % (url, problem))
        if not items:
            sys.exit("Stopping, page unchanged. No entries in " + url)
        print(len(items), "entries from", url.split("/")[2])
        for p in items:
            k = key(p["title"])
            # Keep whichever copy has more detail.
            if k not in works or len(p["details"]) > len(works[k]["details"]):
                works[k] = p

    dois = doi_lookup()
    for k, p in works.items():
        p["href"] = dois.get(k) or p["link"]

    ordered = sorted(works.values(), key=lambda p: (p["sort"], p["title"]), reverse=True)
    block = "\n".join(entry_html(p) for p in ordered)

    page = PAGE.read_text(encoding="utf-8")
    if START not in page or END not in page:
        sys.exit("Stopping: publications.html is missing the START/END markers.")
    before = page.split(START)[0]
    after = page.split(END)[1]
    PAGE.write_text(before + START + "\n" + block + "\n        " + END + after, encoding="utf-8")
    print(len(ordered), "publications written,",
          sum(1 for p in ordered if p["href"].startswith("https://doi.org")), "with DOI links")


if __name__ == "__main__":
    main()
