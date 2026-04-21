"""
Anime Stream Extractor - yt-dlp com fallback
Extrai links reais de stream (.m3u8/.mp4) das fontes brasileiras
"""

import subprocess
import json
import time
import logging
import re
import os
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
    'Referer': 'https://www.google.com/',
}

EXCLUDED_GENRES = ['yaoi', 'boys-love', 'bl']

SOURCES = [
    {"name": "AnimesOnline", "list_url": "https://animesonline.nz/anime", "suffix": "/page/"},
    {"name": "Goyabu", "list_url": "https://goyabu.com/lista-de-animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "list_url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
]


def run_ytdlp(url):
    """Executa yt-dlp e retorna info do stream"""
    try:
        result = subprocess.run(
            ['yt-dlp', '--no-warnings', '--quiet', '--dump-json',
             '--no-playlist', '--extractor-retries', '2',
             '--socket-timeout', '20', url],
            capture_output=True, text=True, timeout=45
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip().split('\n')[0])
    except Exception as e:
        logger.debug(f"yt-dlp error for {url}: {e}")
    return None


def get_best_url(info):
    """Extrai melhor URL de stream"""
    if not info:
        return None
    if info.get('url') and info['url'].startswith('http'):
        return info['url']
    for fmt in reversed(info.get('formats', [])):
        url = fmt.get('url', '')
        if url.startswith('http') and ('.m3u8' in url or '.mp4' in url):
            return url
    for fmt in reversed(info.get('formats', [])):
        if fmt.get('url', '').startswith('http'):
            return fmt['url']
    return None


def get_anime_list(source, max_pages=3):
    """Lista animes de uma fonte"""
    animes = []
    for page in range(1, max_pages + 1):
        url = f"{source['list_url']}{source['suffix']}{page}"
        logger.info(f"[{source['name']}] Página {page}: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 403:
                logger.warning(f"{source['name']} bloqueou acesso (403)")
                break
            if resp.status_code != 200:
                logger.warning(f"Status {resp.status_code} para {url}")
                break
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('.anime-item, .item, article, .film-item, .flw-item, .entry-item, li.anime')
            if not items:
                logger.info(f"{source['name']}: sem itens na página {page}, parando")
                break
            for item in items:
                try:
                    title_el = item.select_one('h2, h3, h4, .title, .name, a[title]')
                    title = title_el.get_text(strip=True) if title_el else ''
                    link_el = item.select_one('a[href]')
                    link = urljoin(source['list_url'], link_el['href']) if link_el else ''
                    img_el = item.select_one('img')
                    cover = ''
                    if img_el:
                        cover = img_el.get('data-src') or img_el.get('src', '')
                    genres = [g.get_text(strip=True).lower() for g in item.select('.genre, .genres a, .cat')]
                    if title and link and not any(ex in genres for ex in EXCLUDED_GENRES):
                        animes.append({
                            'title': title,
                            'page_url': link,
                            'cover': cover,
                            'genres': genres,
                            'source': source['name'],
                            'dubbed': 'dublado' in title.lower() or 'dub' in title.lower()
                        })
                except Exception:
                    pass
            logger.info(f"{source['name']}: {len(animes)} animes até agora")
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            break
    return animes


def get_episodes(page_url):
    """Obtém links de episódios"""
    try:
        resp = requests.get(page_url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = []
        for sel in ['a[href*="episodio"]', 'a[href*="episode"]', 'a[href*="/ep"]',
                    '.ep-item a', '.episodes a', 'ul.episodios li a', '.episode-list a']:
            found = soup.select(sel)
            if found:
                for l in found:
                    href = l.get('href', '')
                    if href:
                        links.append(urljoin(page_url, href))
                break
        seen = set()
        return [l for l in links if not (l in seen or seen.add(l))][:5]
    except Exception:
        return []


def extract_stream(url):
    """Extrai URL
