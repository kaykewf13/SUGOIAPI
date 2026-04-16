import sys
import pandas as pd
import cloudscraper
import time
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup

# 1. CONFIGURAÇÕES DE AMBIENTE
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Lista de busca focada em repositórios e listas públicas (últimos 12 meses)
SEARCH_QUERIES = [
    "https://github.com/search?q=anime+m3u8+dublado+2025&type=code",
    "https://github.com/search?q=playlist+animes+iptv+2026&type=repositories",
    "https://anizero.org/lista-de-animes",
    "https://animeshd.to/animes"
]

def validar_vod_direto(url):
    """Verifica se o link termina em formato aceito pelo SmartOne."""
    extensoes = ('.m3u8', '.mp4', '.ts', '.mkv', '.avi')
    return any(url.lower().split('?')[0].endswith(ext) for ext in extensoes)

def extrair_links_m3u8(scraper, url_alvo):
    """Varre uma página ou código fonte em busca de URLs de vídeo."""
    links_encontrados = []
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res = scraper.get(url_alvo, headers=headers, timeout=15)
        if res.status_code == 200:
            # Regex potente para pegar links m3u8/mp4 em qualquer lugar (HTML, JS ou JSON)
            regex = r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts)[^\s"\'<>]*)'
            matches = re.findall(regex, res.text)
            for m in matches:
                if "http" in m:
                    links_encontrados.append(m)
    except:
        pass
    return list(set(links_encontrados))

def main():
    print(f"🚀 INICIANDO MINERAÇÃO GLOBAL VOD (GITHUB & PÚBLICOS)")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows'})
    todas_listas = []

    for url_busca in SEARCH_QUERIES:
        print(f"📡 Investigando fonte: {url_busca[:50]}...")
        try:
            time.sleep(random.uniform(3, 5))
            res = scraper.get(url_busca, timeout=20)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, 'html.parser')
                
                # Procura links que levam a arquivos ou páginas de vídeo
                potenciais = soup.find_all('a', href=True)
                for p in potenciais:
                    href = p['href']
                    if not href.startswith('http'): 
                        continue
                        
                    # Se o link já for um m3u8 direto, adiciona. 
                    # Se for uma página, tenta minerar o código dela.
                    if validar_vod_direto(href):
                        print(f"   🎯 Link VOD direto encontrado!")
                        todas_listas.append({"Anime": p.get_text()[:40], "URL": href})
                    else:
                        # Deep mining: entra no link para ver se tem um m3u8 escondido
                        deep_links = extrair_links_m3u8(scraper, href)
                        for dl in deep_links:
                            todas_listas.append({"Anime": "VOD Minerado", "URL": dl})
        except:
            continue

    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['URL'])
        
        # Filtro de Gênero/Idioma (Baseado na URL ou Nome)
        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url=""\n\n')
            for _, row in df.iterrows():
                # Tenta classificar o gênero por palavras-chave na URL
                txt = row['URL'].lower()
                cat = "Geral"
                if "dublado" in txt or "portuguese" in txt: cat = "DUBLADOS"
                elif "action" in txt or "acao" in txt: cat = "AÇÃO"
                elif "hentai" in txt or "ecchi" in txt: cat = "ADULTO"
                
                # Formato PREMIUM para Smart TVs
                f.write(f'#EXTINF:-1 group-title="{cat}", {row["Anime"]}\n')
                # Adiciona o User-Agent necessário para o IPTV Pro/SmartOne
                f.write(f"{row['URL']}|User-Agent=Mozilla/5.0\n\n")
        
        print(f"✅ Sucesso! {len(df)} links VOD prontos para Smart TV.")

if __name__ == "__main__":
    main()
