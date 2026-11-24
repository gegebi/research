#!/usr/bin/env python3
"""reports/*.md (와 old/*.md) 를 읽어 site/public/ 에 읽기 좋은 정적 사이트를 만든다.

- 날짜별 페이지: public/YYYY-MM-DD.html   (기존 주소 그대로)
- 목록 페이지:   public/index.html        ("지금 새로고침" 버튼 포함)
리포트 형식은 daily_science.py 가 만드는 마크다운을 그대로 따른다.
"""
import datetime as dt
import html
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUB = ROOT / "public"
SRC = [ROOT.parent / "old", ROOT.parent / "reports"]  # 뒤쪽(reports)이 같은 날짜를 덮어쓴다

WEEK = "월화수목금토일"
LANGS = [("영어권", "en", "영어"), ("중국어권", "zh", "중국어"), ("일본어권", "ja", "일본어"), ("한국어권", "ko", "한국어")]
LANG_CLASS = {k: c for k, c, _ in LANGS}

FONTS = ""

CSS = """
:root{
  color-scheme:light dark;
  --bg:#fff; --ink:#1b1b1f; --ink2:#5a5e6b; --rule:#e5e5ea; --accent:#3b5bdb; --bar:#5b7cfa; --quote:#f4f6fb;
  --btn-ink:#fff; --flag-bg:#fff1cc; --flag-ink:#6b4a00;
  --en:#5b7cfa; --zh:#e5675c; --ja:#e0a43a; --ko:#3fb68b;
  --sans:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Noto Sans KR","Malgun Gothic",system-ui,sans-serif;
}
@media (prefers-color-scheme:dark){:root{
  --bg:#17171a; --ink:#e8e8ec; --ink2:#a0a4b0; --rule:#2e3037; --accent:#8ea6ff; --bar:#5b7cfa; --quote:#22242b;
  --btn-ink:#10131f; --flag-bg:#3a2f10; --flag-ink:#f1d48a;
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:400 1rem/1.75 var(--sans);word-break:keep-all;overflow-wrap:break-word}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}
.wrap{max-width:44rem;margin:0 auto;padding:0 1rem}

/* 상단 바 */
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 90%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--rule)}
.bar .wrap{display:flex;align-items:center;gap:1rem;height:3rem}
.bar a.home{font-weight:700;font-size:.95rem;color:var(--ink);text-decoration:none;white-space:nowrap}
.bar nav{display:flex;gap:1.1rem;overflow-x:auto;scrollbar-width:none;margin-left:auto}
.bar nav::-webkit-scrollbar{display:none}
.bar nav a{font-size:.875rem;color:var(--ink2);text-decoration:none;white-space:nowrap;padding:.5rem 0}
.bar nav a:hover{color:var(--accent)}

/* 머리글 */
.head{padding:2.25rem 0 .5rem}
.date{font:700 clamp(1.75rem,6vw,2.25rem)/1.25 var(--sans);letter-spacing:-.02em;margin:0}
.date small{display:block;font:400 .875rem/1.6 var(--sans);letter-spacing:0;color:var(--ink2);margin-bottom:.2rem}
.lede{margin:1.5rem 0 0;padding:.9rem 1.25rem;background:var(--quote);border-left:4px solid var(--bar);border-radius:0 .5rem .5rem 0}
.lede p{margin:.45rem 0}

/* 언어 비율 막대 */
.mix{margin:1.5rem 0 0}
.mix .strip{display:flex;height:.4rem;border-radius:.2rem;overflow:hidden;gap:2px}
.mix .strip i{display:block;min-width:.5rem}
.mix ul{display:flex;flex-wrap:wrap;gap:.25rem 1.1rem;list-style:none;margin:.6rem 0 0;padding:0;font-size:.8125rem;color:var(--ink2)}
.mix li{display:flex;align-items:center;gap:.4rem}
.en{--c:var(--en)}.zh{--c:var(--zh)}.ja{--c:var(--ja)}.ko{--c:var(--ko)}
.strip i,.dot{background:var(--c)}
.dot{display:inline-block;width:.5rem;height:.5rem;border-radius:50%;flex:none}

/* 섹션과 기사 */
section{scroll-margin-top:3rem}
h2{font:700 1.4rem/1.4 var(--sans);letter-spacing:-.01em;margin:2.5rem 0 .25rem;padding-bottom:.4rem;border-bottom:2px solid var(--rule)}
.intro{color:var(--ink2);font-size:.9375rem;margin:.6rem 0 0}
article{padding:1.4rem 0;border-bottom:1px solid var(--rule)}
article:last-of-type{border-bottom:0}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:.25rem .6rem;font-size:.8125rem;color:var(--ink2);margin:0 0 .35rem}
.meta .dot{margin-right:-.2rem}
.flag{background:var(--flag-bg);color:var(--flag-ink);border-radius:.25rem;padding:0 .4rem;font-size:.75rem;line-height:1.6}
h3{font:700 1.1875rem/1.5 var(--sans);margin:0 0 .45rem;letter-spacing:-.01em}
h3 a{color:var(--ink);text-decoration:none}
h3 a:hover{color:var(--accent);text-decoration:underline;text-underline-offset:.2em}
article p{margin:0 0 .7rem}
.after{border-left:3px solid var(--bar);padding-left:.9rem;margin:1rem 0 .75rem}
.after b{font-weight:700;color:var(--accent);margin-right:.4rem}
.cite{font-size:.8125rem;color:var(--ink2);margin:0}

/* 글 아래 */
details{margin:2.25rem 0 0;color:var(--ink2);font-size:.875rem}
summary{cursor:pointer;padding:.5rem 0}
details ul{margin:.5rem 0 0;padding-left:1.1rem}
details li{margin:.25rem 0;word-break:break-all}
.pager{display:flex;justify-content:space-between;gap:1rem;margin:2.75rem 0 0;padding:1.25rem 0;border-top:1px solid var(--rule);font-size:.9375rem}
.pager a{text-decoration:none}
.pager a:hover{text-decoration:underline}
footer{padding:1.25rem 0 3rem;color:var(--ink2);font-size:.8125rem}

/* 목록 페이지 */
.top{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:1rem;padding:2.25rem 0 1rem}
.top h1{font:700 1.5rem/1.3 var(--sans);margin:0;letter-spacing:-.02em}
.top p{margin:.3rem 0 0;color:var(--ink2);font-size:.9375rem}
button{font:700 .9375rem var(--sans);background:var(--bar);color:#fff;border:0;border-radius:.5rem;padding:.6rem 1.1rem;cursor:pointer;min-height:2.75rem}
button:hover:not(:disabled){filter:brightness(1.1)}
button:disabled{opacity:.55;cursor:default}
#msg{flex-basis:100%;margin:0;color:var(--ink2);font-size:.875rem;min-height:1.4em}
.latest{padding:.5rem 0 1.75rem;border-bottom:2px solid var(--rule)}
.latest .read{display:inline-block;margin-top:1.25rem;font-weight:700;text-decoration:none}
.latest .read:hover{text-decoration:underline}
.days{list-style:none;margin:0;padding:0}
.days a{display:grid;grid-template-columns:8.5rem 1fr;gap:.25rem 1.25rem;padding:1rem 0;border-bottom:1px solid var(--rule);text-decoration:none;color:var(--ink)}
.days a:hover .d{color:var(--accent)}
.days .d{font-weight:700}
.days .s{color:var(--ink2);font-size:.9375rem}
.days h2{margin-top:2rem}
@media (max-width:30rem){.days a{grid-template-columns:1fr}}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto!important}}
"""


# ------------------------------------------------------------------ 파싱
def esc(s):
    return html.escape(s, quote=True)


def inline(s):
    s = esc(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', s)
    return s


def parse(md):
    doc = {"title": "", "lede": [], "sections": []}
    sec = ent = None
    in_srcs = False
    for line in md.splitlines():
        if line.startswith("# "):
            doc["title"] = line[2:].strip()
        elif line.startswith(">"):
            doc["lede"].append(line.lstrip("> ").strip())
        elif line.startswith("## "):
            sec = {"name": line[3:].strip(), "intro": [], "entries": [], "srcs": []}
            doc["sections"].append(sec)
            ent, in_srcs = None, False
        elif line.startswith("### ") and sec is not None:
            ent = {"title": line[4:].strip(), "paras": [], "after": [], "src": ""}
            sec["entries"].append(ent)
            in_srcs = False
        elif line.startswith("재조명 검색 출처") and sec is not None:
            in_srcs = True
        elif in_srcs and line.startswith("- "):
            m = re.match(r"- \[([^\]]+)\]\((https?://[^)\s]+)\)", line)
            if m:
                sec["srcs"].append((m.group(1), m.group(2)))
        elif line.startswith("출처:") and ent is not None:
            ent["src"] = line[3:].strip()
        elif line.startswith("그 후:") and ent is not None:
            ent["after"].append(line[4:].strip())
        elif line.strip():
            if ent is not None:
                ent["paras"].append(line.strip())
            elif sec is not None:
                sec["intro"].append(line.strip())
    return doc


def parse_src(src):
    """'[이름](URL) · 영어권 (본문 미확인, 제목·요약 기준)' -> (이름, URL, 언어권, 메모)"""
    m = re.match(r"\[([^\]]+)\]\((https?://[^)\s]+)\)\s*·\s*(\S+?)(?:\s*\((.*?)\))?\s*$", src)
    if not m:
        return None
    return m.group(1), m.group(2), m.group(3), m.group(4) or ""


def is_retro(sec):
    return sec["name"].startswith("5년 전")


def lang_counts(doc):
    n = {k: 0 for k, _, _ in LANGS}
    for sec in doc["sections"]:
        if is_retro(sec):
            continue
        for e in sec["entries"]:
            p = parse_src(e["src"])
            if p and p[2] in n:
                n[p[2]] += 1
    return n


def count_items(doc):
    return sum(len(s["entries"]) for s in doc["sections"] if not is_retro(s))


def date_label(d):
    return f"{d.year}년 {d.month}월 {d.day}일", WEEK[d.weekday()] + "요일"


# ------------------------------------------------------------------ 조각
def mix_html(doc):
    n = lang_counts(doc)
    total = sum(n.values())
    if not total:
        return ""
    segs = "".join(f'<i class="{LANG_CLASS[k]}" style="flex:{v}"></i>' for k, v in n.items() if v)
    legend = "".join(
        f'<li class="{c}"><span class="dot"></span>{name} {n[k]}건</li>' for k, c, name in LANGS if n[k]
    )
    return f'<div class="mix" role="group" aria-label="언어권별 기사 수"><div class="strip" aria-hidden="true">{segs}</div><ul>{legend}</ul></div>'


def entry_html(e, retro):
    p = None if retro else parse_src(e["src"])
    meta, title = "", esc(e["title"])
    if p:
        name, url, lang, note = p
        cls = LANG_CLASS.get(lang, "")
        flag = ""
        if "미확인" in note:
            flag = '<span class="flag" title="본문을 읽지 못하고 제목과 요약만으로 정리했어요">제목·요약 기준</span>'
        meta = f'<p class="meta {cls}"><span class="dot"></span><span>{esc(lang)}</span><span>{esc(name)}</span>{flag}</p>'
        title = f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{title}</a>'
    body = "".join(f"<p>{inline(x)}</p>" for x in e["paras"])
    after = "".join(f'<p class="after"><b>그 후</b>{inline(x)}</p>' for x in e["after"])
    cite = ""
    if retro and e["src"]:
        cite = f'<p class="cite">출처 {esc(e["src"])}</p>'
    elif not p and e["src"]:
        cite = f'<p class="cite">{inline(e["src"])}</p>'
    return f"<article>{meta}<h3>{title}</h3>{body}{after}{cite}</article>"


def section_html(i, sec):
    retro = is_retro(sec)
    intro = "".join(f'<p class="intro">{inline(x)}</p>' for x in sec["intro"])
    entries = "".join(entry_html(e, retro) for e in sec["entries"])
    srcs = ""
    if sec["srcs"]:
        li = "".join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener noreferrer">{esc(n)}</a></li>' for n, u in sec["srcs"])
        srcs = f"<details><summary>검색에 쓰인 출처 {len(sec['srcs'])}건</summary><ul>{li}</ul></details>"
    return f'<section id="sec{i}"><h2>{esc(sec["name"])}</h2>{intro}{entries}{srcs}</section>'


def head_html(title):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="color-scheme" content="light dark">'
            f'<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme:light)">'
            f'<meta name="theme-color" content="#17171a" media="(prefers-color-scheme:dark)">'
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml">'
            f'<link rel="apple-touch-icon" href="/apple-touch-icon.png">'
            f'<title>{esc(title)}</title>{FONTS}<style>{CSS}</style></head><body>')


# ------------------------------------------------------------------ 페이지
def report_page(day, doc, prev_day, next_day):
    ymd, wd = date_label(day)
    short = lambda n: re.sub(r"\s*\(.*\)$", "", n)
    nav = "".join(f'<a href="#sec{i}">{esc(short(s["name"]))}</a>' for i, s in enumerate(doc["sections"]))
    lede = "".join(f"<p>{inline(x)}</p>" for x in doc["lede"])
    secs = "".join(section_html(i, s) for i, s in enumerate(doc["sections"]))
    prev_l = f'<a href="{prev_day}.html">이전 리포트 {prev_day}</a>' if prev_day else "<span></span>"
    next_l = f'<a href="{next_day}.html">다음 리포트 {next_day}</a>' if next_day else "<span></span>"
    return (head_html(f"과학기술 데일리 브리핑 {day.isoformat()}")
            + f'<header class="bar"><div class="wrap"><a class="home" href="./">브리핑</a><nav aria-label="섹션">{nav}</nav></div></header>'
            + f'<main class="wrap"><div class="head"><h1 class="date"><small>{wd}</small>{ymd}</h1>'
            + (f'<div class="lede">{lede}</div>' if lede else "") + mix_html(doc) + "</div>"
            + secs + f'<nav class="pager" aria-label="다른 날짜">{prev_l}{next_l}</nav></main>'
            + '<footer class="wrap">영어, 중국어, 일본어, 한국어 매체에서 모아 한국어로 정리했어요. 기사 제목을 누르면 원문으로 이동합니다.</footer>'
            + "</body></html>")


REFRESH_JS = """
const b=document.getElementById('r'),m=document.getElementById('msg');
b.addEventListener('click',async()=>{
  b.disabled=true;m.textContent='요청하는 중이에요.';
  try{
    const x=await fetch('/api/refresh',{method:'POST'});
    if(x.ok){m.textContent='새 리포트를 만들기 시작했어요. 2~5분 뒤 이 페이지를 새로고침하면 보여요.';}
    else if(x.status===500){m.textContent='새로고침 기능이 아직 설정되지 않았어요.';}
    else{m.textContent='GitHub에 요청하지 못했어요. 잠시 뒤 다시 눌러 주세요. (오류 '+x.status+')';}
  }catch(e){m.textContent='네트워크에 연결하지 못했어요. 연결을 확인하고 다시 눌러 주세요.';}
  setTimeout(()=>{b.disabled=false},30000);
});
"""


def index_page(days, docs):
    latest = days[0]
    d0 = docs[latest]
    ymd, wd = date_label(dt.date.fromisoformat(latest))
    first = f'<p>{inline(d0["lede"][0])}</p>' if d0["lede"] else ""
    feature = (f'<div class="latest"><h2 class="date" style="margin:0"><small>{wd}</small>{ymd}</h2>'
               f'<div class="lede">{first}</div>{mix_html(d0)}'
               f'<a class="read" href="{latest}.html">오늘 리포트 읽기</a></div>')
    older = ""
    if len(days) > 1:
        rows = ""
        for d in days[1:]:
            doc = docs[d]
            ymd2, wd2 = date_label(dt.date.fromisoformat(d))
            sub = (doc["lede"][0] if doc["lede"] else "")
            sub = (sub[:80] + "…") if len(sub) > 80 else sub
            rows += (f'<li><a href="{d}.html"><span class="d">{ymd2}</span>'
                     f'<span class="s">{esc(sub)}</span></a></li>')
        older = f'<ul class="days"><li><h2>지난 리포트</h2></li>{rows}</ul>'
    return (head_html("과학기술 데일리 브리핑")
            + '<main class="wrap"><div class="top"><div><h1>과학기술 데일리 브리핑</h1>'
              '<p>전 세계 네 언어권 매체의 과학기술 소식을 매일 한국어로 정리합니다.</p></div>'
              '<button id="r" type="button">지금 새로고침</button><p id="msg" role="status"></p></div>'
            + feature + older + "</main>"
            + f"<script>{REFRESH_JS}</script></body></html>")


def main():
    mds = {}
    for d in SRC:
        for f in sorted(d.glob("*.md")):
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", f.name):
                mds[f.stem] = f
    PUB.mkdir(exist_ok=True)
    for f in PUB.glob("*.html"):
        f.unlink()
    if not mds:
        (PUB / "index.html").write_text(head_html("과학기술 데일리 브리핑")
                                        + '<main class="wrap"><div class="top"><h1>아직 리포트가 없어요</h1>'
                                          '<p>첫 리포트가 만들어지면 이곳에 표시됩니다.</p></div></main></body></html>')
        print("리포트 0개")
        return
    days = sorted(mds, reverse=True)
    docs = {d: parse(mds[d].read_text()) for d in days}
    for i, d in enumerate(days):
        nxt = days[i - 1] if i > 0 else None
        prv = days[i + 1] if i + 1 < len(days) else None
        (PUB / f"{d}.html").write_text(report_page(dt.date.fromisoformat(d), docs[d], prv, nxt))
    (PUB / "index.html").write_text(index_page(days, docs))
    print(f"{len(days)}개 리포트 -> {PUB}")


if __name__ == "__main__":
    main()
