import sys
import pandas as pd
import cloudscraper
import time
import random
import re
from pathlib import Path
from bs4 import BeautifulSoup

# CONFIGURAÇÕES
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Providers com maior retorno para estes géneros
PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "Anizero", "url": "https://anizero.org/lista-de-animes", "suffix": "?page="}
]

def classificar_categoria(titulo, genero_site):
    txt = (titulo + " " + genero_site).lower()
    
    # Ordem de prioridade para garantir o nicho
    if any(x in txt for x in ['hentai', '18+', 'adulto', 'uncensored']): return "Hentai"
    if any(x in txt for x in ['ecchi', 'borderline']): return "Ecchi"
    if any(x in txt for x in ['seinen', 'adulto-jovem']): return "Seinen"
    if any(x in txt for x in ['fantasia', 'fantasy', 'isekai', 'magia']): return "Fantasia"
    
    # Caso não encontre nas prioridades, usa o género do site ou Geral
    return genero_site.capitalize() if genero_site else "Geral"

def extrair_v3(scraper, html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    cards = soup.select('article, .item, .element, .divCardAnime, .anime-card')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            raw_title = link_tag.get('title') or card.get_text(" ", strip=True).split('\n')[0]
            titulo_limpo = re.sub(r'^\d+\.?\d*\s*|NOVO\s*|\d{4}\s*|Assistir\s*', '', raw_title).strip()
            
            # Identifica Idioma
            tipo = "Dublado" if "dublado" in raw_title.lower() or "dublado" in link_tag.get('href', '').lower() else "Legendado"
            
            # Captura género original do site
            gen_tag = card.select_one('.genres, .genero, .category, .ani_it_genre')
            gen_site = gen_tag.get_text(strip=True).split(',')[0] if gen_tag else ""
            
            # Aplica lógica de classificação prioritária
            categoria_final = classificar_categoria(titulo_limpo, gen_site)

            items.append({
                "Anime": titulo_limpo,
                "URL": link_tag.get('href'),
                "Imagem": card.select_one('img').get('src', '') if card.select_one('img') else "",
                "Genero": categoria_final,
                "Tipo": tipo
            })
        except: continue
    return items

def main():
    print(f"🚀 SUGOIAPI V3 - CATEGORIAS PRIORITÁRIAS (SEINEN, ECCHI, HENTAI)")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []

    for p in PROVIDERS:
        for pg in range(1, 11): 
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(random.uniform(2, 4))
                res = scraper.get(url, timeout=25)
                if res.status_code == 200:
                    dados = extrair_v3(scraper, res.text, p['name'])
                    if not dados: break
                    todas_listas.extend(dados)
                else: break
            except: break

    if todas_listas:
        df = pd.DataFrame(todas_listas).drop_duplicates(subset=['Anime', 'Tipo'])
        df = df.sort_values(by=['Genero', 'Anime'])

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
            for _, row in df.iterrows():
                # Formato solicitado: Apenas o género no grupo
                grupo = row['Genero']
                nome_exibicao = f"{row['Anime']} [{row['Tipo']}]"
                
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{grupo}", {nome_exibicao}\n')
                f.write(f"{row['URL']}|User-Agent=Mozilla/5.0\n\n")
        
        print(f"✅ Lista Premium gerada com sucesso. Categorias garantidas!")

if __name__ == "__main__":
    main()
