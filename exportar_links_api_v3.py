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

def categorizar_por_tipo(nome, url):
    """Lógica expandida para todos os tipos de anime."""
    txt = (nome + " " + url).lower()
    
    # Ordem de prioridade (Tipos e Gêneros)
    if any(x in txt for x in ['hentai', 'xxx', 'adulto']): return "🔞 HENTAI"
    if any(x in txt for x in ['ecchi', 'pantsu', 'borderline']): return "🍑 ECCHI"
    if any(x in txt for x in ['filme', 'movie', 'longa']): return "🎬 FILMES"
    if any(x in txt for x in ['isekai', 'reincarnat', 'outro mundo']): return "🌀 ISEKAI"
    if any(x in txt for x in ['shonen', 'shounen', 'luta', 'battle', 'dbz', 'naruto']): return "⚔️ SHONEN"
    if any(x in txt for x in ['seinen', 'gore', 'adulto-jovem', 'berserk']): return "💀 SEINEN"
    if any(x in txt for x in ['shoujo', 'romance', 'love', 'drama']): return "🌸 SHOUJO / ROMANCE"
    if any(x in txt for x in ['mecha', 'robo', 'gundam']): return "🤖 MECHA"
    if any(x in txt for x in ['terror', 'horror', 'suspense']): return "🌑 TERROR"
    if any(x in txt for x in ['esporte', 'sport', 'futebol', 'ippo']): return "⚽ ESPORTES"
    if any(x in txt for x in ['dublado', 'pt-br', 'dub']): return "🇧🇷 DUBLADOS"
    
    return "📺 ANIME GERAL"

def main():
    print(f"🚀 INICIANDO HUNTER V4 - CATEGORIZAÇÃO POR TIPOS")
    scraper = cloudscraper.create_scraper()
    acervo = []
    
    # Fontes Online
    for url in DIRECTORIES:
        try:
            res = scraper.get(url, timeout=20)
            if res.status_code == 200:
                matches = re.findall(r'#EXTINF:.*?,(.*?)\n(https?://[^\s\n]+)', res.text, re.IGNORECASE)
                for nome, link in matches:
                    acervo.append({"Anime": nome.strip(), "URL": link.strip()})
        except: continue

    # Fontes Manuais (fontes_manuais.txt)
    caminho_manual = SCRIPT_DIR / "fontes_manuais.txt"
    if caminho_manual.exists():
        conteudo = caminho_manual.read_text(encoding="utf-8")
        links_txt = re.findall(r'(https?://[^\s"\'<>]+(?:\.m3u8|\.mp4|\.ts)[^\s"\'<>]*)', conteudo)
        for l in links_txt:
            acervo.append({"Anime": "VOD Minerado", "URL": l})

    if acervo:
        df = pd.DataFrame(acervo).drop_duplicates(subset=['URL'])
        df = df[df['URL'].str.contains(r'\.m3u8|\.mp4|\.ts', case=False, na=False)]

        m3u_path = OUTPUT_DIR / "playlist_premium.m3u"
        with open(m3u_path, "w", encoding="utf-8") as f:
            f.write('#EXTM3U\n\n')
            
            # AQUI ESTAVA O ERRO: Agora o 'row' está dentro do loop correto
            for index, row in df.iterrows():
                grupo = categorizar_por_tipo(row['Anime'], row['URL'])
                nome_clean = re.sub(r'[^\w\s\-\[\]]', '', row['Anime'])
                
                # Bypass de User-Agent e Referer para o SmartOne
                link_final = f"{row['URL']}|User-Agent=Mozilla/5.0&Referer=https://google.com/"
                
                f.write(f'#EXTINF:-1 group-title="{grupo}", {nome_clean}\n')
                f.write(f"{link_final}\n\n")
        
        print(f"✅ Sucesso! {len(df)} links categorizados por tipo.")

if __name__ == "__main__":
    main()

    txt = (nome + " " + url).lower()
    
    # Ordem de prioridade (do mais específico para o mais geral)
    # 1. Conteúdo Adulto e Nicho Prioritário
    if any(x in txt for x in ['hentai', 'xxx', 'uncensored', '18+']): return "🔞 HENTAI"
    if any(x in txt for x in ['ecchi', 'borderline', 'pantsu']): return "🍑 ECCHI"
    
    # 2. Demografias Japonesas
    if any(x in txt for x in ['seinen', 'berserk', 'vagabond', 'monster']): return "💀 SEINEN"
    if any(x in txt for x in ['shounen', 'shonen', 'luta', 'battle', 'shippuden', 'dragon ball']): return "⚔️ SHONEN"
    if any(x in txt for x in ['shoujo', 'romance', 'love', 'drama', 'slice of life']): return "🌸 SHOUJO"
    if any(x in txt for x in ['josei', 'fashion', 'career']): return "💄 JOSEI"
    
    # 3. Gêneros Específicos e Formatos
    if any(x in txt for x in ['filme', 'movie', 'longa-metragem']): return "🎬 FILMES / MOVIES"
    if any(x in txt for x in ['isekai', 'reincarnat', 'outro mundo']): return "🌀 ISEKAI"
    if any(x in txt for x in ['mecha', 'robo', 'gundam', 'evangelion']): return "🤖 MECHA"
    if any(x in txt for x in ['terror', 'horror', 'suspense', 'dark']): return "🌑 TERROR / HORROR"
    if any(x in txt for x in ['esporte', 'sport', 'futebol', 'vôlei', 'ippo']): return "⚽ ESPORTES"
    
    # 4. Idioma (Filtro Final)
    if any(x in txt for x in ['dublado', 'pt-br', 'dub']): return "🇧🇷 DUBLADOS"
    
    return "📺 ANIME GERAL"

# No momento de gravar o arquivo m3u:
grupo = categorizar_anime_profissional(row['Anime'], row['URL'])
