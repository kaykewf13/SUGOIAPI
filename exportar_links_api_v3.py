#!/usr/bin/env python3
“””
exportar_links_api_v3.py  — SUGOIAPI
Classifica animes por gênero via AniList API com cache local.
Suporta conteúdo adulto (Hentai / Ecchi).
“””
import re, json, time, shutil, urllib.request, cloudscraper
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR  = Path(**file**).parent.absolute()
OUTPUT_DIR  = SCRIPT_DIR / “output”
CACHE_FILE  = SCRIPT_DIR / “genre_cache.json”
ANILIST_URL = “https://graphql.anilist.co”

SOURCES = [
“https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u”,
“https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u”,
“https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u”,
]

LIVE_TERMS = {“TV”,“LIVE”,“24/7”,“ONLINE”,“AO VIVO”,“CANAL”,“CHANNEL”}

GENRE_MAP = {
“Hentai”:        “HENTAI”,
“Ecchi”:         “ECCHI”,
“Action”:        “AÇÃO”,
“Adventure”:     “AVENTURA”,
“Comedy”:        “COMÉDIA”,
“Drama”:         “DRAMA”,
“Fantasy”:       “FANTASIA”,
“Horror”:        “TERROR”,
“Mystery”:       “MISTÉRIO”,
“Psychological”: “PSICOLÓGICO”,
“Romance”:       “ROMANCE”,
“Sci-Fi”:        “FICÇÃO CIENTÍFICA”,
“Slice of Life”: “SLICE OF LIFE”,
“Sports”:        “ESPORTES”,
“Supernatural”:  “SOBRENATURAL”,
“Thriller”:      “THRILLER”,
“Mecha”:         “MECHA”,
“Music”:         “MUSICAL”,
}

# Hentai e Ecchi primeiro — evita que caiam em outro gênero

PRIORITY = [
“Hentai”, “Ecchi”,
“Action”, “Fantasy”, “Sci-Fi”, “Horror”, “Psychological”,
“Thriller”, “Mystery”, “Romance”, “Comedy”, “Sports”,
“Slice of Life”, “Drama”, “Adventure”, “Supernatural”, “Mecha”, “Music”,
]

# ── Cache ──────────────────────────────────────────────────────────────────

def load_cache():
return json.loads(CACHE_FILE.read_text(“utf-8”)) if CACHE_FILE.exists() else {}

def save_cache(c):
CACHE_FILE.write_text(json.dumps(c, ensure_ascii=False, indent=2), “utf-8”)

# ── AniList ────────────────────────────────────────────────────────────────

# isAdult:null retorna todos os títulos, incluindo conteúdo adulto

GQL = ‘query($s:String){Media(search:$s,type:ANIME,isAdult:null){genres}}’

def fetch_genres(title):
data = json.dumps({“query”: GQL, “variables”: {“s”: title}}).encode()
req  = urllib.request.Request(
ANILIST_URL, data=data,
headers={“Content-Type”: “application/json”, “Accept”: “application/json”},
method=“POST”,
)
try:
with urllib.request.urlopen(req, timeout=8) as r:
return json.loads(r.read()).get(“data”, {}).get(“Media”, {}).get(“genres”, [])
except:
return []

def pick_genre(genres):
for g in PRIORITY:
if g in genres:
return GENRE_MAP.get(g, g.upper())
return GENRE_MAP.get(genres[0], genres[0].upper()) if genres else “OUTROS”

# ── Título limpo para busca ────────────────────────────────────────────────

STRIP = [
r”[.*?]”, r”(.*?)”,
r”\s[-–]\s?\d+.*$”,
r”\bS\d{1,2}E\d{1,2}\b.*$”,
r”\b(ep|episode).?\s?\d+.*$”,
r”\b(dublado|legendado|dub|sub|leg)\b”,
r”\b(1080p?|720p?|480p?|4k|hdr)\b”,
]

def extract_title(name):
t = name
for p in STRIP:
t = re.sub(p, “”, t, flags=re.IGNORECASE)
return re.sub(r”\s+”, “ “, t).strip()

def resolve_genre(name, cache):
key = extract_title(name).lower()
if not key:
return “OUTROS”
if key not in cache:
cache[key] = pick_genre(fetch_genres(key))
time.sleep(0.6)   # rate limit AniList ~90 req/min
return cache[key]

# ── Fontes M3U ────────────────────────────────────────────────────────────

def fetch_sources(scraper):
entries, seen = [], set()
for url in SOURCES:
try:
res = scraper.get(url, timeout=15)
if res.status_code != 200:
print(f”  [SKIP] {url} → {res.status_code}”)
continue
matches = re.findall(r”#EXTINF:.*?,(.*?)\n(https?://\S+)”, res.text, re.DOTALL)
added = 0
for nome, link in matches:
nome, link = nome.strip(), link.strip()
if link in seen or any(t in nome.upper() for t in LIVE_TERMS):
continue
seen.add(link)
entries.append({“nome”: nome, “url”: link})
added += 1
print(f”  [OK] {url} → {added} entradas”)
except Exception as e:
print(f”  [ERRO] {url}: {e}”)
return entries

# ── M3U ───────────────────────────────────────────────────────────────────

NOISE = re.compile(r”[(1080p?|720p?|480p?|4K|HDR|x264|x265|HEVC|AAC|BluRay|WEB-?DL)]”, re.I)

def build_m3u(entries, cache):
lines = [’#EXTM3U x-tvg-url=”” m3u-type=“m3u_plus”\n\n’]
stats, total = defaultdict(int), len(entries)
for i, e in enumerate(entries, 1):
genre = resolve_genre(e[“nome”], cache)
group = f”ANIMES | {genre}”
nome  = re.sub(r”\s{2,}”, “ “, NOISE.sub(””, e[“nome”])).strip()
tid   = re.sub(r”[^\w]”, “_”, nome.lower())[:40]
lines.append(
f’#EXTINF:-1 tvg-id=”{tid}” tvg-name=”{nome}” ’
f’tvg-logo=”” group-title=”{group}”, {nome}\n’
f’{e[“url”]}?output=ts\n\n’
)
stats[group] += 1
if i % 50 == 0:
save_cache(cache)
print(f”  [{i}/{total}] processados…”)
return “”.join(lines), dict(stats)

# ── Main ──────────────────────────────────────────────────────────────────

def main():
if OUTPUT_DIR.exists():
shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

```
print("\n" + "="*55)
print("  SUGOIAPI — Gêneros via AniList (+ adulto)")
print("="*55 + "\n")

cache   = load_cache()
scraper = cloudscraper.create_scraper()

print("[1/3] Buscando fontes...\n")
entries = fetch_sources(scraper)
print(f"\n  {len(entries)} entradas | {len(cache)} no cache\n")

print("[2/3] Classificando por gênero...\n")
m3u, stats = build_m3u(entries, cache)
save_cache(cache)

out = OUTPUT_DIR / "playlist_premium.m3u"
out.write_text(m3u, encoding="utf-8")

print("\n[3/3] Por gênero:\n")
for g, c in sorted(stats.items(), key=lambda x: -x[1]):
    print(f"  {c:>5}  {g}")
print(f"\n  Total: {sum(stats.values())} → {out}\n" + "="*55 + "\n")
```

if **name** == “**main**”:
main()