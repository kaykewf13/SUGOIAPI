# yt-dlp extractor for real anime streams.

import yt_dlp

class AnimeExtractor:
    def __init__(self, url):
        self.url = url
        self.ydl_opts = {
            'format': 'best',
            'noplaylist': True,
        }

    def extract(self):
        with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
            info = ydl.extract_info(self.url, download=False)
            return info

# Example usage:
# extractor = AnimeExtractor('https://example.com/anime-stream')
# print(extractor.extract())
