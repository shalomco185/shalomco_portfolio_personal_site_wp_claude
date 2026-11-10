import json, sys, time
sys.path.insert(0, sys.argv[1])
import os; os.environ.setdefault("DATA_DIR", "/tmp/claude-0/benchdata")
from app.services.ocr import extract_text
from app.services.address_parser import parse_label
meta = json.load(open(sys.argv[2] if len(sys.argv) > 2 else "meta.json")); ok = top = 0; t0 = time.time(); fails = []
for m in meta:
    text = extract_text(open(m["file"], "rb").read())
    p = parse_label(text)
    hit = lambda c: m["street"].split()[-1] in c and m["city"].split()[-1] in c
    if p.candidates and hit(p.candidates[0]): top += 1
    if any(hit(c) for c in p.candidates): ok += 1
    else: fails.append((m["file"], p.candidates[:2]))
n = len(meta)
print(f"top1 {top}/{n}  any {ok}/{n}  avg {(time.time()-t0)/n:.1f}s/img")
for f in fails[:12]: print("  FAIL", f)
