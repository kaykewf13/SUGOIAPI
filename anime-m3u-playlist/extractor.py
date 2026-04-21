"""Anime M3U Extractor - Fontes Brasileiras
Extrai links de anime dublado/legendado e gera playlist M3U"""

import requests
from bs4 import BeautifulSoup
import time
import json
import re
import logging
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO, format=’%(asctime)s - %(levelname)s - %(message)s’)
logger = logging.getLogger(**name**)

# Gêneros excluídos

EXCLUDED_GENRES = [‘yaoi’, ‘boys-love’, ‘bl’]

# Headers para evitar bloqueio

HEADERS = {
‘User-Agent’: ‘Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36’,
‘Accept’: ‘text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8’,
‘Accept-Language’: ‘pt-BR,pt;q=0.9,en;q=0.8’,
}

SOURCES = [
{“name”: “AnimesHD”, “url”: “https://animeshd.to/animes”, “suffix”: “/page/”, “priority”: 1},
{“name”: “AnimePlayer”, “url”: “https://animeplayer.com.br/genero/dublado”, “suffix”: “/page/”, “priority”: 1},
{“name”: “AnimesOnline”, “url”: “https://animesonline.nz/anime”, “suffix”: “/page/”, “priority”: 2},
{“name”: “Anizero”, “url”: “https://anizero.org/lista-de-animes”, “suffix”: “?page=”, “priority”: 2},
{“name”: “Goyabu”, “url”: “https://goyabu.com/lista-de-animes”, “suffix”: “/page/”, “priority”: 2},
]

def get_page(url, retries=3):
“”“Faz requisição com retry”””
for i in range(retries):
try:
response = requests.get(url, headers=HEADERS, timeout=15)
if response.status_code == 200:
return response.text
logger.warning(f”Status {response.status_code} para {url}”)
except Exception as e:
logger.error(f”Erro ao acessar {url}: {e}”)
time.sleep(2)
return None

def is_excluded(genres):
“”“Verifica se o anime deve ser excluído por gênero”””
if not genres:
return False
genres_lower = [g.lower() for g in genres]
return any(ex in genres_lower for ex in EXCLUDED_GENRES)

def normalize_title(title):
“”“Normaliza título para comparação e evitar duplicatas”””
title = title.lower().strip()
title = re.sub(r’\s*(dublado|legendado|dual audio|dub|leg)\s*’, ‘’, title, flags=re.IGNORECASE)
title = re.sub(r’\s+’, ’ ’, title).strip()
return title

def extract_animeshd(source):
“”“Extrai animes do AnimesHD”””
animes = []
page = 1

```
while True:
    url = f"{source['url']}{source['suffix']}{page}"
    logger.info(f"AnimesHD - Página {page}: {url}")
    
    html = get_page(url)
    if not html:
        break
        
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.select('.flw-item, .film-poster, .anime-item, article.item')
    
    if not items:
        logger.info(f"AnimesHD - Sem mais itens na página {page}")
        break
    
    for item in items:
        try:
            # Título
            title_el = item.select_one('.film-name, .title, h2, h3')
            title = title_el.get_text(strip=True) if title_el else ''
            
            # URL
            link_el = item.select_one('a[href]')
            link = urljoin(source['url'], link_el['href']) if link_el else ''
            
            # Capa
            img_el = item.select_one('img[src], img[data-src]')
            cover = img_el.get('data-src') or img_el.get('src', '') if img_el else ''
            
            # Gêneros
            genres = [g.get_text(strip=True) for g in item.select('.genre, .fdi-item')]
            
            if title and link and not is_excluded(genres):
                is_dubbed = 'dublado' in title.lower() or 'dub' in title.lower()
                animes.append({
                    'title': title,
                    'url': link,
                    'cover': cover,
                    'genres': genres,
                    'source': source['name'],
                    'dubbed': is_dubbed,
                    'type': 'series'
                })
        except Exception as e:
            logger.error(f"Erro ao processar item AnimesHD: {e}")
    
    page += 1
    time.sleep(1)
    
    if page > 50:  # Limite de segurança
        break

return animes
```

def extract_animeplayer(source):
“”“Extrai animes do AnimePlayer”””
animes = []
page = 1

```
while True:
    url = f"{source['url']}{source['suffix']}{page}"
    logger.info(f"AnimePlayer - Página {page}: {url}")
    
    html = get_page(url)
    if not html:
        break
        
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.select('.anime-card, .item, article, .entry-item')
    
    if not items:
        break
    
    for item in items:
        try:
            title_el = item.select_one('h2, h3, .title, .entry-title')
            title = title_el.get_text(strip=True) if title_el else ''
            
            link_el = item.select_one('a[href]')
            link = urljoin(source['url'], link_el['href']) if link_el else ''
            
            img_el = item.select_one('img')
            cover = img_el.get('data-src') or img_el.get('src', '') if img_el else ''
            
            genres = [g.get_text(strip=True) for g in item.select('.genre, .cat')]
            
            if title and link and not is_excluded(genres):
                animes.append({
                    'title': title,
                    'url': link,
                    'cover': cover,
                    'genres': genres,
                    'source': source['name'],
                    'dubbed': True,  # AnimePlayer foca em dublado
                    'type': 'series'
                })
        except Exception as e:
            logger.error(f"Erro ao processar item AnimePlayer: {e}")
    
    page += 1
    time.sleep(1)
    
    if page > 50:
        break

return animes
```

def extract_generic(source):
“”“Extrator genérico para demais fontes”””
animes = []
page = 1

```
while True:
    url = f"{source['url']}{source['suffix']}{page}"
    logger.info(f"{source['name']} - Página {page}: {url}")
    
    html = get_page(url)
    if not html:
        break
        
    soup = BeautifulSoup(html, 'html.parser')
    
    # Seletores comuns
    items = soup.select(
        '.anime-item, .item, article, .film-item, '
        '.flw-item, .entry-item, li.anime'
    )
    
    if not items:
        break
    
    for item in items:
        try:
            title_el = item.select_one('h2, h3, h4, .title, .name, a[title]')
            title = title_el.get_text(strip=True) if title_el else ''
            if not title and title_el:
                title = title_el.get('title', '')
            
            link_el = item.select_one('a[href]')
            link = urljoin(source['url'], link_el['href']) if link_el else ''
            
            img_el = item.select_one('img')
            cover = ''
            if img_el:
                cover = img_el.get('data-src') or img_el.get('data-lazy-src') or img_el.get('src', '')
            
            genres = [g.get_text(strip=True) for g in item.select('.genre, .genres a, .cat')]
            
            if title and link and not is_excluded(genres):
                is_dubbed = 'dublado' in title.lower() or 'dub' in title.lower()
                animes.append({
                    'title': title,
                    'url': link,
                    'cover': cover,
                    'genres': genres,
                    'source': source['name'],
                    'dubbed': is_dubbed,
                    'type': 'series'
                })
        except Exception as e:
            logger.error(f"Erro ao processar item {source['name']}: {e}")
    
    page += 1
    time.sleep(1.5)
    
    if page > 50:
        break

return animes
```

def get_stream_links(anime_url, source_name):
“”“Extrai links de stream de uma página de anime”””
html = get_page(anime_url)
if not html:
return []

```
soup = BeautifulSoup(html, 'html.parser')
links = []

# Padrões comuns de players
patterns = [
    r'file["\s]*:["\s]*["\']([^"\']+\.m3u8[^"\']*)["\']',
    r'file["\s]*:["\s]*["\']([^"\']+\.mp4[^"\']*)["\']',
    r'src=["\']([^"\']+\.m3u8[^"\']*)["\']',
    r'"url"["\s]*:["\s]*"([^"]+\.m3u8[^"]*)"',
    r'source src=["\']([^"\']+)["\']',
]

page_source = str(soup)

for pattern in patterns:
    matches = re.findall(pattern, page_source, re.IGNORECASE)
    for match in matches:
        if match and 'http' in match:
            links.append(match)

# Procura iframes
iframes = soup.select('iframe[src]')
for iframe in iframes:
    src = iframe.get('src', '')
    if src and ('player' in src or 'embed' in src):
        links.append(src)

return list(set(links))
```

def deduplicate_animes(all_animes):
“”“Remove duplicatas priorizando dublado”””
seen = {}

```
# Ordena: dublado primeiro (priority 1), depois por fonte
sorted_animes = sorted(all_animes, key=lambda x: (0 if x['dubbed'] else 1, x.get('source', '')))

for anime in sorted_animes:
    key = normalize_title(anime['title'])
    if key not in seen:
        seen[key] = anime
    else:
        # Se já existe legendado e agora temos dublado, substitui
        if anime['dubbed'] and not seen[key]['dubbed']:
            seen[key] = anime

return list(seen.values())
```

def extract_all():
“”“Extrai animes de todas as fontes”””
all_animes = []

```
for source in SOURCES:
    logger.info(f"Extraindo de {source['name']}...")
    try:
        if source['name'] == 'AnimesHD':
            animes = extract_animeshd(source)
        elif source['name'] == 'AnimePlayer':
            animes = extract_animeplayer(source)
        else:
            animes = extract_generic(source)
        
        logger.info(f"{source['name']}: {len(animes)} animes encontrados")
        all_animes.extend(animes)
    except Exception as e:
        logger.error(f"Erro ao extrair {source['name']}: {e}")
    
    time.sleep(2)

# Remove duplicatas
unique_animes = deduplicate_animes(all_animes)
logger.info(f"Total após deduplicação: {len(unique_animes)} animes")

return unique_animes
```

if **name** == “**main**”:
animes = extract_all()

```
# Salva JSON intermediário
with open('animes_raw.json', 'w', encoding='utf-8') as f:
    json.dump(animes, f, ensure_ascii=False, indent=2)

logger.info(f"Extração concluída: {len(animes)} animes salvos em animes_raw.json")
```
