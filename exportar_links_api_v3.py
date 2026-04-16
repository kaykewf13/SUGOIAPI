def categorizar_anime_profissional(nome, url):
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
