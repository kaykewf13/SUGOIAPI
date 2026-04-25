"""
rss_sources.py
--------------
Módulo de fontes RSS para o pipeline SUGOIAPI.
Integra SubsPlease (RSS oficial) e AnimeKaizoku (via Nyaa.si).

Uso standalone:
    python rss_sources.py

Uso integrado (importar no exportar_links_api_v3.py):
    from rss_sources import buscar_todos_episodios
"""

import re
import xml.etree.ElementTree as ET
from urllib.request import urlopen, Request
from urllib.error import URLError

# ─── CONFIGURAÇÃO ──────────────────────────────────────────────────────────────

SOURCES = {
    # SubsPlease — RSS oficial, episódios legendados em inglês (1080p)
    "SubsPlease": "https://subsplease.org/rss/?t=1080",

    # AnimeKaizoku — releases no Nyaa.si filtrados pelo grupo
    "AnimeKaizoku": "https://nyaa.si/?page=rss&q=AnimeKaizoku&c=1_2&f=0",
}

# Resolução preferida para SubsPlease (480, 720, 1080)
RESOLUCAO = "720"

# Número máximo de entradas por fonte (0 = sem limite)
LIMITE_POR_FONTE = 100

# group-title padrão para séries
GROUP_TITLE_SERIES = "Anime | Series"

# ───────────────────────────────────────────────────────────────────────────────


def _fetch_rss(url: str) -> ET.Element | None:
    """Faz o fetch do RSS e retorna o root XML."""
    try:
        req = Request(url, headers={"User-Agent": "SUGOIAPI/1.0"})
        with urlopen(req, timeout=15) as resp:
            conteudo = resp.read()
        return ET.fromstring(conteudo)
    except (URLError, ET.ParseError) as e:
        print(f"⚠️  Erro ao buscar {url}: {e}")
        return None


def _extrair_titulo_episodio(titulo_raw: str) -> tuple[str, str]:
    """
    Extrai (nome_serie, episodio) de títulos como:
    '[SubsPlease] Naruto (01) (1080p) [HASH]'
    '[AnimeKaizoku] One Piece - 1000 [1080p]'
    """
    # Remove prefixo do grupo [SubsPlease], [AnimeKaizoku], etc.
    titulo = re.sub(r'^\[.*?\]\s*', '', titulo_raw).strip()

    # Tenta capturar episódio no formato (01), - 01, E01
    ep_match = re.search(r'[-–]\s*(\d{1,4})\b|[Ee](\d{1,4})\b|\((\d{1,4})\)', titulo)
    episodio = ""
    if ep_match:
        episodio = next(g for g in ep_match.groups() if g is not None)
        # Remove o episódio do título para obter o nome da série
        titulo = titulo[:ep_match.start()].strip(" -–")

    # Remove qualificadores de resolução/hash restantes
    titulo = re.sub(r'\s*[\(\[][^\)\]]*[\)\]]', '', titulo).strip()

    return titulo, episodio


def _montar_entrada_m3u(nome_serie: str, episodio: str, link: str, fonte: str) -> str:
    """Monta a linha #EXTINF e a URL para o arquivo .m3u."""
    nome_exibido = f"{nome_serie} - Ep {episodio}" if episodio else nome_serie
    return (
        f'#EXTINF:-1 tvg-name="{nome_exibido}" '
        f'tvg-logo="" '
        f'group-title="{GROUP_TITLE_SERIES} | {fonte}",'
        f'{nome_exibido}\n'
        f'{link}\n'
    )


def buscar_subsplease() -> list[str]:
    """Retorna lista de entradas M3U do SubsPlease."""
    url = SOURCES["SubsPlease"]
    root = _fetch_rss(url)
    if root is None:
        return []

    entradas = []
    channel = root.find("channel")
    items = channel.findall("item") if channel else root.findall(".//item")

    for item in items[:LIMITE_POR_FONTE or len(items)]:
        titulo_raw = item.findtext("title", "")
        link = item.findtext("link", "") or item.findtext("enclosure", "")

        # Preferir o link direto se disponível
        enclosure = item.find("enclosure")
        if enclosure is not None:
            link = enclosure.get("url", link)

        if not link:
            continue

        nome, ep = _extrair_titulo_episodio(titulo_raw)
        entradas.append(_montar_entrada_m3u(nome, ep, link, "SubsPlease"))

    print(f"✅ SubsPlease: {len(entradas)} entradas encontradas.")
    return entradas


def buscar_animekaizoku() -> list[str]:
    """Retorna lista de entradas M3U do AnimeKaizoku via Nyaa.si."""
    url = SOURCES["AnimeKaizoku"]
    root = _fetch_rss(url)
    if root is None:
        return []

    entradas = []
    items = root.findall(".//item")

    for item in items[:LIMITE_POR_FONTE or len(items)]:
        titulo_raw = item.findtext("title", "")
        link = item.findtext("link", "")

        if not link:
            continue

        nome, ep = _extrair_titulo_episodio(titulo_raw)
        entradas.append(_montar_entrada_m3u(nome, ep, link, "AnimeKaizoku"))

    print(f"✅ AnimeKaizoku: {len(entradas)} entradas encontradas.")
    return entradas


def buscar_todos_episodios() -> list[str]:
    """Agrega todas as fontes e retorna lista unificada de entradas M3U."""
    entradas = []
    entradas.extend(buscar_subsplease())
    entradas.extend(buscar_animekaizoku())
    return entradas


def gerar_bloco_m3u(entradas: list[str]) -> str:
    """Converte a lista de entradas em bloco M3U pronto para concatenar."""
    return "\n".join(entradas)


# ─── STANDALONE ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🔍 Buscando fontes RSS...\n")
    entradas = buscar_todos_episodios()

    if entradas:
        saida = "rss_series.m3u"
        with open(saida, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(gerar_bloco_m3u(entradas))
        print(f"\n📁 Arquivo gerado: {saida} ({len(entradas)} entradas)")
    else:
        print("⚠️  Nenhuma entrada encontrada.")