"""
rss_to_putio.py
---------------
Bridge: feeds RSS (rss_sources.py) → Put.io (putio_integration.py).

Reaproveita SOURCES e o fetcher de rss_sources.py, extrai magnets dos
itens RSS e envia ao PutioOrchestrator.enqueue.

Suporta duas formas de magnet no RSS:
  • <link>magnet:?...</link>                      → SubsPlease
  • <nyaa:infoHash>HASH</nyaa:infoHash>           → Nyaa.si (AnimeKaizoku)

Uso standalone (no GitHub Actions):
    python rss_to_putio.py

Uso programático:
    from rss_to_putio import enqueue_putio_from_rss
    n = enqueue_putio_from_rss()
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import quote

from rss_sources import (
    SOURCES,
    LIMITE_POR_FONTE,
    _fetch_rss,
    _extrair_titulo_episodio,
)
from putio_integration import PutioOrchestrator


# Trackers públicos usados quando construímos o magnet a partir do info_hash
# (Nyaa.si não inclui os trackers no RSS, só o hash).
DEFAULT_TRACKERS = [
    "http://nyaa.tracker.wf:7777/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
]


def _magnet_from_item(item: ET.Element, fallback_title: str) -> str | None:
    """
    Tenta extrair um magnet URI de um <item> de RSS, em ordem:
      1. <link> que já comece com 'magnet:'  (SubsPlease)
      2. <nyaa:infoHash> + título            (Nyaa.si)
    Retorna None se nenhum dos dois estiver presente.
    """
    # 1) link direto
    link = (item.findtext("link") or "").strip()
    if link.startswith("magnet:"):
        return link

    # 2) info_hash via tag <nyaa:infoHash> (namespace pode vir prefixado)
    info_hash = None
    for child in item:
        tag = child.tag.split("}")[-1]  # remove '{namespace}'
        if tag == "infoHash" and child.text:
            info_hash = child.text.strip().lower()
            break

    if not info_hash:
        return None

    trackers = "&".join(f"tr={quote(t, safe='')}" for t in DEFAULT_TRACKERS)
    return (
        f"magnet:?xt=urn:btih:{info_hash}"
        f"&dn={quote(fallback_title)}"
        f"&{trackers}"
    )


def coletar_itens_rss() -> list[dict]:
    """
    Varre todos os SOURCES e retorna lista de dicts no formato esperado
    por PutioOrchestrator.enqueue:
        {"magnet": str, "title": str, "category": str}
    """
    out: list[dict] = []

    for fonte, url in SOURCES.items():
        root = _fetch_rss(url)
        if root is None:
            continue

        rss_items = root.findall(".//item")
        limite = LIMITE_POR_FONTE or len(rss_items)
        recortados = rss_items[:limite]

        ok = 0
        for it in recortados:
            titulo_raw = (it.findtext("title") or "").strip()
            if not titulo_raw:
                continue

            # Normaliza para formato "Nome - EP01" — o que parse_serie em
            # pipeline.py reconhece via regex \s*-?\s*EP\.?\s*(\d+).
            # Sem essa normalização, todo episódio vira "Temporada 01 / E01".
            nome_serie, ep = _extrair_titulo_episodio(titulo_raw)
            if ep:
                titulo_norm = f"{nome_serie} - EP{int(ep):02d}"
            else:
                titulo_norm = nome_serie or titulo_raw

            magnet = _magnet_from_item(it, titulo_raw)
            if not magnet:
                continue

            # group_title no formato esperado pelo pipeline.py:
            # "Series | <subcat>" — subcat genérica (Anime) força
            # detectar_categoria_anime(nome) a rodar e categorizar
            # pela keyword presente no título.
            out.append({
                "magnet": magnet,
                "title": titulo_norm,
                "category": "Series | Anime",
                "fonte": fonte,  # metadado, não vira group_title
            })
            ok += 1

        print(f"  {fonte}: {ok}/{len(recortados)} itens com magnet utilizável.")

    return out


def enqueue_putio_from_rss(state_path: str = "putio_state.json") -> int:
    """Coleta itens dos RSSs e envia ao Put.io. Retorna nº de novos transfers."""
    items = coletar_itens_rss()
    orch = PutioOrchestrator(state_path=state_path)
    return orch.enqueue(items)


if __name__ == "__main__":
    print("🔍 Coletando RSS e enviando ao Put.io...\n")
    n = enqueue_putio_from_rss()
    print(f"\n✅ {n} novos magnets enviados ao Put.io.")
