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

PROVIDERS = [
    {"name": "AnimesHD", "url": "https://animeshd.to/animes", "suffix": "/page/"},
    {"name": "AnimePlayer", "url": "https://animeplayer.com.br/genero/dublado", "suffix": "/page/"},
    {"name": "Anizero", "url": "https://anizero.org/lista-de-animes", "suffix": "?page="}
]

def classificar_inteligente(titulo, genero_site):
    txt = (titulo + " " + genero_site).lower()
    
    # Mapeamento de Categorias Balanceadas
    regras = {
        "Hentai": ['hentai', '18+', 'adulto', 'uncensored'],
        "Ecchi": ['ecchi', 'borderline', 'softcore'],
        "Seinen": ['seinen', 'adulto-jovem', 'gore'],
        "Fantasia": ['fantasia', 'fantasy', 'isekai', 'magia', 'adventure', 'aventura'],
        "Ação": ['ação', 'action', 'shonen', 'luta', 'battle'],
        "Romance": ['romance', 'shoujo', 'drama', 'love'],
        "Sci-Fi": ['sci-fi', 'mecha', 'ficção', 'cyberpunk']
    }
    
    for cat, termos in regras.items():
        if any(t in txt for t in termos):
            return cat
            
    return genero_site.capitalize() if genero_site else "Outros"

def extrair_v4(scraper, html, provider_name):
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    cards = soup.select('article, .item, .element, .divCardAnime, .anime-card')
    
    for card in cards:
        try:
            link_tag = card.select_one('a')
            if not link_tag: continue
            
            raw_title = link_tag.get('title') or card.get_text(" ", strip=True).split('\n')[0]
            # Limpeza profissional de título
            titulo_limpo = re.sub(r'^\d+\.?\d*\s*|NOVO\s*|\d{4}\s*|Assistir\s*', '', raw_title).strip()
            
            tipo = "Dublado" if "dublado" in raw_title.lower() or "dublado" in link_tag.get('href', '').lower() else "Legendado"
            
            gen_tag = card.select_one('.genres, .genero, .category, .ani_it_genre')
            gen_site = gen_tag.get_text(strip=True).split(',')[0] if gen_tag else ""
            
            categoria = classificar_inteligente(titulo_limpo, gen_site)

            items.append({
                "Anime": titulo_limpo,
                "URL": link_tag.get('href'),
                "Imagem": card.select_one('img').get('src', '') if card.select_one('img') else "",
                "Genero": categoria,
                "Tipo": tipo
            })
        except: continue
    return items

def main():
    print(f"🚀 SUGOIAPI V4 - EXPANSÃO BALANCEADA (20 PÁGINAS)")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    todas_listas = []

    for p in PROVIDERS:
        print(f"📡 Minerando {p['name']}...")
        # Expansão para 20 páginas por provider
        for pg in range(1, 21): 
            url = f"{p['url']}{p['suffix']}{pg}" if pg > 1 else p['url']
            try:
                time.sleep(random.uniform(1.5, 3)) # Delay otimizado para velocidade
                res = scraper.get(url, timeout=20)
                if res.status_code == 200:
                    dados = extrair_v4(scraper, res.text, p['name'])
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
                grupo = row['Genero']
                nome_exibicao = f"{row['Anime']} [{row['Tipo']}]"
                f.write(f'#EXTINF:-1 tvg-logo="{row["Imagem"]}" group-title="{grupo}", {nome_exibicao}\n')
                f.write(f"{row['URL']}|User-Agent=Mozilla/5.0\n\n")
        
        print(f"✅ Lista Premium Finalizada. Total de {len(df)} itens em categorias equilibradas.")

if __name__ == "__main__":
    main()
