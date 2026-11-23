#!/usr/bin/env python3
"""reports/ (와 old/) 의 날짜별 HTML을 site/public/ 으로 복사하고 목록 index.html을 만든다."""
import re, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PUB = ROOT / "public"
SRC = [ROOT.parent / "reports", ROOT.parent / "old"]

PUB.mkdir(exist_ok=True)
for f in PUB.glob("*.html"):
    f.unlink()
dates = {}
for d in SRC:
    for f in sorted(d.glob("*.html")):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", f.name):
            dates[f.stem] = f  # reports 가 old 보다 우선(뒤에 오는 쪽이 덮어쓰므로 SRC 순서 주의)
for name, f in dates.items():
    shutil.copy(f, PUB / f.name)

items = "".join(f'<li><a href="{d}.html">{d}</a></li>' for d in sorted(dates, reverse=True))
(PUB / "index.html").write_text(f"""<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>과학기술 데일리 브리핑</title>
<style>body{{font:16px/1.8 -apple-system,"Apple SD Gothic Neo",sans-serif;max-width:720px;margin:40px auto;padding:0 16px}}
li{{margin:.4rem 0}}@media(prefers-color-scheme:dark){{body{{background:#121214;color:#eee}}a{{color:#8ea6ff}}}}</style>
<h1>과학기술 데일리 브리핑</h1>
<button id=r style="padding:.5rem 1rem;font:inherit">지금 새로고침</button> <span id=m></span>
<ul>{items}</ul>
<script>
r.onclick=async()=>{{r.disabled=true;m.textContent="요청 중...";
try{{const x=await fetch("/api/refresh",{{method:"POST"}});
m.textContent=x.ok?"시작했어요. 2~5분 뒤 새로고침하면 새 리포트가 보여요.":"실패("+x.status+")";}}
catch(e){{m.textContent="실패";}}setTimeout(()=>r.disabled=false,30000);}};
</script></html>""")
print(f"{len(dates)}개 리포트 -> {PUB}")
