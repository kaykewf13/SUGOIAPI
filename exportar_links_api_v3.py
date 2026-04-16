import sys
import logging
import traceback
import pandas as pd
import cloudscraper
import time
from pathlib import Path
from datetime import datetime

# =========================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E LOGS
# =========================================================
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = OUTPUT_DIR / "saude_providers.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# =========================================================
# 2. DEFINIÇÃO DOS PROVIDERS COM HEADERS REAIS
# =========================================================
HEADERS_CHROME = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}

PROVIDERS = [
    {"name": "Provider-Anime1", "base_url": "https://animefire.io/animes/", "enabled": True},
    {"name": "Provider-Anime2", "base_url": "https://animesonlinecc.to/anime/", "enabled": True},
    {"name": "Provider-Anime3", "base_url": "https://goyabu.io/lista-de-animes?l=todos/", "enabled": True},
    {"name": "Provider-Anime4", "base_url": "https://sushianimes.com.br/categories/", "enabled": True}
]

# =========================================================
# 3. LÓGICA DE COLETA COM CLOUDSCRAPER (Anti-403)
# =========================================================
def buscar_links():
    resultados = []
    # Cria o scraper que simula comportamento humano para pular Cloudflare
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})
    
    for p in PROVIDERS:
        if not p["enabled"]:
            continue
            
        print(f"🔍 Tentando acessar: {p['name']}...")
        try:
            # Uso do scraper.get em vez de requests.get
            response = scraper.get(p["base_url"], headers=HEADERS_CHROME, timeout=20)
            
            if response.status_code == 200:
                logging.info(f"SUCESSO [200]: {p['name']}")
                resultados.append({
                    "Anime": f"Catálogo {p['name']}",
                    "URL": p["base_url"],
                    "Status": "Online",
                    "Provider": p["name"],
                    "Data_Verificacao": datetime.now().strftime("%d/%m/%Y %H:%M")
                })
            else:
                logging.warning(f"AVISO [{response.status_code}]: {p['name']}")
                print(f"⚠️ {p['name']} negou o acesso (Status {response.status_code})")
                
            # Pequena pausa para não ser bloqueado por excesso de requisições
            time.sleep(2)
            
        except Exception as e:
            logging.error(f"ERRO FATAL em {p['name']}: {str(e)}")
            print(f"❌ Falha de conexão em {p['name']}")
            
    return resultados

# =========================================================
# 4. EXECUÇÃO E EXPORTAÇÃO
# =========================================================
def main():
    print(f"🚀 Iniciando Varredura - Destino: {OUTPUT_DIR}")
    
    dados = buscar_links()
    
    if not dados:
        print("⚠️ A busca não retornou dados. Verifique saude_providers.log")
        return

    df = pd.DataFrame(dados)

    # Caminhos de saída
    csv_file = OUTPUT_DIR / "catalogo.csv"
    xlsx_file = OUTPUT_DIR / "catalogo.xlsx"

    # Salvando os arquivos
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    df.to_excel(xlsx_file, index=False)
    
    print(f"✅ Concluído! {len(dados)} providers processados com sucesso.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        traceback.print_exc()
        sys.exit(1)
