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
    "Referer": "https://www.google.com/"
}

PROVIDERS = [
    {"name": "AnimeFire", "base_url": "https://animefire.net/lista-de-animes/", "page_suffix": "page/"},
    {"name": "AnimesOnline", "base_url": "https://animesonlinecc.to/anime/", "page_suffix": "page/"},
    {"name": "Goyabu", "base_url": "https://goyabu.com/lista-de-animes/", "page_suffix": "page/"},
    {"name": "SushiAnimes", "base_url": "https://sushianimes.com.br/lista-de-animes/", "page_suffix": "page/"}
]

def extrair_dados_html(html, provider_name):
    """Analisa o HTML e extrai títulos e links baseados na estrutura do site."""
    soup = BeautifulSoup(html, 'html.parser')
    items = []
    
    # Busca por padrões comuns de containers de animes (cards)
    # Nota: Estes seletores podem precisar de ajuste conforme o site muda o layout
    articles = soup.find_all(['article', 'div'], class_=['item', 'element', 'ani_it', 'vosty'])
    
    for art in articles:
        link_tag = art.find('a')
        title_tag = art.find(['h2', 'h3', 'span', 'div'], class_=['title', 'nome', 'tt'])
        
        if link_tag and (link_tag.get('title') or title_tag):
            titulo = link_tag.get('title') or title_tag.get_text(strip=True)
            link = link_tag.get('href')
            
            if titulo and link:
                items.append({
                    "Anime": titulo,
                    "URL": link,
                    "Provider": provider_name,
                    "Data_Extração": datetime.now().strftime("%d/%m/%Y")
                })
    return items

def buscar_links_profundo():
    resultados = []
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    MAX_PAGINAS = 50 

    for p in PROVIDERS:
        print(f"🚀 Iniciando Varredura: {p['name']}")
        
        for pagina in range(1, MAX_PAGINAS + 1):
            url = f"{p['base_url']}{p['page_suffix']}{pagina}/" if pagina > 1 else p['base_url']
            
            try:
                response = scraper.get(url, headers=HEADERS_CHROME, timeout=20)
                
                if response.status_code == 200:
                    encontrados = extrair_dados_html(response.text, p['name'])
                    if not encontrados:
                        print(f"   ⚠️ Página {pagina} parece vazia. Pulando provider.")
                        break
                    
                    resultados.extend(encontrados)
                    print(f"   ✅ Pg {pagina}: {len(encontrados)} animes capturados.")
                else:
                    print(f"   🛑 Erro {response.status_code} na página {pagina}.")
                    break
                
                # Respeito ao servidor para evitar banimento de IP
                time.sleep(1) 
                
            except Exception as e:
                print(f"   ❌ Falha na conexão: {e}")
                break

    return resultados

def main():
    print(f"📂 Pasta de Destino: {OUTPUT_DIR}")
    
    lista_animes = buscar_links_profundo()
    
    if not lista_animes:
        print("❌ Nenhum dado foi extraído.")
        return

    df = pd.DataFrame(lista_animes)
    
    # Remove duplicados caso o mesmo anime apareça em duas páginas
    df = df.drop_duplicates(subset=['Anime', 'Provider'])

    # Exportação
    df.to_csv(OUTPUT_DIR / "catalogo_completo.csv", index=False, encoding='utf-8-sig')
    df.to_excel(OUTPUT_DIR / "catalogo_completo.xlsx", index=False)
    
    print(f"✨ Finalizado! Total de {len(df)} animes únicos catalogados.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)
