import subprocess
import sys
# Tenta importar o pandas; se falhar, instala automaticamente
try:
    import pandas as pd
except ImportError:
    print("🛠️ Pandas não encontrado. Instalando dependências...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas", "openpyxl", "requests"])
    import pandas as pd

# =========================================================
# 1. CONFIGURAÇÃO DE DIRETÓRIOS E LOGS
# =========================================================
# Localiza onde o script está e garante a pasta 'output'
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
# 2. DEFINIÇÃO DOS PROVIDERS
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
# 3. LÓGICA DE COLETA (SIMPLIFICADA PARA VOD)
# =========================================================
def buscar_links():
    resultados = []
    
    for p in PROVIDERS:
        if not p["enabled"]:
            continue
            
        print(f"🔍 Acessando: {p['name']}...")
        try:
            # Tenta uma requisição simples para validar se o site está online
            response = requests.get(p["base_url"], headers=p["headers"], timeout=15)
            
            if response.status_code == 200:
                logging.info(f"Sucesso ao acessar {p['name']}")
                
                # AQUI ENTRARIA O SEU PARSER (BeautifulSoup ou Regex)
                # Exemplo de dado mockado para gerar o arquivo:
                resultados.append({
                    "Anime": f"Exemplo {p['name']}",
                    "URL": p["base_url"],
                    "Status": "Online",
                    "Provider": p["name"],
                    "Data_Verificacao": datetime.now().strftime("%Y-%m-%d %H:%M")
                })
            else:
                logging.warning(f"Provider {p['name']} retornou status {response.status_code}")
                
        except Exception as e:
            print(f"⚠️ Falha ao conectar em {p['name']}")
            logging.error(f"Erro no provider {p['name']}: {str(e)}")
            
    return resultados

# =========================================================
# 4. FUNÇÃO PRINCIPAL E EXPORTAÇÃO
# =========================================================
def main():
    print(f"🚀 Iniciando SUGOIAPI VOD - Diretório: {OUTPUT_DIR}")
    
    # Executa a busca
    dados_finais = buscar_links()
    
    if not dados_finais:
        print("⚠️ Nenhum dado capturado. Verifique os logs.")
        return

    # Cria o DataFrame
    df = pd.DataFrame(dados_finais)

    # Nomes fixos para o GitHub Actions encontrar sempre
    csv_path = OUTPUT_DIR / "catalogo.csv"
    xlsx_path = OUTPUT_DIR / "catalogo.xlsx"
    m3u_path = OUTPUT_DIR / "playlist.m3u"

    # Salva arquivos
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    df.to_excel(xlsx_path, index=False)
    
    # Gera Playlist M3U básica
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for item in dados_finais:
            f.write(f"#EXTINF:-1, {item['Anime']} [{item['Provider']}]\n{item['URL']}\n")

    print(f"✅ Sucesso! {len(dados_finais)} itens exportados para a pasta output.")

# =========================================================
# 5. DISPARADOR FINAL
# =========================================================
if __name__ == "__main__":
    try:
        main()
        print("🏁 Processo concluído com sucesso!")
    except Exception as e:
        print("\n❌ --- ERRO CRÍTICO NO SCRIPT ---")
        traceback.print_exc() 
        sys.exit(1)
