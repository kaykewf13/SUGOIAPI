"""
Gerador M3U com streams reais extraídos pelo yt-dlp
"""

import json, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GENRE_MAP = {
    'action': 'Ação', 'adventure': 'Aventura', 'comedy': 'Comédia',
    'drama': 'Drama', 'fantasy': 'Fantasia', 'horror': 'Terror',
    'mystery': 'Mistério', 'romance': 'Romance', 'sci-fi': 'Ficção Científica',
    'slice of life': 'Slice of Life', 'supernatural': 'Sobrenatural',
    'isekai': 'Isekai', 'ecchi': 'Ecchi', 'mecha': 'Mecha',
    'shounen': 'Shounen', 'shoujo': 'Shoujo', 'seinen': 'Seinen',
}

def get_group(s):
    audio = 'Dublado' if s.get('dubbed') else 'Legendado'
    genres = s.get('genres', [])
    genre = GENRE_MAP.get(genres[0].lower().strip(), genres[0].title()) if genres else ''
    return f"Anime {audio} | {genre}" if genre else f"Anime {audio}"

def generate_m3u(streams):
    dubbed = [s for s in streams if s.get('dubbed')]
    subbed = [s for s in streams if not s.get('dubbed')]
    sorted_streams = sorted(streams, key=lambda x: (get_group(x), x.get('title',''), x.get('episode',1)))

    m3u = '#EXTM3U\n'
    m3u += f'# Gerado em: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
    m3u += f'# Total: {len(streams)} | Dublados: {len(dubbed)} | Legendados: {len(subbed)}\n\n'

    for s in sorted_streams:
        title = s.get('title', 'Sem título')
        ep = s.get('episode', 1)
        cover = s.get('cover', '')
        group = get_group(s)
        url = s.get('stream_url', '')
        is_dubbed = s.get('dubbed', False)
        name = f"{title} - Ep {ep:02d}" if s.get('type') == 'series' else title
        name = name.replace(',', ' -')

        m3u += f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{cover}" group-title="{group}"'
        if is_dubbed:
            m3u += ' tvg-language="Portuguese"'
        m3u += f',{name}\n{url}\n'

    os.makedirs('docs', exist_ok=True)
    for path in ['playlist.m3u', 'docs/playlist.m3u']:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(m3u)

    stats = {'total': len(streams), 'dubbed': len(dubbed), 'subbed': len(subbed),
             'generated_at': datetime.now().isoformat()}
    with open('docs/stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    logger.info(f"Playlist gerada: {len(streams)} streams reais")

if __name__ == "__main__":
    if not os.path.exists('streams.json'):
        logger.error("streams.json não encontrado")
        exit(1)
    with open('streams.json', 'r', encoding='utf-8') as f:
        streams = json.load(f)
    generate_m3u(streams)
