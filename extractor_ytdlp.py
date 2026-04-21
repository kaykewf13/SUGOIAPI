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

STREAM_PATTERNS = [
    r'["\']([^"\']{10,}\.m3u8[^"\']*)["\']',
    r'file:\s*["\']([^"\']{10,}\.mp4[^"\']*)["\']',
    r'"hls":\s*"([^"]+)"',
    r'"stream_url":\s*"([^"]+)"',
    r'"videoUrl":\s*"([^"]+)"',
    r'"contentUrl":\s*"([^"]+)"',
    r'source\s+src=["\']([^"\']{10,})["\']',
    r'["\']([^"\']{10,}\.mp4[^"\']*)["\']',
    r'["\']([^"\']{10,}\.webm[^"\']*)["\']',
    r'jwplayer\([^)]+\)\.setup\(\s*\{[^}]*file:\s*["\']([^"\']+)["\']',
]

MAX_RETRIES = 3
RETRY_BACKOFF = [2, 5, 10]
SAVE_INTERVAL = 5


def fetch_with_retry(url, retries=MAX_RETRIES, **kwargs):
    kwargs.setdefault('headers', HEADERS)
    kwargs.setdefault('timeout', 20)
    last_exc = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, **kwargs)
            if resp.status_code == 429:
                wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)] * 2
                logger.warning(f"Rate limited (429) on {url}, aguardando {wait}s")
                time.sleep(wait)
                continue
            return resp
        except requests.exceptions.ConnectionError as e:
            last_exc = e
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            logger.debug(f"Conexão falhou para {url} (tentativa {attempt+1}/{retries}), aguardando {wait}s")
            time.sleep(wait)
        except requests.exceptions.Timeout as e:
            last_exc = e
            logger.debug(f"Timeout para {url} (tentativa {attempt+1}/{retries})")
            time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
        except requests.exceptions.RequestException as e:
            last_exc = e
            break
    if last_exc:
        raise last_exc
    return None


def run_ytdlp(url):
    try:
        result = subprocess.run(
            ['yt-dlp', '--no-warnings', '--quiet', '--dump-json',
             '--no-playlist', '--extractor-retries', '3',
             '--socket-timeout', '20', '--retries', '3', url],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip().split('\n')[0])
        if result.returncode != 0 and result.stderr:
            logger.debug(f"yt-dlp stderr for {url}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.debug(f"yt-dlp timeout for {url}")
    except json.JSONDecodeError as e:
        logger.debug(f"yt-dlp JSON parse error for {url}: {e}")
    except FileNotFoundError:
        logger.error("yt-dlp não encontrado. Instale com: pip install yt-dlp")
    except Exception as e:
        logger.debug(f"yt-dlp error for {url}: {e}")
    return None


def get_best_url(info):
    if not info:
        return None
    if info.get('url') and info['url'].startswith('http'):
        return info['url']
    formats = info.get('formats', [])
    for fmt in reversed(formats):
        url = fmt.get('url', '')
        if url.startswith('http') and ('.m3u8' in url or '.mp4' in url):
            return url
    for fmt in reversed(formats):
        if fmt.get('url', '').startswith('http'):
            return fmt['url']
    return None


def get_anime_list(source, max_pages=3):
    animes = []
    for page in range(1, max_pages + 1):
        url = f"{source['list_url']}{source['suffix']}{page}"
        logger.info(f"[{source['name']}] Página {page}: {url}")
        try:
            resp = fetch_with_retry(url)
            if resp is None:
                logger.warning(f"{source['name']}: sem resposta para {url}")
                break
            if resp.status_code == 403:
                logger.warning(f"{source['name']} bloqueou acesso (403)")
                break
            if resp.status_code == 404:
                logger.info(f"{source['name']}: página {page} não encontrada (404), parando")
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
                        cover = img_el.get('data-src') or img_el.get('data-lazy-src') or img_el.get('src', '')
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
            logger.error(f"Request error para {source['name']}: {e}")
            break
        except Exception as e:
            logger.error(f"Erro inesperado ao coletar {source['name']}: {e}")
            break
    return animes


def get_episodes(page_url):
    try:
        resp = fetch_with_retry(page_url)
        if resp is None or resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = []
        for sel in ['a[href*="episodio"]', 'a[href*="episode"]', 'a[href*="/ep"]',
                    '.ep-item a', '.episodes a', 'ul.episodios li a', '.episode-list a',
                    'a[href*="ep-"]', 'a[href*="-episodio"]']:
            found = soup.select(sel)
            if found:
                for lnk in found:
                    href = lnk.get('href', '')
                    if href:
                        links.append(urljoin(page_url, href))
                break
        seen = set()
        return [lnk for lnk in links if not (lnk in seen or seen.add(lnk))][:5]
    except requests.exceptions.RequestException as e:
        logger.debug(f"Erro ao buscar episódios de {page_url}: {e}")
        return []
    except Exception as e:
        logger.debug(f"Erro inesperado ao buscar episódios de {page_url}: {e}")
        return []


def extract_stream_from_html(url):
    try:
        resp = fetch_with_retry(url)
        if resp is None or resp.status_code != 200:
            return None
        for pattern in STREAM_PATTERNS:
            for match in re.findall(pattern, resp.text):
                if match.startswith('http'):
                    return match
    except requests.exceptions.RequestException as e:
        logger.debug(f"Erro ao buscar stream HTML de {url}: {e}")
    except Exception as e:
        logger.debug(f"Erro inesperado ao extrair stream de {url}: {e}")
    return None


def extract_stream(url):
    info = run_ytdlp(url)
    stream_url = get_best_url(info)
    if stream_url:
        return stream_url

    stream_url = extract_stream_from_html(url)
    if stream_url:
        return stream_url

    return None


def deduplicate(animes):
    seen = {}
    for a in sorted(animes, key=lambda x: 0 if x.get('dubbed') else 1):
        key = re.sub(r'\s*(dublado|legendado|dub|leg)\s*', '', a['title'].lower()).strip()
        if key not in seen or (a.get('dubbed') and not seen[key].get('dubbed')):
            seen[key] = a
    return list(seen.values())


def save_progress(results, path='streams.json'):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error(f"Erro ao salvar progresso: {e}")


def main():
    all_animes = []
    results = []

    for source in SOURCES:
        logger.info(f"\n=== Coletando {source['name']} ===")
        try:
            animes = get_anime_list(source, max_pages=3)
            logger.info(f"{source['name']}: {len(animes)} animes coletados")
            all_animes.extend(animes)
        except Exception as e:
            logger.error(f"Erro em {source['name']}: {e}")
        time.sleep(3)

    if not all_animes:
        logger.error("Nenhum anime coletado de nenhuma fonte!")
        save_progress([])
        return

    unique = deduplicate(all_animes)
    logger.info(f"\nTotal único: {len(unique)} animes")

    for i, anime in enumerate(unique):
        logger.info(f"[{i+1}/{len(unique)}] Processando: {anime['title']}")
        try:
            episodes = get_episodes(anime['page_url'])

            if not episodes:
                stream_url = extract_stream(anime['page_url'])
                if stream_url:
                    results.append({
                        **anime,
                        'stream_url': stream_url,
                        'episode': 1,
                        'type': 'movie'
                    })
                    logger.info(f"  ✅ Stream direto encontrado")
                else:
                    logger.info(f"  ⚠️ Sem stream para {anime['title']}")
            else:
                logger.info(f"  {len(episodes)} episódios encontrados")
                for ep_num, ep_url in enumerate(episodes, 1):
                    stream_url = extract_stream(ep_url)
                    if stream_url:
                        results.append({
                            **anime,
                            'stream_url': stream_url,
                            'episode': ep_num,
                            'episode_url': ep_url,
                            'type': 'series'
                        })
                    time.sleep(1.5)
        except Exception as e:
            logger.error(f"  Erro ao processar {anime['title']}: {e}")

        time.sleep(2)

        if (i + 1) % SAVE_INTERVAL == 0:
            save_progress(results)
            logger.info(f"  💾 Progresso salvo: {len(results)} streams")

    save_progress(results)
    logger.info(f"\n✅ Extração concluída: {len(results)} streams reais encontrados")


if __name__ == "__main__":
    main()