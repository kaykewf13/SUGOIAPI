import json
import os
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def normalize_genre(genre):
    """Normaliza nomes de gênero"""
    genre_map = {
        'shounen': 'Shounen',
        'shoujo': 'Shoujo',
        'seinen': 'Seinen',
        'josei': 'Josei',
        'action': 'Action',
        'romance': 'Romance',
        'comedy': 'Comedy',
        'drama': 'Drama',
        'fantasy': 'Fantasy',
        'sci-fi': 'Sci-Fi',
        'slice of life': 'Slice of Life',
        'school': 'School',
        'supernatural': 'Supernatural',
        'mystery': 'Mystery',
        'thriller': 'Thriller',
        'horror': 'Horror',
        'sports': 'Sports',
        'music': 'Music',
        'psychological': 'Psychological'
    }
    return genre_map.get(genre.lower(), genre)

def get_group_title(anime):
    """Retorna o grupo de classificação"""
    if anime.get('dubbed'):
        return 'DUBLADOS'
    return 'LEGENDADOS'

def format_m3u_entry(anime):
    """Formata uma entrada M3U"""
    title = anime.get('title', 'Sem Título')
    url = anime.get('url', '')
    cover = anime.get('cover', '')
    dubbed = anime.get('dubbed', False)
    group = get_group_title(anime)
    genres = ', '.join([normalize_genre(g) for g in anime.get('genres', [])])
    
    if not url:
        logger.warning(f"URL vazia para: {title}")
        return ''
    
    entry = '#EXTINF:-1'
    
    if cover:
        entry += f' tvg-logo="{cover}"'
    
    entry += f' group-title="{group}"'
    
    if genres:
        entry += f' tvg-genre="{genres}"'
    
    if dubbed:
        entry += f' tvg-language="Portuguese"'
    
    entry += f',{title}\n'
    entry += f'{url}\n'
    
    return entry

def generate_m3u(animes, output_file='playlist.m3u'):
    """Gera arquivo M3U completo"""
    
    dubbed = [a for a in animes if a.get('dubbed', False)]
    subbed = [a for a in animes if not a.get('dubbed', False)]
    
    logger.info(f"Dublados: {len(dubbed)} | Legendados: {len(subbed)}")
    
    all_sorted = sorted(animes, key=lambda x: (get_group_title(x), x.get('title', '')))
    
    m3u_content = '#EXTM3U\n'
    m3u_content += f'# Gerado em: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
    m3u_content += f'# Total: {len(animes)} animes\n'
    m3u_content += f'# Dublados: {len(dubbed)} | Legendados: {len(subbed)}\n'
    m3u_content += '\n'
    
    for anime in all_sorted:
        m3u_content += format_m3u_entry(anime)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    
    logger.info(f"Playlist gerada: {output_file} ({len(animes)} entradas)")
    return output_file

def generate_stats(animes):
    """Gera estatísticas da playlist"""
    genres = {}
    dubbed_count = 0
    subbed_count = 0
    
    for anime in animes:
        if anime.get('dubbed'):
            dubbed_count += 1
        else:
            subbed_count += 1
        
        for genre in anime.get('genres', []):
            genre_norm = normalize_genre(genre)
            genres[genre_norm] = genres.get(genre_norm, 0) + 1
    
    stats = {
        'total': len(animes),
        'dubbed': dubbed_count,
        'subbed': subbed_count,
        'genres': dict(sorted(genres.items(), key=lambda x: x[1], reverse=True)),
        'generated_at': datetime.now().isoformat()
    }
    
    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Stats: {stats['total']} total, {dubbed_count} dublados, {subbed_count} legendados")
    return stats

if __name__ == "__main__":
    if not os.path.exists('animes_raw.json'):
        logger.error("animes_raw.json não encontrado. Execute extractor.py primeiro.")
        exit(1)
    
    with open('animes_raw.json', 'r', encoding='utf-8') as f:
        animes = json.load(f)
    
    generate_m3u(animes, 'playlist.m3u')
    generate_stats(animes)
    
    logger.info("Geração concluída!")