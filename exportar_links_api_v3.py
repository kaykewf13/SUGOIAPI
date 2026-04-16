import sys
import pandas as pd
import cloudscraper
import time
import random
import re
import traceback
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# =========================================================
# 1. CONFIGURAÇÕES DE AMBIENTE
# =========================================================
# Define o caminho absoluto para garantir que o Git encontre os arquivos
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "Goyabu", "url": "https://goyabu.com/lista-de-animes", "suffix": "/page/"}
]

# =========================================================
# 2. FUNÇÕES DE EXTRAÇÃO DE VÍDEO (DEEP SCRAPING)
# =========================================================
def buscar_video_direto(scraper, url_pagina):
    """Tenta capturar o link real do streaming (m3u8/mp4) ou Iframe."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": url_pagina
    }
    try:
        # Timeout estendido para evitar o erro de 'Time Out'
        res = scraper.get(url_pagina, headers=headers, timeout=30)
        if res.status_code != 200: return url_pagina
        
        # Procura padrões de vídeo no HTML/Scripts
        video_links = re.findall(r'(https?://[^\s"\']+\.(?:m3u8|mp4))', res.text)
        if video_links: return video_links[0]
            
        # Procura por Iframes de players externos
        soup = BeautifulSoup(res.text, 'html.parser')
        iframe = soup.find('iframe')
        if iframe and iframe.get('src'):
            return iframe.get('src')
    except:
        pass
    return url_pagina

# =========================================================
# 3. LÓGICA PRINCIPAL DE VARREDURA
# =========================================================
def main():
    print(f"🚀 INICIANDO SUGOIAPI V3 - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []

    for p in PROVIDERS:
        print(f"📡 Processando Provider: {p['name']}")
        # Varredura limitada para evitar bloqueios por excesso de requisições
        for pg in range(1, 4): 
            url_lista = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(random.uniform(4, 7)) # Delay humano para evitar 403
                res = scraper.get(url_lista, timeout=30)
                
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, 'html.parser')
                    cards = soup.select('article, .item, .element, .divCardAnime')
                    
                    for card in cards:
                        link_tag = card.select_one('a')
                        if not link_tag: continue
                        
                        titulo = link_tag.get('title') or card.get_text(strip=True)
                        url_origem = link_tag.get('href')
                        if not url_origem.startswith('http'): 
                            url_origem = f"{p['url'].split('/animes')[0]}{url_origem}"
                        
                        img_tag = card.select_one('img')
                        capa = img_tag.get('src') or img_tag.get('data-src') if img_tag else ""

                        # BUSCA PROFUNDA DO LINK DO VÍDEO (Isso resolve o problema de links de página)
                        print(f"   🎬 Investigando fonte: {titulo[:30]}...")
                        link_final = buscar_video_direto(scraper, url_origem)
                        
                        todas_listas.append({
                            "Anime": titulo.strip().replace('"', ''),
                            "URL": link_final,
                            "Imagem": capa,
                            "Provider": p['name'],
                            "Tipo": "Dublado" if "dublado" in titulo.lower() else "Legendado"
                        })
                else: 
                    print(f"   🛑 Provider {p['name']} retornou status {res.status_code}")
                    break
            except Exception as e:
                print(f"   ⚠️ Erro na página {pg}: {str(e)[:50]}")
                break

    # =========================================================
    # 4. GERAÇÃO DA PLAYLIST M3U E LOGS
    # =========================================================
    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['Anime', 'URL'])
        
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n\n")
            for _, row in df.iterrows():
                # Separação Filmes vs Séries
                is_movie = any(x in row['Anime'].lower() for x in ['filme', 'movie'])
                cat = "Filmes" if is_movie else "Séries"
                
                # Identifica o domínio para o Referer
                try:
                    ref_domain = row['URL'].split('/')[2]
                except:
                    ref_domain = "google.com"
                
                # Camuflagem de Header (User-Agent + Referer) para evitar 403/Timeout
                link_com_headers = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://{ref_domain}/"
                
                # Tag group-title para criar pastas no player
                grupo = f"{cat} | {row['Provider']} ({row['Tipo']})"
                
                f.write(f'#EXTINF:-1 group-title="{grupo}" tvg-logo="{row["Imagem"]}", {row["Anime"]} [{row["Provider"]}]\n')
                f.write(f"{link_com_headers}\n")
        
        # LOGS CRÍTICOS PARA O GITHUB ACTIONS
        print("-" * 30)
        print(f"✅ Arquivo salvo com sucesso em: {m3u_path.absolute()}")
        print(f"📊 Total de itens catalogados: {len(df)}")
        print("-" * 30)
    else:
        print("⚠️ ERRO: Nenhuma informação foi capturada. Verifique os logs de conexão.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
