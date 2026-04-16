import sys
import pandas as pd
import cloudscraper
import time
import re
from pathlib import Path

# 1. CONFIGURAÇÕES
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# FONTES GLOBAIS
DIRECTORIES = [
    "https://raw.githubusercontent.com/mariosanthos/IPTV/main/lista%20m3u",
    "https://iptv-org.github.io/iptv/categories/animation.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u"
]

def categorizar_anime_profissional(nome, url):
    """Organiza os animes por tipos e gêneros."""
    txt = (str(nome) + " " + str(url)).lower()
    
    # Ordem de prioridade
    if any(x in txt for x in ['hentai', 'xxx', 'uncensored', '18+']): 
        return "🔞 HENTAI"
    if any(x in txt for x in ['ecchi', 'borderline', 'pantsu']): 
        return "🍑 ECCHI"
    if any(x in txt for x in ['seinen', 'berserk', 'vagabond', 'monster', 'gore']): 
        return "💀 SEINEN"
    if any(x in txt for x in ['shounen', 'shonen', 'luta', 'battle', 'shippuden', 'dragon ball']): 
        return "⚔️ SHONEN"
    if any(x in txt for x in ['filme', 'movie', 'longa-metragem']): 
        return "🎬 FILMES / MOVIES"
    if any(x in txt for x in ['isekai', 'reincarnat', 'outro mundo']): 
        return "🌀 ISEKAI"
    if any(x in txt for x in ['mecha', 'robo', 'gundam', 'evangelion']): 
        return "🤖 MECHA"
    if any(x in txt for x in ['terror', 'horror', 'suspense', 'dark']): 
        return "🌑 TERROR / HORROR"
    if any(x in txt for x in ['esporte', 'sport', 'futebol', 'vôlei', 'ippo']): 
        return "⚽ ESPORTES"
    if any(x in txt for x in ['shoujo', 'romance', 'love', 'drama']): 
        return "🌸 SHOUJO / ROMANCE"
    if any(x in txt for x in ['dublado', 'pt-br', 'dub']): 
        return "🇧🇷 DUBLADOS"
    
    return "📺 ANIME GERAL"

def main():
    print(f"🚀 INICIANDO HUNTER V4 - CATEGORIZAÇÃO POR TIPOS")
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    # Processa Fontes Online
    for url in DIRECTORIES:
        print(f"📡 Varrendo: {url[:50]}...")
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                # Captura nome e link
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://[^\s\n]+)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
        except: continue

    # Processa Fontes Manuais
    caminho_manual = SCRIPT_DIR / "fontes_manuais.txt"
    if caminho_manual.exists():
        print("📁 Lendo fontes manuais...")
        conteudo = caminho_manual.read_text(encoding="utf-8")
        # Regex para capturar links m3u8/mp4/ts no texto manual
        links_txt = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts)[^\s"\'<>]*)', conteudo)
        for l in links_txt:
            acervo.append({"Anime": "VOD Minerado", "URL": l})

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        # Mantém apenas o que o SmartOne consegue ler
        df = df[df['URL'].str.contains(r'\.m3u8|\.mp4|\.ts', case=False, na=False)]

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U x-tvg-url=""\n\n')
            
            for index, row in df.iterrows():
                # CHAMA A FUNÇÃO DE CATEGORIZAÇÃO AQUI DENTRO
                grupo = categorizar_anime_profissional(row['Anime'], row['URL'])
                
                # Limpa caracteres que podem quebrar o M3U
                nome_clean = re.sub(r'[^\w\s\-\[\]]', '', row['Anime'])
                
                # Link com bypass de segurança para o SmartOne
                link_final = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/"
                
                f.write(f'#EXTINF:-1 group-title="{grupo}", {nome_clean}\n')
                f.write(f"{link_final}\n\n")
        
        print(f"✅ Sucesso! {len(df)} links categorizados por tipo e prontos.")

if __name__ == "__main__":
    main()
