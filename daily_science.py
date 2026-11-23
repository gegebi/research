#!/usr/bin/env python3
"""매일 전 세계(영·중·일·한) 과학기술 이슈를 모아 한국어 브리핑을 만든다.

흐름
  1) 여러 언어의 RSS/Atom 피드를 직접 수집하고 중복을 제거한다 (Gemini 호출 없음)
  2) 제목+요약 수백 건을 한 번의 호출로 넘겨 중요한 것만 고른다
  3) 고른 기사의 본문을 가져와, 본문에 근거해서만 한국어로 요약한다
  4) '5년 전 재조명'만 Google Search 그라운딩으로 따로 만든다 (하루 1회)
Gemini 호출은 하루 3번이다.

표준 라이브러리만 사용한다. 키는 환경변수 GEMINI_API_KEY 또는 같은 폴더의 .env 에서 읽는다.
사용법: python3 daily_science.py [--model MODEL] [--collect-only]
"""
import argparse
import concurrent.futures as cf
import datetime as dt
import email.utils
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
SEEN_FILE = REPORTS / "seen.json"
DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
UA = "Mozilla/5.0 (compatible; daily-science-digest/1.0)"
MAX_AGE_DAYS = 4          # 이보다 오래된 기사는 버린다 (날짜를 알 수 있을 때만)
MAX_PER_FEED = 40
PICK_COUNT = 16           # 최종 요약할 기사 수


def gnews(query, hl, gl, ceid):
    q = urllib.parse.quote(f"{query} when:2d")
    return f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"


# (언어, 이름, URL). 죽은 피드는 건너뛰므로 자유롭게 추가/삭제해도 된다.
FEEDS = [
    ("영어", "Nature", "https://www.nature.com/nature.rss"),
    ("영어", "Science News", "https://www.science.org/rss/news_current.xml"),
    ("영어", "ScienceDaily", "https://www.sciencedaily.com/rss/top/science.xml"),
    ("영어", "Phys.org", "https://phys.org/rss-feed/"),
    ("영어", "Quanta", "https://www.quantamagazine.org/feed/"),
    ("영어", "MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("중국어", "Solidot", "https://www.solidot.org/index.rss"),
    ("중국어", "구글뉴스(과학연구)", gnews("科学 研究 突破", "zh-CN", "CN", "CN:zh-Hans")),
    ("중국어", "구글뉴스(科技)", gnews("科技 创新 成果 发布", "zh-CN", "CN", "CN:zh-Hans")),
    ("중국어", "구글뉴스(政策)", gnews("科技 政策 伦理 人工智能 监管", "zh-CN", "CN", "CN:zh-Hans")),
    ("일본어", "JST 보도자료", "https://www.jst.go.jp/rss/press.xml"),
    ("일본어", "Nature(일본어)", "https://www.nature.com/ja/rss.xml"),
    ("일본어", "ITmedia", "https://rss.itmedia.co.jp/rss/2.0/news_technology.xml"),
    ("일본어", "Gigazine", "https://gigazine.net/news/rss_2.0/"),
    ("일본어", "sorae", "https://sorae.info/feed"),
    ("일본어", "구글뉴스(研究)", gnews("研究グループ 発表 科学", "ja", "JP", "JP:ja")),
    ("일본어", "구글뉴스(技術)", gnews("新技術 開発 成功 大学", "ja", "JP", "JP:ja")),
    ("한국어", "한겨레 과학", "https://www.hani.co.kr/rss/science/"),
    ("한국어", "HelloDD", "https://www.hellodd.com/rss/allArticle.xml"),
    ("한국어", "구글뉴스(연구)", gnews("연구팀 개발 성공 과학", "ko", "KR", "KR:ko")),
    ("한국어", "구글뉴스(기술)", gnews("신기술 연구 발표 KAIST OR 서울대 OR 기초과학연구원", "ko", "KR", "KR:ko")),
    ("한국어", "구글뉴스(정책)", gnews("과학기술 정책 윤리 AI 규제", "ko", "KR", "KR:ko")),
]


# ---------------------------------------------------------------- 공통
def load_key():
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            m = re.match(r"\s*(?:export\s+)?(GEMINI_API_KEY|GOOGLE_API_KEY)\s*=\s*(.+)", line)
            if m:
                key = m.group(2).strip().strip("'\"")
    if not key:
        sys.exit("GEMINI_API_KEY 가 없습니다. 환경변수로 넣거나 research/.env 에 적어 주세요.")
    return key


def call_gemini(key, model, prompt, search=False, as_json=False, retries=3):
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if search:
        body["tools"] = [{"google_search": {}}]
    if as_json:
        body["generationConfig"] = {"responseMimeType": "application/json"}
    req = urllib.request.Request(
        API.format(model=model),
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    data = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code in (429, 500, 503) and attempt < retries - 1:
                time.sleep(15 * (attempt + 1))
                continue
            raise RuntimeError(f"Gemini HTTP {e.code}: {msg}")
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            raise RuntimeError(f"네트워크 오류: {e}")
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
    sources = [(c["web"].get("title", ""), c["web"].get("uri", "")) for c in chunks if "web" in c]
    return text.strip(), sources


def http_get(url, timeout=15, limit=600_000, depth=0):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en,ko,ja,zh"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(limit)
            charset = r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        # Python 3.9 의 urllib 은 308 리다이렉트를 따라가지 않는다
        loc = e.headers.get("Location") if e.code == 308 else None
        if not loc or depth > 3:
            raise
        return http_get(urllib.parse.urljoin(url, loc), timeout, limit, depth + 1)
    return raw.decode(charset, errors="replace")


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ---------------------------------------------------------------- 1) 수집
def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_date(s):
    if not s:
        return None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(s.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d


def parse_feed(lang, name, xml_text):
    xml_text = xml_text.lstrip("﻿ \r\n\t")
    root = ET.fromstring(xml_text.encode("utf-8"))
    items = []
    for el in root.iter():
        if local(el.tag) not in ("item", "entry"):
            continue
        f = {}
        for ch in el:
            k = local(ch.tag)
            if k == "link":
                f.setdefault("link", ch.get("href") or (ch.text or "").strip())
            elif k in ("title", "description", "summary", "pubDate", "published", "updated", "date"):
                f.setdefault(k, ch.text or "")
        title = strip_html(f.get("title"))
        link = (f.get("link") or "").strip()
        if not title or not link:
            continue
        pub = parse_date(f.get("pubDate") or f.get("published") or f.get("updated") or f.get("date"))
        items.append({
            "lang": lang, "source": name, "title": title, "link": link,
            "desc": strip_html(f.get("description") or f.get("summary"))[:300], "date": pub,
        })
    items.sort(key=lambda x: x["date"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
    return items[:MAX_PER_FEED]


def fetch_one(feed):
    lang, name, url = feed
    try:
        return feed, parse_feed(lang, name, http_get(url)), None
    except Exception as e:  # noqa: BLE001
        return feed, [], str(e)[:80]


def norm(t):
    t = re.sub(r"\s+-\s+[^-]{1,40}$", "", t)  # 구글뉴스의 ' - 매체명' 꼬리 제거
    return re.sub(r"[\W_]+", "", t.lower())[:60]


def load_seen():
    try:
        return json.loads(SEEN_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def collect(today):
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=MAX_AGE_DAYS)
    seen = load_seen()
    out, keys, dead = [], set(seen), []
    with cf.ThreadPoolExecutor(8) as ex:
        for feed, items, err in ex.map(fetch_one, FEEDS):
            if err:
                dead.append(f"{feed[1]}({err})")
                continue
            for it in items:
                if it["date"] and it["date"] < cutoff:
                    continue
                k = norm(it["title"])
                if k in keys or it["link"] in keys:
                    continue
                keys.add(k)
                out.append(it)
    counts = {}
    for it in out:
        counts[it["lang"]] = counts.get(it["lang"], 0) + 1
    print(f"수집 {len(out)}건 {counts}", file=sys.stderr)
    if dead:
        print(f"  응답 없는 피드: {', '.join(dead)}", file=sys.stderr)
    return out


# ---------------------------------------------------------------- 2) 선별
def select(key, model, items):
    lines = [f"{i}|{it['lang']}|{it['source']}|{it['title']}|{it['desc'][:110]}" for i, it in enumerate(items)]
    prompt = (
        "아래는 오늘 수집한 과학기술 기사 목록입니다 (id|언어|매체|제목|요약).\n"
        f"독자는 노벨상 수상 소식이 나온 뒤에야 그 분야를 알게 되는 일이 싫은, 과학 호기심이 많은 사람입니다. "
        f"이 독자에게 가치 있는 기사를 정확히 {PICK_COUNT}개 고르세요.\n\n"
        "기준:\n"
        "- 새로운 발견·기술·방법론, 또는 과학기술과 사회가 만나는 중요한 이슈를 우선합니다.\n"
        "- 이미 모두가 아는 빅뉴스보다 놓치기 쉬운 흥미로운 연구를 우대합니다.\n"
        "- 광고성 기사, 제품 후기, 주가·실적 기사, 단순 행사 소식, 연예·가십은 제외합니다.\n"
        "- 같은 사건은 하나만 고릅니다. 영어 외 언어권(중국어·일본어·한국어)에서 나온 것도 "
        "각각 최소 2개씩은 포함하려 노력하세요.\n"
        "- section 은 latest(최신 연구·기술), hidden(덜 알려진 흥미로운 연구), society(정책·윤리·산업·사회) 중 하나.\n\n"
        '출력은 JSON 배열만: [{"id": 숫자, "section": "latest|hidden|society", "why": "한 줄 이유"}]\n\n'
        + "\n".join(lines)
    )
    text, _ = call_gemini(key, model, prompt, as_json=True)
    picks = json.loads(text)
    chosen, used = [], set()
    for p in picks:
        i = p.get("id")
        if isinstance(i, int) and 0 <= i < len(items) and i not in used:
            used.add(i)
            chosen.append({**items[i], "section": p.get("section", "latest"), "why": p.get("why", "")})
    return chosen[: PICK_COUNT + 4]


# ---------------------------------------------------------------- 3) 본문 + 요약
def fetch_body(it):
    if "news.google.com" in it["link"]:
        return it, ""  # 구글뉴스 링크는 리다이렉트라 본문 추출이 불안정하다
    try:
        page = http_get(it["link"], timeout=12, limit=400_000)
        page = re.sub(r"(?is)<(script|style|noscript|nav|footer|header)\b.*?</\1>", " ", page)
        paras = [strip_html(p) for p in re.findall(r"(?is)<p\b[^>]*>(.*?)</p>", page)]
        text = " ".join(p for p in paras if len(p) > 40)
        return it, text[:3500]
    except Exception:  # noqa: BLE001
        return it, ""


def summarize(key, model, chosen, retro_headings):
    with cf.ThreadPoolExecutor(8) as ex:
        enriched = list(ex.map(fetch_body, chosen))
    blocks = []
    for n, (it, body) in enumerate(enriched, 1):
        basis = body or it["desc"] or "(제목만 확인됨)"
        kind = "본문" if body else "RSS 요약/제목만"
        blocks.append(
            f"[{n}] 섹션:{it['section']} | {it['lang']}권 | 매체:{it['source']} | 링크:{it['link']}\n"
            f"제목: {it['title']}\n근거 자료({kind}): {basis}"
        )
    prompt = (
        "아래 기사 자료로 한국어 데일리 과학기술 브리핑을 쓰세요.\n\n"
        "형식(마크다운):\n"
        "맨 위에 전체 3줄 요약을 `> ` 인용문으로. 제목(# )은 쓰지 마세요.\n"
        "그 다음 `## 최신 동향`, `## 숨은 흥미 연구`, `## 과학기술과 사회` 섹션. 기사의 section 값에 맞춰 배치하세요.\n"
        "항목은 `### 한국어 제목` + 본문 3~4문장(무슨 일인지, 어떻게 가능했는지, 왜 흥미로운지) + "
        "마지막 줄 `출처: [매체명](링크) · 언어권`. 기사 하나당 항목 하나, 서로 다른 주제를 한 제목에 묶지 마세요.\n\n"
        "규칙(중요):\n"
        "- 주어진 근거 자료에 있는 내용만 쓰세요. 자료에 없는 수치·기관·결과를 지어내지 마세요.\n"
        "- 근거가 '제목만 확인됨' 또는 'RSS 요약'인 항목은 본문 끝에 `(본문 미확인, 제목·요약 기준)` 을 붙이고 짧게 쓰세요.\n"
        "- 전문 용어는 처음 나올 때 쉬운 말로 풀어 주세요.\n"
        f"- 최근 이미 다룬 소제목과 같은 주제는 피하세요: {'; '.join(retro_headings[-30:]) or '없음'}\n\n"
        "===== 기사 자료 =====\n" + "\n\n".join(blocks)
    )
    text, _ = call_gemini(key, model, prompt)
    return text


# ---------------------------------------------------------------- 4) 5년 전 재조명 (그라운딩)
def retro(key, model, today, headings):
    year = today.year - 5
    prompt = (
        f"오늘은 {today.isoformat()}입니다. 웹을 검색해서, {year}년에 발표된 과학기술 연구 중 "
        "당시 흥미로웠거나 중요했고, 그 뒤 5년 동안 어떻게 발전했는지(또는 어떻게 뒤집혔는지) 확인되는 것을 3개 고르세요.\n\n"
        "규칙(중요):\n"
        f"- 발표 시점이 반드시 {year}년이어야 합니다. 다른 연도의 연구는 쓰지 마세요.\n"
        "- 서로 다른 두 곳 이상의 출처로 확인되는 사실만 쓰세요. 확인이 안 되면 항목을 줄이세요.\n"
        "- 이후 진전은 검색으로 확인된 것만 쓰고, 확인 안 되면 `이후 진전은 확인하지 못함`이라고 쓰세요.\n"
        "- 영어권 밖(중국·일본·한국) 연구도 한 개 이상 포함하려 노력하세요.\n"
        "- 형식: `### 제목` + 무엇이었는지 2문장 + `그 후:` 로 시작하는 2문장 + `출처: 매체명, 연도`. 한국어로 쓰세요.\n"
        f"- 아래 이미 다룬 주제는 피하세요: {'; '.join(headings[-30:]) or '없음'}"
    )
    return call_gemini(key, model, prompt, search=True)


# ---------------------------------------------------------------- 출력
def recent_headings(days=7):
    seen = []
    for p in sorted(REPORTS.glob("*.md"))[-days:]:
        seen += re.findall(r"^### (.+)$", p.read_text(), flags=re.M)
    return seen


def md_to_html(md):
    out, in_list = [], False

    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
        return s

    for line in md.splitlines():
        if line.startswith(("- ", "* ")):
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(line[2:])}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        if line.startswith("### "):
            out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            out.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.startswith(">"):
            out.append(f"<blockquote>{inline(line.lstrip('> '))}</blockquote>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


PAGE = """<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{font:16px/1.7 -apple-system,"Apple SD Gothic Neo",sans-serif;max-width:720px;margin:40px auto;padding:0 16px;color:#1b1b1f}}
h1{{font-size:1.6rem}}h2{{margin-top:2.2rem;border-bottom:2px solid #e5e5ea;padding-bottom:.3rem}}
h3{{margin-bottom:.2rem}}blockquote{{margin:1rem 0;padding:.6rem 1rem;background:#f4f6fb;border-left:4px solid #5b7cfa}}
a{{color:#3b5bdb}}details{{margin-top:2rem;color:#555;font-size:.9rem}}
@media(prefers-color-scheme:dark){{body{{background:#17171a;color:#e8e8ec}}blockquote{{background:#22242b}}a{{color:#8ea6ff}}h2{{border-color:#333}}}}
</style>
<h1>{title}</h1>
{body}
{extra}
</html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--collect-only", action="store_true", help="수집·중복제거 결과만 보고 종료 (API 불필요)")
    args = ap.parse_args()
    today = dt.date.today()
    REPORTS.mkdir(exist_ok=True)

    items = collect(today)
    if args.collect_only:
        for it in items[:15]:
            print(f"[{it['lang']}/{it['source']}] {it['title']}")
        return
    if not items:
        sys.exit("수집된 기사가 없습니다. 네트워크와 피드를 확인하세요.")

    key = load_key()
    headings = recent_headings()
    print("선별 중...", file=sys.stderr)
    chosen = select(key, args.model, items)
    print(f"  {len(chosen)}건 선택. 본문 가져와 요약 중...", file=sys.stderr)
    body_md = summarize(key, args.model, chosen, headings)

    retro_md, retro_sources = "", []
    try:
        print("5년 전 재조명 (검색) 중...", file=sys.stderr)
        retro_md, retro_sources = retro(key, args.model, today, headings)
    except Exception as e:  # noqa: BLE001
        print(f"  재조명 실패(건너뜀): {e}", file=sys.stderr)

    title = f"과학기술 데일리 브리핑 · {today.isoformat()}"
    md = f"# {title}\n\n{body_md}\n"
    if retro_md:
        md += f"\n## 5년 전 재조명 ({today.year - 5}년)\n{retro_md}\n"
        if retro_sources:
            md += "\n재조명 검색 출처:\n" + "\n".join(
                f"- [{t or u}]({u})" for t, u in dict.fromkeys(retro_sources)
            ) + "\n"
    (REPORTS / f"{today.isoformat()}.md").write_text(md)

    extra = ""
    if retro_sources:
        li = "".join(f'<li><a href="{html.escape(u)}">{html.escape(t or u)}</a></li>'
                     for t, u in dict.fromkeys(retro_sources))
        extra = f"<details><summary>재조명 검색 출처 ({len(retro_sources)})</summary><ul>{li}</ul></details>"
    page_body = md_to_html(body_md)
    if retro_md:
        page_body += f"\n<h2>5년 전 재조명 ({today.year - 5}년)</h2>\n" + md_to_html(retro_md)
    (REPORTS / f"{today.isoformat()}.html").write_text(
        PAGE.format(title=title, body=page_body, extra=extra)
    )

    seen = load_seen()
    cutoff = (today - dt.timedelta(days=14)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    for it in chosen:
        seen[norm(it["title"])] = today.isoformat()
        seen[it["link"]] = today.isoformat()
    SEEN_FILE.write_text(json.dumps(seen, ensure_ascii=False))
    print(f"저장: {REPORTS / (today.isoformat() + '.html')}", file=sys.stderr)


if __name__ == "__main__":
    main()
