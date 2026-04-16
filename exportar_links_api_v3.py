import requests
import re
import concurrent.futures
import json
import logging
import time
from urllib.parse import urljoin
from pathlib import Path
from datetime import datetime

# =========================================================
# CONFIGURAÇÕES E CONSTANTES
# =========================================================
MAX_WORKERS = 15
TIMEOUT_HEAD = 5
EXPIRATION_LIMIT_HOURS = 6  # TTL dos links no cache
CACHE_FILE = Path("vod_cache_db.json")
LOG_FILE = Path("saude_providers.log")

# Configuração de Logs
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# [DESTAQUE] ALTERE OS SITES ABAIXO
PROVIDERS = [
    {
        "name": "Provider-Anime1",
        "base_url": "https://animefire.io/animes/", 
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    },
  {
        "name": "Provider-Anime2",
        "base_url": "https://animesonlinecc.to/anime/", 
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    },
  {
        "name": "Provider-Anime3",
        "base_url": "https://goyabu.io/lista-de-animes?l=todos/", 
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    },
  
  {
        "name": "Provider-Anime4",
        "base_url": "https://sushianimes.com.br/categories/", 
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    }
]

MEDIA_EXTENSIONS = {".mp4", ".m3u8", ".mkv", ".webm", ".ts"}

# =========================================================
# NÚCLEO DE INTELIGÊNCIA E VALIDAÇÃO
# =========================================================

def validar_link_midia(url, headers):
    """Verifica se a URL é um vídeo real e extrai a resolução."""
    try:
        res = requests.head(url, headers=headers, timeout=TIMEOUT_HEAD, allow_redirects=True)
        content_type = res.headers.get("Content-Type", "").lower()
        
        if any(t in content_type for t in ["video", "mpegurl", "bitstream"]):
            # Extração de Resolução via Regex
            match = re.search(r'(1080p|720p|480p)', url.lower())
            return {
                "url": url, 
                "valid": True, 
                "res": match.group(1).upper() if match else "SD",
                "timestamp": time.time(),
                "fail_count": 0
            }
    except Exception as e:
        logging.error(f"Falha ao validar {url}: {e}")
    return {"url": url, "valid": False}

def gerenciar_cache(resultados_novos):
    """Carrega, limpa e atualiza o banco de dados local de links."""
    cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

    agora = time.time()
    for item in resultados_novos:
        url = item['url']
        # Se o link já existe e não expirou, mantém. Caso contrário, atualiza.
        if url not in cache or (agora - cache[url].get('timestamp', 0)) > (EXPIRATION_LIMIT_HOURS * 3600):
            cache[url] = item

    # Limpeza: Remove itens com mais de 3 falhas seguidas
    cache = {u: d for u, d in cache.items() if d.get('fail_count', 0) < 3}
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    return cache

# =========================================================
# GERAÇÃO DE PLAYLIST VOD (M3U8)
# =========================================================

def gerar_playlist_vod(cache_data):
    """Cria a lista M3U8 organizada por Categorias (Dub/Leg e Filme/Série)."""
    priorizados = {}
    
    for url, dados in cache_data.items():
        nome = dados.get('anime_name', 'Anime Desconhecido')
        
        # Lógica de Categorização
        is_dub = any(x in nome.lower() for x in ["dub", "dublado", "(dub)"])
        idioma = "DUBLADO" if is_dub else "LEGENDADO"
        is_filme = any(x in nome.lower() for x in ["movie", "filme", "longa"])
        categoria = f"{'FILMES' if is_filme else 'SÉRIES'} DE ANIMES ({idioma})"
        
        chave = (nome, categoria)
        rank = {"1080P": 3, "720P": 2, "480P": 1, "SD": 0}
        
        # Priorização de Qualidade: Mantém apenas o melhor link por título/categoria
        if chave not in priorizados or rank.get(dados['res'], 0) > rank.get(priorizados[chave]['res'], 0):
            priorizados[chave] = {**dados, "categoria": categoria}

    with open("vod_animes_final.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for (nome, cat), d in priorizados.items():
            f.write(f'#EXTINF:-1 group-title="{cat}", {nome} [{d["res"]}]\n{d["url"]}\n\n')
    
    print(f"✅ Playlist gerada com {len(priorizados)} títulos únicos.")

# =========================================================
# FLUXO PRINCIPAL
# =========================================================

def main():
    print(f"🚀 Iniciando Media Scraper VOD - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    # Simulação de captura (Aqui entraria a sua lógica de scraping de HTML)
    links_descobertos = [] 
    
    # Validação em Paralelo
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Lógica de processamento...
        pass
    
    # (Exemplo de fluxo final após extração)
    # cache = gerenciar_cache(links_validados)
    # gerar_playlist_vod(cache)

if __name__ == "__main__":
    main()
