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

QUALIDADES_PREFERIDAS = ["1080p", "720p"]

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
            title    = item.findtext("title", "").strip()
            seeders  = int(item.findtext("nyaa:seeders", "0", ns) or 0)
            ihash    = item.findtext("nyaa:infoHash", "", ns).lower()
            trusted_flag = item.findtext("nyaa:trusted", "No", ns) == "Yes"

            if not ihash:
                continue

            magnet = (
                f"magnet:?xt=urn:btih:{ihash}"
                f"&dn={quote_plus(title)}"
                f"&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80"
                f"&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
            )

            items.append({
                "title"   : title,
                "magnet"  : magnet,
                "info_hash": ihash,
                "seeders" : seeders,
                "trusted" : trusted_flag,
            })
    except ET.ParseError as e:
        print(f"  ⚠️  Erro parse RSS: {e}")

    return items


def filtrar_qualidade(items: list[dict], qualidades: list[str]) -> list[dict]:
    out = []
    for item in items:
        title_lower = item["title"].lower()
        if any(q in title_lower for q in qualidades):
            out.append(item)
    return out


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
                          max_por_termo: int = 10,
                          qualidades: list[str] = None) -> list[dict]:
    if qualidades is None:
        qualidades = QUALIDADES_PREFERIDAS

    termos = termos_sfw_com_uploader(uploader)
    print(f"\n🎌 SFW: {len(termos)} termos (uploader={uploader})")

    all_items = []
    seen = set()

    for query, categoria in termos:
        items = fetch_rss(query, base=NYAA_BASE, trusted=True)
        items = filtrar_uploader_confiavel(items)
        items = filtrar_qualidade(items, qualidades)
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


def buscar_categoria_adult(max_por_termo: int = 5,
                            qualidades: list[str] = None) -> list[dict]:
    if qualidades is None:
        qualidades = QUALIDADES_PREFERIDAS

    termos = termos_adult()
    print(f"\n🔞 Adult: {len(termos)} termos (sukebei.nyaa.si)")

    all_items = []
    seen = set()

    for query, categoria in termos:
        items = fetch_rss(query, base=SUKEBEI_BASE, trusted=False)
        items = filtrar_qualidade(items, qualidades)
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
                                  max_sfw: int = 10,
                                  max_adult: int = 5) -> list[dict]:
    items_sfw   = buscar_categoria_sfw(max_por_termo=max_sfw)
    items_adult = buscar_categoria_adult(max_por_termo=max_adult) if incluir_adulto else []

    print(f"\n{'─'*48}")
    print(f"  SFW   coletados : {len(items_sfw):>5}")
    print(f"  Adult coletados : {len(items_adult):>5}")
    print(f"  Total           : {len(items_sfw) + len(items_adult):>5}")
    print(f"{'─'*48}\n")

    return items_sfw + items_adult


if __name__ == "__main__":
    items = buscar_animes_por_categoria()
    print(f"\n✅ {len(items)} magnets prontos para enqueue\n")

    from collections import Counter
    cats = Counter(item["category"] for item in items)
    print("📊 Distribuição por categoria:")
    for cat, n in cats.most_common():
        print(f"   {cat:<22} {n:>4}")