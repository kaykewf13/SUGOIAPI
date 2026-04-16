import sys
import pandas as pd
import cloudscraper
import time
import random
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# CONFIGURAÇÃO DE DIRETÓRIOS
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LISTA DE PROVIDERS COM ROTAS CORRIGIDAS (404 FIX)
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

def extrair_universal(html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    # Seletores mais abrangentes para capturar cards em diversos layouts
    cards = soup.select('article, .item, .element, .ani_it, .vosty, .ep_item, .divCardAnime, .anime-card')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            href = link_tag.get('href')
            titulo = link_tag.get('title') or card.get_text(strip=True).split('\n')[0]
            img_tag = card.select_one('img')
            
            imagem = "Sem Imagem"
            if img_tag:
                imagem = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-lazy-src') or "Sem Imagem"

            if titulo and href:
                items.append({
                    "Anime": titulo.strip()[:120],
                    "URL": href if href.startswith('http') else f"https://{provider_name}.com{href}",
                    "Imagem": imagem,
                    "Tipo": "Dublado" if "dublado" in titulo.lower() else "Legendado",
                    "Provider": provider_name,
                    "Data": datetime.now().strftime("%d/%m/%Y")
                })
        except: continue
    return items

def main():
    # Scraper com emulação de navegador moderno
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []
    
    PAGINAS_POR_PROVIDER = 10 

    for p in PROVIDERS:
        print(f"📡 Varrendo: {p['name']}")
        for pg in range(1, PAGINAS_POR_PROVIDER + 1):
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            
            # TÉCNICA DE CAMUFLAGEM: Referer Dinâmico
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Referer": "https://www.google.com.br/", # Faz o site pensar que veio da pesquisa Google
                "Accept-Language": "pt-BR,pt;q=0.9"
            }
            
            try:
                time.sleep(random.uniform(3, 6)) # Pausa humana para evitar 403
                res = scraper.get(url, headers=headers, timeout=30)
                
                if res.status_code == 200:
                    dados = extrair_universal(res.text, p['name'])
                    if not dados: break
                    todas_listas.extend(dados)
                    print(f"   ✅ Pg {pg}: {len(dados)} capturados.")
                else:
                    print(f"   🛑 Status {res.status_code} na pg {pg}")
                    break
            except Exception as e:
                print(f"   ❌ Erro: {str(e)[:50]}")
                break

    if todas_listas:
        df = pd.DataFrame(todas_listas)
        df = df.drop_duplicates(subset=['Anime', 'Provider'])
        
        # Salva o catálogo principal
        df.to_csv(OUTPUT_DIR / "catalogo_global.csv", index=False, encoding='utf-8-sig')
        df.to_excel(OUTPUT_DIR / "catalogo_global.xlsx", index=False)
        print(f"✨ Sucesso! {len(df)} animes catalogados.")

if __name__ == "__main__":
    main()
