"""Build docs/index.html (GitHub Pages "link in bio" page) from trends/affiliate.json.

usage: python3 trends/links.py add <video-id> "<Video title>" "<Product label>" "<amazon search words>"
       python3 trends/links.py build
Links are Amazon search links with the partner tag, e.g. https://www.amazon.com/s?k=wand+cat+toy&tag=xyz-20
"""
import json, sys, os, html, datetime, urllib.parse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "trends", "affiliate.json")


def load(): return json.load(open(CFG))


def save(c): json.dump(c, open(CFG, "w"), ensure_ascii=False, indent=1)


def url(c, q): return f"{c['store']}/s?k={urllib.parse.quote_plus(q)}&tag={c['amazon_tag']}"


def build(c):
    rows = "".join(
        f'<a class="card" href="{html.escape(url(c, l["query"]))}" rel="sponsored noopener" target="_blank">'
        f'<span class="v">{html.escape(l["video"])}</span><span class="p">{html.escape(l["label"])} →</span></a>'
        for l in reversed(c["links"][-60:]))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Trends Explained – Links</title><style>
:root{{--bg:#101014;--card:#1c1c24;--fg:#fff;--mut:#a9a9b8;--acc:#ffcc00}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.4 system-ui,sans-serif}}
main{{max-width:560px;margin:0 auto;padding:24px 16px}}h1{{font-size:24px;margin:0 0 4px}}
.d{{color:var(--mut);font-size:13px;margin:0 0 20px}}
.card{{display:block;background:var(--card);border-radius:14px;padding:14px 16px;margin:0 0 10px;color:var(--fg);text-decoration:none}}
.v{{display:block;color:var(--mut);font-size:13px}}.p{{display:block;font-weight:700;color:var(--acc)}}
</style></head><body><main><h1>Trends Explained</h1>
<p class="d">Products mentioned in our videos. As an Amazon Associate I earn from qualifying purchases (affiliate links, marked as ads).</p>
{rows}<p class="d">Updated {datetime.date.today().isoformat()}</p></main></body></html>"""
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    open(os.path.join(ROOT, "docs", "index.html"), "w").write(page)


if __name__ == "__main__":
    c = load()
    if sys.argv[1] == "add":
        vid, title, label, query = sys.argv[2:6]
        c["links"] = [l for l in c["links"] if l["id"] != vid] + [{"id": vid, "video": title, "label": label, "query": query,
                                                                    "date": datetime.date.today().isoformat()}]
        save(c)
    build(c)
    print(os.path.join(ROOT, "docs", "index.html"))
