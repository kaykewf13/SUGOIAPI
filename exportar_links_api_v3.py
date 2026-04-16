import sys
import pandas as pd
import cloudscraper
import time
import random
import traceback
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# =========================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E AMBIENTE
# =========================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LISTA DE PROVIDERS OTIMIZADA (URLs e Sufixos revisados)
PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer-Dub", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "Anizero", "url": "https://anizero.org/lista-de-animes", "suffix": "?page="},
    {"name": "AnimesOnlineClub", "url": "https://animesonlineclub.net/animes", "suffix": "/page/"},
    {"name": "AnimesComix", "url": "https://animescomix.tv/animes", "suffix": "/page/"},
    {"name": "TopAnimes", "url": "https://topanimes.net/animes", "suffix": "/page/"},
    {"name": "Goyabu", "url": "https://goyabu.com/lista-de-animes", "suffix": "/page/"},
    {"name": "AnimeFLV", "url": "https://m.animeflv.net/browse", "suffix": "&page="}
]

# =========================================================
# 2. FUNÇÃO DE EXTRAÇÃO UNIVERSAL (BS4)
# =========================================================
def extrair_universal(html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    # Seletores de containers comuns em sites de streaming
    cards = soup.select('article, .item, .element, .ani_it, .vosty, .ep_item, .divCardAnime, .anime-card')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            href = link_tag.get('href')
            titulo = link_tag.get('title') or card.get_text(strip=True).split('\n')[0]
            img_tag = card.select_one('img')
            
            # Captura de imagem com suporte a lazy-loading
            imagem = "Sem Imagem"
            if img_tag:
                imagem = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-lazy-src') or "Sem Imagem"

            if titulo and href:
                # Normalização de links
                url_final = href if href.startswith('http') else f"https://{provider_name.lower()}.com{href}"
                
                items.append({
                    "Anime": titulo.strip()[:120],
                    "URL": url_final,
                    "Imagem": imagem,
                    "Tipo": "Dublado" if "dublado" in titulo.lower() else "Legendado",
                    "Provider": provider_name,
                    "Data": datetime.now().strftime("%d/%m/%Y")
                })
        except: 
            continue
    return items

# =========================================================
# 3. LOGICA PRINCIPAL DE VARREDURA
# =========================================================
def main():
    print(f"📡 Iniciando SUGOIAPI VOD - {datetime.now().strftime('%H:%M:%S')}")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []
    
    # Reduzido para 10 páginas para garantir estabilidade e evitar 403
    PAGINAS_POR_PROVIDER = 10 

    for p in PROVIDERS:
        print(f"🔍 Varrendo: {p['name']}")
        for pg in range(1, PAGINAS_POR_PROVIDER + 1):
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            
            # Headers com Referer para burlar proteções simples
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://www.google.com.br/",
                "Accept-Language": "pt-BR,pt;q=0.9"
            }
            
            try:
                # Delay aleatório para simular comportamento humano
                time.sleep(random.uniform(3.0, 5.5))
                res = scraper.get(url, headers=headers, timeout=30)
                
                if res.status_code == 200:
                    dados = extrair_universal(res.text, p['name'])
                    if not dados: break # Se a página não tem animes, pula para o próximo provider
                    todas_listas.extend(dados)
                    print(f"   ✅ Pg {pg}: {len(dados)} encontrados.")
                else:
                    print(f"   🛑 Status {res.status_code} na pg {pg}")
                    break
            except Exception as e:
                print(f"   ❌ Erro na pg {pg}: {str(e)[:50]}")
                break

    # =========================================================
    # 4. EXPORTAÇÃO E GERAÇÃO DE PLAYLIST M3U
    # =========================================================
    if todas_listas:
        df = pd.DataFrame(todas_listas)
        df = df.drop_duplicates(subset=['Anime', 'Provider'])
        
        # 4.1. CSV e XLSX
        df.to_csv(OUTPUT_DIR / "catalogo_global.csv", index=False, encoding='utf-8-sig')
        df.to_excel(OUTPUT_DIR / "catalogo_global.xlsx", index=False)
        
        # 4.2. Geração da Playlist M3U (DIRECIONAMENTO IPTV)
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for _, row in df.iterrows():
                # Formatação padrão IPTV: Título, Logo e Link
                f.write(f"#EXTINF:-1 tvg-logo=\"{row['Imagem']}\", {row['Anime']} [{row['Provider']}]\n")
                f.write(f"{row['URL']}\n")

        print("-" * 30)
        print(f"✨ Sucesso! {len(df)} animes únicos catalogados.")
        print(f"📂 Arquivos gerados em: {OUTPUT_DIR}")
    else:
        print("⚠️ Nenhuma informação capturada nesta rodada.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
