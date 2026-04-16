
#!/usr/bin/env python3
import re, json, time, shutil, urllib.request, cloudscraper
from pathlib import Path
from collections import defaultdict

OUTPUT_DIR = Path(‘output’)
CACHE_FILE = Path(‘genre_cache.json’)
ANILIST_URL = ‘https://graphql.anilist.co’

SOURCES = [
‘https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u’,
‘https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u’,
‘https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u’,
]

LIVE_TERMS = {‘TV’, ‘LIVE’, ‘24/7’, ‘ONLINE’, ‘AO VIVO’, ‘CANAL’, ‘CHANNEL’}

GENRE_MAP = {
‘Hentai’: ‘HENTAI’, ‘Ecchi’: ‘ECCHI’, ‘Action’: ‘ACAO’,
‘Adventure’: ‘AVENTURA’, ‘Comedy’: ‘COMEDIA’, ‘Drama’: ‘DRAMA’,
‘Fantasy’: ‘FANTASIA’, ‘Horror’: ‘TERROR’, ‘Mystery’: ‘MISTERIO’,
‘Psychological’: ‘PSICOLOGICO’, ‘Romance’: ‘ROMANCE’,
‘Sci-Fi’: ‘FICCAO CIENTIFICA’, ‘Slice of Life’: ‘SLICE OF LIFE’,
‘Sports’: ‘ESPORTES’, ‘Supernatural’: ‘SOBRENATURAL’,
‘Thriller’: ‘THRILLER’, ‘Mecha’: ‘MECHA’, ‘Music’: ‘MUSICAL’,
}

PRIORITY = [
‘Hentai’, ‘Ecchi’, ‘Action’, ‘Fantasy’, ‘Sci-Fi’, ‘Horror’,
‘Psychological’, ‘Thriller’, ‘Mystery’, ‘Romance’, ‘Comedy’,
‘Sports’, ‘Slice of Life’, ‘Drama’, ‘Adventure’, ‘Supernatural’,
‘Mecha’, ‘Music’,
]
def load_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        content = CACHE_FILE.read_text('utf-8').strip()
        return json.loads(content) if content else {}
    except Exception:
        return {}

def save_cache(c):
CACHE_FILE.write_text(json.dumps(c, ensure_ascii=False, indent=2), ‘utf-8’)

GQL = ‘query($s:String){Media(search:$s,type:ANIME,isAdult:null){genres}}’

def fetch_genres(title):
payload = json.dumps({‘query’: GQL, ‘variables’: {‘s’: title}}).encode()
req = urllib.request.Request(
ANILIST_URL, data=payload,
headers={‘Content-Type’: ‘application/json’, ‘Accept’: ‘application/json’},
method=‘POST’
)
try:
with urllib.request.urlopen(req, timeout=8) as r:
return json.loads(r.read()).get(‘data’, {}).get(‘Media’, {}).get(‘genres’, [])
except Exception:
return []

def pick_genre(genres):
for g in PRIORITY:
if g in genres:
return GENRE_MAP.get(g, g.upper())
return GENRE_MAP.get(genres[0], genres[0].upper()) if genres else ‘OUTROS’

STRIP_PATS = [
r’[.*?]’, r’(.*?)’,
r’\s[-]\s?\d+.*$’,
r’\bS\d{1,2}E\d{1,2}\b.*$’,
r’\b(ep|episode).?\s?\d+.*$’,
r’\b(dublado|legendado|dub|sub|leg)\b’,
r’\b(1080p?|720p?|480p?|4k|hdr)\b’,
]

def extract_title(name):
t = name
for p in STRIP_PATS:
t = re.sub(p, ‘’, t, flags=re.IGNORECASE)
return re.sub(r’\s+’, ’ ’, t).strip()

def resolve_genre(name, cache):
key = extract_title(name).lower()
if not key:
return ‘OUTROS’
if key not in cache:
cache[key] = pick_genre(fetch_genres(key))
time.sleep(0.6)
return cache[key]

def fetch_sources(scraper):
entries, seen = [], set()
for url in SOURCES:
try:
res = scraper.get(url, timeout=15)
if res.status_code != 200:
continue
pat = r’#EXTINF:.*?,(.*?)\n(https?://\S+)’
for nome, link in re.findall(pat, res.text, re.DOTALL):
nome, link = nome.strip(), link.strip()
if link in seen or any(t in nome.upper() for t in LIVE_TERMS):
continue
seen.add(link)
entries.append({‘nome’: nome, ‘url’: link})
print(’  [OK] ’ + url)
except Exception as e:
print(’  [ERRO] ’ + url + ’: ’ + str(e))
return entries

NOISE = re.compile(
r’[(1080p?|720p?|480p?|4K|HDR|x264|x265|HEVC|AAC|BluRay|WEB-?DL)]’, re.I
)

def build_m3u(entries, cache):
parts = [’#EXTM3U x-tvg-url=”” m3u-type=“m3u_plus”\n\n’]
stats = defaultdict(int)
total = len(entries)
for i, e in enumerate(entries, 1):
genre = resolve_genre(e[‘nome’], cache)
group = ‘ANIMES | ’ + genre
nome  = re.sub(r’\s{2,}’, ’ ‘, NOISE.sub(’’, e[‘nome’])).strip()
tid   = re.sub(r’[^\w]’, ‘_’, nome.lower())[:40]
line  = (
‘#EXTINF:-1 tvg-id=”’ + tid + ‘” tvg-name=”’ + nome + ‘” ’
+ ‘tvg-logo=”” group-title=”’ + group + ‘”, ’ + nome + ‘\n’
+ e[‘url’] + ‘?output=ts\n\n’
)
parts.append(line)
stats[group] += 1
if i % 50 == 0:
save_cache(cache)
print(’  [’ + str(i) + ‘/’ + str(total) + ‘] processados…’)
return ‘’.join(parts), dict(stats)

def main():
if OUTPUT_DIR.exists():
shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

```
cache = load_cache()
scraper = cloudscraper.create_scraper()

print('Buscando fontes...')
entries = fetch_sources(scraper)
print(str(len(entries)) + ' entradas | ' + str(len(cache)) + ' cache')

print('Classificando por genero...')
m3u, stats = build_m3u(entries, cache)
save_cache(cache)

out = OUTPUT_DIR / 'playlist_premium.m3u'
out.write_text(m3u, encoding='utf-8')

for g, c in sorted(stats.items(), key=lambda x: -x[1]):
    print(str(c).rjust(5) + '  ' + g)
print('Total: ' + str(sum(stats.values())))
```

if **name** == ‘**main**’:
main()
