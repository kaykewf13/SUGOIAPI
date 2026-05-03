"""
SUGOIAPI - pipeline.py v3.6.1

Pipeline IPTV que consome multiplas fontes M3U, classifica entradas em
Live/VOD/Series, agrupa por categoria e gera output/playlist_validada.m3u

Mudancas v3.6:
- Bug critico corrigido: parse_serie nao e mais reentrante.
  Antes: chamadas multiplas sobre o mesmo item geravam "Episodio 001 E01 E01 E01"
  Agora: cada item e processado UMA vez; nome e group-title sao deterministicos.
- group-title fixo: "Series | <Categoria> | <NomeSerie>" sem hierarquia infinita
- Deteccao de episodio extrai metadados sem mutar o nome original
"""

import os
import re
import urllib.request
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from categorias import detectar_categoria_anime

# ================================================================
# Config
# ================================================================

SOURCES_LIVE = [
    "https://raw.githubusercontent.com/Drewski2423/DrewLive/main/PlutoTV.m3u8",
    "https://raw.githubusercontent.com/Drewski2423/DrewLive/main/TubiTV.m3u8",
    "https://raw.githubusercontent.com/Drewski2423/DrewLive/main/JapanTV.m3u8",
    "https://raw.githubusercontent.com/Drewski2423/DrewLive/main/DrewLiveVOD.m3u8",
    "https://m3u.ibert.me/jp.m3u",
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_brazil.m3u8",
]

SOURCES_VOD = [
    "sources/putio_entries.m3u",
    "sources/central_animes.m3u",
    "sources/anime_fire.m3u",
    "https://raw.githubusercontent.com/alzamer2/iptv/main/Anime.m3u",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/animes.m3u",
]

OUTPUT_FILE = "output/playlist_validada.m3u"
EPG_URL     = "http://drewlive24.duckdns.org:8081/merged_epg.xml.gz"

VALIDATION_TIMEOUT = 8
MAX_WORKERS_VALIDATION = 20


# ================================================================
# Modelo de dados
# ================================================================

class Item:
    """Representa uma entrada da playlist (canal/filme/episodio)."""

    __slots__ = ("name", "logo", "tvg_name", "url", "kind",
                 "category", "serie_name", "temporada", "episodio")

    def __init__(self, name, url, logo="", tvg_name=""):
        self.name      = name.strip()
        self.url       = url.strip()
        self.logo      = logo.strip()
        self.tvg_name  = tvg_name.strip() or self.name
        self.kind      = "live"
        self.category  = "Geral"
        self.serie_name = ""
        self.temporada = ""
        self.episodio  = ""

    def to_extinf(self):
        """Gera linha #EXTINF + URL para a playlist final."""

        if self.kind == "series":
            display_name = f"{self.serie_name} S{self.temporada}E{self.episodio}"
            group_title  = f"Series | {self.category} | {self.serie_name}"
            tvg_type     = "series"

        elif self.kind == "movie":
            display_name = self.name
            group_title  = f"Filmes | {self.category}"
            tvg_type     = "vod"

        else:
            display_name = self.name
            group_title  = f"Canais | {self.category}"
            tvg_type     = "live"

        extinf = (
            f'#EXTINF:-1 tvg-name="{display_name}" '
            f'tvg-logo="{self.logo}" '
            f'tvg-type="{tvg_type}" '
            f'group-title="{group_title}", {display_name}\n'
            f'{self.url}'
        )
        return extinf


# ================================================================
# Deteccao de episodio (extracao pura, sem mutacao)
# ================================================================

EP_PATTERNS = [
    (re.compile(r"S(\d{1,2})E(\d{1,3})", re.IGNORECASE),
     lambda m: (str(int(m.group(1))).zfill(2), str(int(m.group(2))).zfill(2))),

    (re.compile(r"\bEP\s*(\d{1,3})\b", re.IGNORECASE),
     lambda m: ("01", m.group(1).zfill(2))),

    (re.compile(r"Epis[oó]dio\s*(\d{1,3})", re.IGNORECASE),
     lambda m: ("01", m.group(1).zfill(2))),

    (re.compile(r"Temporada\s*(\d{1,2})", re.IGNORECASE),
     lambda m: (m.group(1).zfill(2), "01")),

    (re.compile(r"(\d+)(?:st|nd|rd|th)\s+Season", re.IGNORECASE),
     lambda m: (m.group(1).zfill(2), "01")),

    (re.compile(r"[\s\-_\.]\s*(\d{2,3})\s*(?:\(|\[|\.|$)"),
     lambda m: ("01", str(int(m.group(1))).zfill(2) if int(m.group(1)) < 100 else m.group(1))),
]


def parse_episode(name):
    """
    Extrai (temporada, episodio) do nome SEM modifica-lo.
    Retorna (None, None) se nao detectar padrao de episodio.
    """
    if not name:
        return None, None

    for pattern, extractor in EP_PATTERNS:
        match = pattern.search(name)
        if match:
            return extractor(match)

    return None, None


def is_episode(name):
    """Retorna True se o nome tem padrao de episodio."""
    temp, ep = parse_episode(name)
    return temp is not None and ep is not None


def extrair_nome_serie(name):
    """
    Remove sufixos de episodio para obter o nome base da serie.
    Exemplo: "Naruto Shippuden S03E15 [1080p]" -> "Naruto Shippuden"
    """
    cleanup_patterns = [
        r"\s*[-_]?\s*S\d{1,2}E\d{1,3}.*",
        r"\s*[-_]?\s*EP\s*\d{1,3}.*",
        r"\s*[-_]?\s*Epis[oó]dio\s*\d{1,3}.*",
        r"\s*[-_]?\s*Temporada\s*\d{1,2}.*",
        r"\s*[-_]?\s*\d+(?:st|nd|rd|th)\s+Season.*",
        r"\s*[-_]?\s*\(?\d{3,4}p\)?.*",
        r"\s*\[.*?\]",
        r"\s*\(.*?\)",
        r"\s*[-_]?\s*\d{2,3}\s*$",
    ]

    nome = name
    for pat in cleanup_patterns:
        nome = re.sub(pat, "", nome, flags=re.IGNORECASE)

    return nome.strip(" -_.|")


# ================================================================
# Parser M3U
# ================================================================

EXTINF_RE   = re.compile(r'#EXTINF:[^,]*,(.+)$')
TVG_NAME_RE = re.compile(r'tvg-name="([^"]*)"')
TVG_LOGO_RE = re.compile(r'tvg-logo="([^"]*)"')


def parse_m3u(content):
    """Parse M3U content para lista de Items."""
    items = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("#EXTINF"):
            url = ""
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if next_line and not next_line.startswith("#"):
                    url = next_line
                    break
                j += 1

            if url:
                tvg_name_match = TVG_NAME_RE.search(line)
                tvg_logo_match = TVG_LOGO_RE.search(line)
                name_match     = EXTINF_RE.search(line)

                tvg_name = tvg_name_match.group(1) if tvg_name_match else ""
                logo     = tvg_logo_match.group(1) if tvg_logo_match else ""
                name     = name_match.group(1).strip() if name_match else tvg_name

                if name and url:
                    items.append(Item(name=name, url=url, logo=logo, tvg_name=tvg_name))

            i = j + 1
        else:
            i += 1

    return items


# ================================================================
# Classificacao (UMA passagem por item - sem recursao)
# ================================================================

def detectar_categoria_canal(name):
    """Categoriza canais ao vivo por keywords no nome."""
    n = name.lower()

    if any(k in n for k in ("brasil", "globo", "sbt", "record", "rede ", "tv brasil", "cultura")):
        return "Brazil"
    if any(k in n for k in ("usa", "fox", "cbs", "nbc", "abc news", "cnn", " us ")):
        return "USA"
    if "pluto tv ca" in n:
        return "PlutoTV CA"
    if "pluto tv uk" in n:
        return "PlutoTV UK"
    if "pluto tv usa" in n or "pluto" in n:
        return "PlutoTV USA"

    return "Geral"


def classificar_item(item):
    """
    Classifica o item em live/movie/series.
    UMA chamada por item. Determinista. Sem recursao.
    """
    url_lower  = item.url.lower()

    # Live: streams .m3u8 ou .ts
    if any(ext in url_lower for ext in (".m3u8", ".ts", "/manifest")):
        item.kind = "live"
        item.category = detectar_categoria_canal(item.name)
        return item

    # Series: padrao de episodio detectavel + URL VOD + nome de serie identificavel
    temp, ep = parse_episode(item.name)
    serie_name = extrair_nome_serie(item.name)
    is_vod_url = (".mp4" in url_lower or ".mkv" in url_lower or "stream" in url_lower)

    if temp and ep and is_vod_url and serie_name and len(serie_name) >= 3:
        item.kind       = "series"
        item.temporada  = temp
        item.episodio   = ep
        item.serie_name = serie_name
        item.category   = detectar_categoria_anime(serie_name) or "Geral"
        return item

    # Movie: .mp4 sem padrao de episodio
    if any(ext in url_lower for ext in (".mp4", ".mkv", ".avi")):
        item.kind = "movie"
        item.category = detectar_categoria_anime(item.name) or "Geral"
        return item

    # Fallback: trata como Live
    item.kind = "live"
    item.category = "Geral"
    return item


# ================================================================
# Validacao de URLs
# ================================================================

def validar_live(url):
    """Valida URL ao vivo via HEAD/GET request."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=VALIDATION_TIMEOUT) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


# ================================================================
# Fetch de fontes
# ================================================================

def fetch_url(url):
    """Busca conteudo de URL ou arquivo local."""
    if url.startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0")
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"  WARN: Falha ao buscar {url}: {e}")
            return ""
    else:
        if os.path.exists(url):
            with open(url, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""


# ================================================================
# Pipeline principal
# ================================================================

def main():
    print("=" * 50)
    print("  SUGOIAPI - Pipeline v3.6.1")
    print("=" * 50 + "\n")

    todos = []
    seen_urls = set()

    # 1. Coletar Live
    print("Coletando fontes Live...\n")
    for src in SOURCES_LIVE:
        content = fetch_url(src)
        if not content:
            continue
        items = parse_m3u(content)
        novos = 0
        for item in items:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            classificar_item(item)
            todos.append(item)
            novos += 1
        print(f"   {src[:60]:<62} -> +{novos}")

    # 2. Coletar VOD
    print("\nColetando fontes VOD/Series...\n")
    for src in SOURCES_VOD:
        content = fetch_url(src)
        if not content:
            continue
        items = parse_m3u(content)
        novos = 0
        for item in items:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            classificar_item(item)
            todos.append(item)
            novos += 1
        print(f"   {src[:60]:<62} -> +{novos}")

    # 3. Validacao (apenas live)
    print("\nValidando URLs Live...\n")
    live_items = [i for i in todos if i.kind == "live"]
    vod_items  = [i for i in todos if i.kind != "live"]

    valid_live = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS_VALIDATION) as executor:
        future_to_item = {executor.submit(validar_live, item.url): item for item in live_items}
        for fut in as_completed(future_to_item):
            item = future_to_item[fut]
            try:
                if fut.result():
                    valid_live.append(item)
            except Exception:
                pass

    print(f"   Live validos: {len(valid_live)}/{len(live_items)}")
    print(f"   VOD aceitos:  {len(vod_items)} (sem validacao)")

    final = valid_live + vod_items

    # 4. Agrupamento e ordenacao
    by_kind = defaultdict(list)
    for item in final:
        by_kind[item.kind].append(item)

    by_kind["series"].sort(key=lambda x: (x.serie_name, x.temporada, x.episodio))
    by_kind["movie"].sort(key=lambda x: (x.category, x.name))
    by_kind["live"].sort(key=lambda x: (x.category, x.name))

    # 5. Escrever output
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        # Header simples - sem comentarios (alguns players nao aceitam)
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}"\n')

        # Escreve em ordem: Live, Filmes, Series (sem separadores em comentarios)
        for item in by_kind["live"]:
            f.write(item.to_extinf() + "\n")
        for item in by_kind["movie"]:
            f.write(item.to_extinf() + "\n")
        for item in by_kind["series"]:
            f.write(item.to_extinf() + "\n")

    print("\n" + "-" * 50)
    print(f"  Total final     : {len(final):>5}")
    print(f"    Canais        : {len(by_kind['live']):>5}")
    print(f"    Filmes        : {len(by_kind['movie']):>5}")
    print(f"    Series        : {len(by_kind['series']):>5}")
    print(f"  Output          : {OUTPUT_FILE}")
    print("-" * 50 + "\n")


if __name__ == "__main__":
    main()
