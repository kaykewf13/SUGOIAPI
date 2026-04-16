import requests
import pandas as pd
import os
import logging  # Essencial para não dar erro no basicConfig
import sys      # Necessário para o sys.exit()
import traceback # Para te mostrar o erro exato no log do GitHub
from pathlib import Path
from datetime import datetime

# =========================================================
# CONFIGURAÇÃO DE DIRETÓRIOS (kaykewf13/SUGOIAPI/output)
# =========================================================

# Detecta o caminho onde o script está rodando
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"

# Cria a pasta de saída (parents=True evita erros de diretório pai inexistente)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = OUTPUT_DIR / "vod_cache_db.json"
LOG_FILE = OUTPUT_DIR / "saude_providers.log"

# Configuração de Log - Agora com o import correto
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# =========================================================
# EXECUÇÃO PROTEGIDA (O SEU ESCUDO)
# =========================================================

def main():
    # Insira aqui sua lógica de busca e exportação
    # Exemplo: df.to_excel(OUTPUT_DIR / "report.xlsx")
    print("🚀 Processando links...")
    pass

if __name__ == "__main__":
    try:
        main()
        print("✅ Script concluído com sucesso!")
    except Exception as e:
        print("\n❌ --- ERRO IDENTIFICADO ---")
        print(f"Tipo do Erro: {type(e).__name__}")
        print(f"Mensagem: {e}")
        print("\n--- RASTRO DO ERRO (TRACEBACK) ---")
        traceback.print_exc() 
        sys.exit(1) # Informa ao GitHub que houve erro, mas mostra qual foi acima

# =========================================================
# CONFIGURAÇÃO DE PROVIDERS (4 ESPAÇOS DEFINIDOS)
# =========================================================
PROVIDERS = [
    {
        "name": "Provider-Anime1",
        "base_url": "https://animefire.io/animes/",
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    },
    {
       "name": "Provider-Anime2",
        "base_url": "https://animesonlinecc.to/anime/",        
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    },
    {
        "name": "Provider-Anime3",
        "base_url": "https://goyabu.io/lista-de-animes?l=todos/",
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    },
    {
        "name": "Provider-Anime4",
        "base_url": "https://sushianimes.com.br/categories/",
        "enabled": True,
        "headers": {"User-Agent": "VLC/3.0.18"}
    }
]

# =========================================================
# FUNÇÕES DE PROCESSAMENTO E EXPORTAÇÃO
# =========================================================

def validar_link_midia(url, headers):
    """Verifica integridade e resolução do vídeo."""
    try:
        res = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
        content_type = res.headers.get("Content-Type", "").lower()
        
        if any(t in content_type for t in ["video", "mpegurl", "bitstream"]):
            # Busca resolução (1080p, 720p, etc)
            match = re.search(r'(1080p|720p|480p)', url.lower())
            return {
                "url": url, 
                "valid": True, 
                "res": match.group(1).upper() if match else "SD",
                "timestamp": time.time(),
                "fail_count": 0
            }
    except Exception as e:
        logging.error(f"Erro ao validar {url}: {e}")
    return {"url": url, "valid": False}

def exportar_dados_finais(dados_validados):
    """Gera CSV e XLSX na pasta de output definida."""
    if not dados_validados:
        return

    df = pd.DataFrame(dados_validados)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    csv_path = BASE_OUTPUT_DIR / f"report_vod_{timestamp}.csv"
    xlsx_path = BASE_OUTPUT_DIR / f"report_vod_{timestamp}.xlsx"

    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df.to_excel(xlsx_path, index=False)
    
    print(f"📊 Relatórios salvos em: {BASE_OUTPUT_DIR}")

def gerar_playlist_m3u(dados_validados):
    """Gera a playlist organizada por categorias VOD."""
    m3u_path = BASE_OUTPUT_DIR / "playlist_vod_final.m3u"
    
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for item in dados_validados:
            nome = item.get('anime_name', 'Anime')
            is_dub = "DUBLADO" if any(x in nome.lower() for x in ["dub", "dublado"]) else "LEGENDADO"
            tipo = "FILMES" if any(x in nome.lower() for x in ["movie", "filme"]) else "SÉRIES"
            categoria = f"{tipo} DE ANIMES ({is_dub})"
            
            f.write(f'#EXTINF:-1 group-title="{categoria}", {nome} [{item["res"]}]\n')
            f.write(f"{item['url']}\n\n")

# =========================================================
# FLUXO DE EXECUÇÃO
# =========================================================

def main():
    print(f"🚀 Iniciando SUGOIAPI VOD - Output: {BASE_OUTPUT_DIR}")
    
    # Exemplo de fluxo:
    # 1. Scraping de links dos 4 providers (Discovery)
    # 2. Validação paralela (ThreadPoolExecutor)
    # 3. Gestão de Cache/Expiração
    # 4. Exportação:
    # exportar_dados_finais(links_processados)
    # gerar_playlist_m3u(links_processados)

if __name__ == "__main__":
    main()
