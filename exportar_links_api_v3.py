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
# 2. FUNÇÃO DE EXTRAÇÃO MELHORADA
# =========================================================
def extrair_universal(html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    # Seletores para cards de animes e episódios
    cards = soup.select('article, .item, .element, .ani_it, .vosty, .ep_item, .divCardAnime, .anime-card')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            href = link_tag.get('href')
            full_text = card.get_text(" ", strip=True)
            titulo = link_tag.get('title') or full_text.split('\n')[0]
            
            img_tag = card.select_one('img')
            imagem = "Sem Imagem"
            if img_tag:
                imagem = img_tag.get('data-src') or img_tag.get('src') or img_tag.get('data-lazy-src') or ""

            if titulo and href:
                url_final = href if href.startswith('http') else f"https://{provider_name.lower()}.com{href}"
                
                # Tenta extrair o número do episódio se existir no texto
                # Exemplo: "Naruto Episódio 10" -> extrai "Episódio 10"
                ep_info = ""
                if "episódio" in full_text.lower():
                    parts = full_text.lower().split("episódio")
                    if len(parts) > 1:
                        ep_num = parts[1].strip().split(" ")[0]
                        ep_info = f" EP {ep_num}"

                items.append({
                    "Anime_Base": titulo.replace("Todos os Episódios", "").strip(),
                    "Titulo_Completo": f"{titulo.strip()}{ep_info}",
                    "URL": url_final,
                    "Imagem": imagem,
                    "Tipo": "Dublado" if "dublado" in titulo.lower() else "Legendado",
                    "Provider": provider_name
                })
        except: continue
    return items

# =========================================================
# 3. LÓGICA PRINCIPAL
# =========================================================
def main():
    print(f"📡 SUGOIAPI V3 - Iniciando Varredura Categorizada")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []
    
    PAGINAS_POR_PROVIDER = 10 

    for p in PROVIDERS:
        print(f"🔍 Provendo: {p['name']}")
        for pg in range(1, PAGINAS_POR_PROVIDER + 1):
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            headers = {"Referer": "https://www.google.com.br/"}
            
            try:
                time.sleep(random.uniform(2.5, 4.5))
                res = scraper.get(url, headers=headers, timeout=30)
                if res.status_code == 200:
                    dados = extrair_universal(res.text, p['name'])
                    if not dados: break
                    todas_listas.extend(dados)
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas)
        df = df.drop_duplicates(subset=['Titulo_Completo', 'Provider'])
        
        # Salva Planilhas
        df.to_csv(OUTPUT_DIR / "catalogo_global.csv", index=False, encoding='utf-8-sig')
        df.to_excel(OUTPUT_DIR / "catalogo_global.xlsx", index=False)
        
        # =========================================================
        # 4. GERAÇÃO DA PLAYLIST M3U POR CATEGORIA E GRUPO
        # =========================================================
        m3u_path = OUTPUT_DIR / "playlist.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            
            for _, row in df.iterrows():
                titulo_lower = row['Titulo_Completo'].lower()
                
                # Classificação: Filme ou Série
                is_movie = any(word in titulo_lower for word in ['filme', 'movie', 'the movie'])
                categoria = "Filmes" if is_movie else "Séries"
                
                # Grupo M3U: Organiza por Anime e Idioma
                # Isso cria "pastas" dentro do player
                grupo_final = f"{categoria} | {row['Anime_Base']} ({row['Tipo']})"
                
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{grupo_final}", {row["Titulo_Completo"]} [{row["Provider"]}]\n')
                f.write(f"{row['URL']}\n")

        print(f"✨ Sucesso! {len(df)} itens organizados em categorias e grupos.")

if __name__ == "__main__":
    main()
