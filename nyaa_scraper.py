"""
SUGOIAPI — nyaa_scraper.py v2

Coleta magnets do Nyaa.si (SFW) e Sukebei (adulto) classificando por categoria.
A classificação vem da lista curada em termos_categorias.py — cada anime tem
sua categoria pré-definida (Shounen, Isekai, Hentai, etc.).
"""

import time
import requests
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from termos_categorias import termos_sfw_com_uploader, termos_adult

NYAA_BASE   = "https://nyaa.si"
SUKEBEI_BASE = "https://sukebei.nyaa.si"

# Qualidade única — fallback para 1080p só se não houver 720p
QUALIDADE_PRIMARIA  = "720p"
QUALIDADE_FALLBACK  = "1080p"

TRUSTED_UPLOADERS = [
    "subsplease", "erai-raws", "judas", "asw",
    "[subsplease]", "[erai-raws]", "[judas]", "[asw]",
]


def _user_agent():
    return {"User-Agent": "Mozilla/5.0 (compatible; SUGOIAPI/2.0)"}


def fetch_rss(query: str, base: str = NYAA_BASE, trusted: bool = True) -> list[dict]:
    params = {"page": "rss", "q": query}
    if base == NYAA_BASE:
        params["c"] = "1_2"
        params["f"] = "2" if trusted else "0"
    else:
        params["c"] = "1_1"

    qs = "&".join(f"{k}={quote_plus(v)}" for k, v in params.items())
    url = f"{base}/?{qs}"

    try:
        r = requests.get(url, headers=_user_agent(), timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  ⚠️  RSS erro: {e}")
        return []

    items = []
    try:
        root = ET.fromstring(r.text)
        ns   = {"nyaa": "https://nyaa.si/xmlns/nyaa"}

        for item in root.findall(".//item"):
            title     = item.findtext("title", "").strip()
            seeders   = int(item.findtext("nyaa:seeders", "0", ns) or 0)
            leechers  = int(item.findtext("nyaa:leechers", "0", ns) or 0)
            completed = int(item.findtext("nyaa:downloads", "0", ns) or 0)
            ihash     = item.findtext("nyaa:infoHash", "", ns).lower()
            trusted_flag = item.findtext("nyaa:trusted", "No", ns) == "Yes"

            if not ihash:
                continue

            magnet = (
                f"magnet:?xt=urn:btih:{ihash}"
                f"&dn={quote_plus(title)}"
                f"&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80"
                f"&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
            )

            # Score composto: seeders*2 + leechers*1 + completed*0.1
            peer_score = (seeders * 2) + leechers + (completed * 0.1)

            items.append({
                "title"     : title,
                "magnet"    : magnet,
                "info_hash" : ihash,
                "seeders"   : seeders,
                "leechers"  : leechers,
                "completed" : completed,
                "peer_score": peer_score,
                "trusted"   : trusted_flag,
            })
    except ET.ParseError as e:
        print(f"  ⚠️  Erro parse RSS: {e}")

    return items


def filtrar_qualidade(items: list[dict],
                       qualidade_primaria: str = QUALIDADE_PRIMARIA,
                       qualidade_fallback: str = QUALIDADE_FALLBACK) -> list[dict]:
    """
    Prioriza qualidade primaria. Só usa fallback se nenhum item tiver primaria.
    Garante 1 qualidade por busca — não mistura 720p e 1080p.
    """
    primarios = [i for i in items if qualidade_primaria in i["title"].lower()]
    if primarios:
        return primarios
    fallback = [i for i in items if qualidade_fallback in i["title"].lower()]
    return fallback


def filtrar_uploader_confiavel(items: list[dict]) -> list[dict]:
    out = []
    for item in items:
        title_lower = item["title"].lower()
        if item.get("trusted"):
            out.append(item)
            continue
        if any(u in title_lower for u in TRUSTED_UPLOADERS):
            out.append(item)
    return out


def buscar_categoria_sfw(uploader: str = "subsplease",
                          max_por_termo: int = 10) -> list[dict]:
    termos = termos_sfw_com_uploader(uploader)
    print(f"\n🎌 SFW: {len(termos)} termos (uploader={uploader}) — qualidade {QUALIDADE_PRIMARIA}")

    all_items = []
    seen = set()

    for query, categoria in termos:
        items = fetch_rss(query, base=NYAA_BASE, trusted=True)
        items = filtrar_uploader_confiavel(items)
        items = filtrar_qualidade(items)
        items.sort(key=lambda x: x.get("seeders", 0), reverse=True)
        items = items[:max_por_termo]

        novos = 0
        for item in items:
            ih = item["info_hash"]
            if ih in seen:
                continue
            seen.add(ih)
            all_items.append({
                "magnet"   : item["magnet"],
                "title"    : item["title"],
                "category" : categoria,
                "logo"     : "",
                "info_hash": ih,
                "seeders"  : item.get("seeders", 0),
            })
            novos += 1

        if novos > 0:
            print(f"   [{categoria:<22}] {query[:40]:<42} → +{novos}")
        time.sleep(0.5)

    return all_items


def buscar_categoria_adult(max_por_termo: int = 5) -> list[dict]:
    termos = termos_adult()
    print(f"\n🔞 Adult: {len(termos)} termos (sukebei.nyaa.si) — qualidade {QUALIDADE_PRIMARIA}")

    all_items = []
    seen = set()

    for query, categoria in termos:
        items = fetch_rss(query, base=SUKEBEI_BASE, trusted=False)
        items = filtrar_qualidade(items)
        items.sort(key=lambda x: x.get("seeders", 0), reverse=True)
        items = items[:max_por_termo]

        novos = 0
        for item in items:
            ih = item["info_hash"]
            if ih in seen:
                continue
            seen.add(ih)
            all_items.append({
                "magnet"   : item["magnet"],
                "title"    : item["title"],
                "category" : categoria,
                "logo"     : "",
                "info_hash": ih,
                "seeders"  : item.get("seeders", 0),
            })
            novos += 1

        if novos > 0:
            print(f"   [{categoria:<22}] {query[:40]:<42} → +{novos}")
        time.sleep(0.5)

    return all_items


def buscar_animes_por_categoria(incluir_adulto: bool = True,
                                  max_sfw: int = 5,
                                  max_adult: int = 15) -> list[dict]:
    """
    PRIORIDADE: adulto primeiro, com orçamento maior.
    - Adult (Hentai, Milf, Netorare): max 15 torrents/termo
    - SFW (Shounen, Isekai, etc.): max 5 torrents/termo

    Adult vai PRIMEIRO no Put.io — fila de download começa por ele.
    """
    items_adult = buscar_categoria_adult(max_por_termo=max_adult) if incluir_adulto else []
    items_sfw   = buscar_categoria_sfw(max_por_termo=max_sfw)

    # Categoria Ecchi e Harem — também SFW mas com prioridade alta
    # (já está em CATEGORIAS_SFW; aplicamos boost via reordenação abaixo)

    # Reordena: Adult → Ecchi/Harem → resto
    sfw_priority = [i for i in items_sfw if i["category"] in ("Ecchi e Harem",)]
    sfw_outros   = [i for i in items_sfw if i["category"] not in ("Ecchi e Harem",)]

    todos = items_adult + sfw_priority + sfw_outros

    print(f"\n{'─'*48}")
    print(f"  Adult coletados   : {len(items_adult):>5}  (prioridade 1)")
    print(f"  Ecchi/Harem       : {len(sfw_priority):>5}  (prioridade 2)")
    print(f"  Outros SFW        : {len(sfw_outros):>5}  (prioridade 3)")
    print(f"  Total             : {len(todos):>5}")
    print(f"{'─'*48}\n")

    return todos


if __name__ == "__main__":
    items = buscar_animes_por_categoria()
    print(f"\n✅ {len(items)} magnets prontos para enqueue\n")

    from collections import Counter
    cats = Counter(item["category"] for item in items)
    print("📊 Distribuição por categoria:")
    for cat, n in cats.most_common():
        print(f"   {cat:<22} {n:>4}")