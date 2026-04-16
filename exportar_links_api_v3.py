import sys
import logging
import traceback
import pandas as pd
import cloudscraper
import time
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

# CONFIGURAÇÃO DE DIRETÓRIOS
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS_CHROME = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

PROVIDERS = [
    {"name": "AnimeFire", "base_url": "https://animefire.net/lista-de-animes/", "suffix": "page/"},
    {"name": "AnimesOnline", "base_url": "https://animesonlinecc.to/anime/", "suffix": "page/"},
    {"name": "Goyabu", "base_url": "https://goyabu.com/lista-de-animes/", "suffix": "page/"},
    {"name": "SushiAnimes", "base_url": "https://sushianimes.com.br/lista-de-animes/", "suffix": "page/"}
]

def extrair_dados_site(html, provider_name):
    """Extrai Título, Link, Imagem e Gêneros."""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    
    # Identifica os containers de anime (comum em layouts de grid)
    articles = soup.find_all(['article', 'div'], class_=['item', 'element', 'ani_it', 'vosty', 'ep_item'])
    
    for art in articles:
        try:
            link_tag = art.find('a')
            img_tag = art.find('img')
            # Busca gêneros em tags menores (span ou div dentro do card)
            genre_tags = art.find_all(['span', 'div'], class_=['genres', 'genero', 'cat'])
            generos = ", ".join([g.get_text(strip=True) for g in genre_tags]) if genre_tags else "N/A"
            
            if link_tag:
                titulo = link_tag.get('title') or art.get_text(strip=True).split('\n')[0]
                link = link_tag.get('href')
                # Tenta pegar a imagem de diferentes atributos (lazy loading comum)
                imagem = img_tag.get('data-src') or img_tag.get('src') if img_tag else "Sem Imagem"
                
                if titulo and link:
                    items.append({
                        "Anime": titulo.strip(),
                        "URL": link,
                        "Imagem_Capa": imagem,
                        "Gêneros": generos,
                        "Provider": provider_name,
                        "Data_Extração": datetime.now().strftime("%d/%m/%Y")
                    })
        except:
            continue
    return items

def buscar_links_profundo():
    resultados = []
    # Inicializa o scraper anti-bloqueio
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    MAX_PAGINAS = 50 

    for p in PROVIDERS:
        print(f"🚀 Varredura Profunda: {p['name']}")
        
        for pagina in range(1, MAX_PAGINAS + 1):
            url = f"{p['base_url']}{p['suffix']}{pagina}/" if pagina > 1 else p['base_url']
            
            try:
                print(f"   📄 Lendo página {pagina} de {MAX_PAGINAS}...", end="\r")
                response = scraper.get(url, headers=HEADERS_CHROME, timeout=20)
                
                if response.status_code == 200:
                    encontrados = extrair_dados_site(response.text, p['name'])
                    if not encontrados:
                        print(f"\n   ⚠️ Sem novos dados na página {pagina}. Finalizando {p['name']}.")
                        break
                    
                    resultados.extend(encontrados)
                else:
                    print(f"\n   🛑 Status {response.status_code} na página {pagina}.")
                    break
                
                # Delay curto para evitar sobrecarga e bloqueio de IP
                time.sleep(1.2) 
                
            except Exception as e:
                print(f"\n   ❌ Erro de conexão: {e}")
                break
        print(f"\n   ✅ Total parcial: {len(resultados)} itens.")

    return resultados

def main():
    print(f"📡 SUGOIAPI V3 - Módulo de Extração Visual")
    print("-" * 40)
    
    lista_completa = buscar_links_profundo()
    
    if not lista_completa:
        print("❌ Nenhuma informação foi capturada. Verifique as URLs dos Providers.")
        return

    df = pd.DataFrame(lista_completa)
    
    # Limpeza: Remove animes duplicados entre páginas do mesmo provider
    df = df.drop_duplicates(subset=['Anime', 'Provider'])

    # Geração dos Arquivos
    csv_out = OUTPUT_DIR / "catalogo_visual_premium.csv"
    xlsx_out = OUTPUT_DIR / "catalogo_visual_premium.xlsx"

    df.to_csv(csv_out, index=False, encoding='utf-8-sig')
    df.to_excel(xlsx_out, index=False)
    
    print("-" * 40)
    print(f"✨ Missão Cumprida!")
    print(f"📊 Total de Animes Únicos: {len(df)}")
    print(f"📁 Arquivos salvos em: {OUTPUT_DIR}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
