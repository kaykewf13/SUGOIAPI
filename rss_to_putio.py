"""
rss_to_putio.py
---------------
Bridge: feeds RSS (rss_sources.py) → Put.io (putio_integration.py).

Reaproveita SOURCES e o fetcher de rss_sources.py, extrai magnets dos
itens RSS e envia ao PutioOrchestrator.enqueue.

Suporta múltiplas formas de magnet no RSS (em ordem de preferência):
  • <link>magnet:?...</link>
  • <guid>magnet:?...</guid>                       (SubsPlease)
  • <enclosure url="magnet:?..."/>
  • magnet embebido no <description>               (alguns feeds)
  • <nyaa:infoHash>HASH</nyaa:infoHash>            (Nyaa.si — AnimeKaizoku)

Uso standalone (no GitHub Actions):
    python rss_to_putio.py

Uso programático:
    from rss_to_putio import enqueue_putio_from_rss
    n = enqueue_putio_from_rss()
"""

from __future__ import annotations

import re
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

# Regex para encontrar magnet links embedded em texto (description, etc.)
_MAGNET_INLINE_RE = re.compile(
    r'magnet:\?xt=urn:btih:[A-Za-z0-9]+(?:&[^\s"<>]+)*',
    re.IGNORECASE,
)

# Regex para extrair info_hash isolado (40 hex chars ou 32 base32 chars)
_INFOHASH_RE = re.compile(r'\b([A-Fa-f0-9]{40}|[A-Za-z2-7]{32})\b')


def _sanitize_dn(title: str, max_len: int = 120) -> str:
    """
    Limpa o display name pra um magnet URI:
      - Remove caracteres de controle e quebras de linha
      - Remove sequências problemáticas que confundem o parser do Put.io
      - Trunca pra evitar URIs absurdamente longas
    """
    if not title:
        return "untitled"
    # Remove controls/newlines/tabs
    clean = re.sub(r'[\x00-\x1f\x7f]', '', title)
    # Remove caracteres reservados que costumam causar 400 quando não-encoded
    # mesmo com quote() — testes empíricos mostram que '*' e '?' literais
    # no dn às vezes são rejeitados pelo Put.io.
    clean = re.sub(r'[\*\?\\<>|"]', '', clean)
    clean = clean.strip()
    return clean[:max_len] or "untitled"


def _build_magnet(info_hash: str, title: str) -> str:
    """Monta um magnet URI completo a partir de um info_hash."""
    safe_title = _sanitize_dn(title)
    trackers = "&".join(f"tr={quote(t, safe='')}" for t in DEFAULT_TRACKERS)
    return (
        f"magnet:?xt=urn:btih:{info_hash.lower()}"
        f"&dn={quote(safe_title, safe='')}"
        f"&{trackers}"
    )


def _magnet_from_item(item: ET.Element, fallback_title: str) -> str | None:
    """
    Tenta extrair (ou construir) um magnet URI de um <item> de RSS.
    Retorna None se nenhuma estratégia funcionar.
    """
    # 1) <link> direto
    link = (item.findtext("link") or "").strip()
    if link.startswith("magnet:"):
        return link

    # 2) <guid> — SubsPlease coloca o magnet aqui
    guid = (item.findtext("guid") or "").strip()
    if guid.startswith("magnet:"):
        return guid

    # 3) <enclosure url="magnet:..."/>
    enc = item.find("enclosure")
    if enc is not None:
        enc_url = (enc.get("url") or "").strip()
        if enc_url.startswith("magnet:"):
            return enc_url

    # 4) magnet embebido no <description>
    desc = item.findtext("description") or ""
    m = _MAGNET_INLINE_RE.search(desc)
    if m:
        return m.group(0)

    # 5) <nyaa:infoHash> (namespace pode vir prefixado em ElementTree)
    info_hash = None
    for child in item:
        tag = child.tag.split("}")[-1]  # remove '{namespace}'
        if tag == "infoHash" and child.text:
            info_hash = child.text.strip().lower()
            break

    # 6) Último recurso: info_hash bruto no guid (alguns feeds)
    if not info_hash and guid:
        h = _INFOHASH_RE.search(guid)
        if h:
            info_hash = h.group(1).lower()

    if info_hash:
        return _build_magnet(info_hash, fallback_title)

    return None


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
