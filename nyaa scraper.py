"""
SUGOIAPI — nyaa_scraper.py v3

Coleta magnets do Nyaa.si (SFW) classificando por categoria.

MUDANCA v3:
  - max_por_termo agora conta ITENS NOVOS, nao itens brutos.
  - Cruza com hashes ja existentes (run atual + state persistido do Put.io):
    reconhece existente -> ignora -> puxa o proximo, ate completar a meta.
  - Nao corta a lista do RSS antes de checar duplicados.

A coleta adulta (Sukebei) foi DESATIVADA do fluxo padrao.
"""

import time
import requests
from urllib.parse import quote_plus
from xml.etree import ElementTree as ET

from termos_categorias import termos_sfw_com_uploader

NYAA_BASE = "https://nyaa.si"

QUALIDADE_PRIMARIA = "720p"
QUALIDADE_FALLBACK = "1080p"

TRUSTED_UPLOADERS = [
    "subsplease", "erai-raws", "judas", "asw",
    "[subsplease]", "[erai-raws]", "[judas]", "[asw]",
]


def _user_agent():
    return {"User-Agent": "Mozilla/5.0 (compatible; SUGOIAPI/3.0)"}


def fetch_rss(query: str, base: str = NYAA_BASE, trusted: bool = True) -> list[dict]:
    params = {"page": "rss", "q": query}
    params["c"] = "1_2"
    params["f"] = "2" if trusted else "0"

    qs = "&".join(f"{k}={quote_plus(v)}" for k, v in params.items())
    url = f"{base}/?{qs}"

    try:
        r = requests.get(url, headers=_user_agent(), timeout=8)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  WARN  RSS erro: {e}")
        return []

    items = []
    try:
        root = ET.fromstring(r.text)
        ns = {"nyaa": "https://nyaa.si/xmlns/nyaa"}

        for item in root.findall(".//item"):
            title = item.findtext("title", "").strip()
            seeders = int(item.findtext("nyaa:seeders", "0", ns) or 0)
            leechers = int(item.findtext("nyaa:leechers", "0", ns) or 0)
            completed = int(item.findtext("nyaa:downloads", "0", ns) or 0)
            ihash = item.findtext("nyaa:infoHash", "", ns).lower()
            trusted_flag = item.findtext("nyaa:trusted", "No", ns) == "Yes"

            if not ihash:
                continue

            magnet = (
                f"magnet:?xt=urn:btih:{ihash}"
                f"&dn={quote_plus(title)}"
                f"&tr=udp%3A%2F%2Ftracker.openbittorrent.com%3A80"
                f"&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A1337%2Fannounce"
            )

            peer_score = (seeders * 2) + leechers + (completed * 0.1)

            items.append({
                "title": title,
                "magnet": magnet,
                "info_hash": ihash,
                "seeders": seeders,
                "leechers": leechers,
                "completed": completed,
                "peer_score": peer_score,
                "trusted": trusted_flag,
            })
    except ET.ParseError as e:
        print(f"  WARN  Erro parse RSS: {e}")

    return items


def filtrar_qualidade(items, qualidade_primaria=QUALIDADE_PRIMARIA,
                      qualidade_fallback=QUALIDADE_FALLBACK):
    primarios = [i for i in items if qualidade_primaria in i["title"].lower()]
    if primarios:
        return primarios
    return [i for i in items if qualidade_fallback in i["title"].lower()]


def filtrar_uploader_confiavel(items):
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
                         hashes_existentes: set | None = None) -> list[dict]:
    """
    Coleta ate `max_por_termo` itens NOVOS por termo.

    hashes_existentes: hashes ja no Put.io (vindos do putio_state.json).
    Itens cujo hash ja existe sao ignorados — e o loop PUXA O PROXIMO
    da lista do RSS ate completar a meta de novos.
    """
    termos = termos_sfw_com_uploader(uploader)
    print(f"\n SFW: {len(termos)} termos (uploader={uploader}) — meta {max_por_termo} novos/termo")

    existentes = hashes_existentes or set()
    all_items = []
    seen = set()  # dedup dentro deste run

    for query, categoria in termos:
        items = fetch_rss(query, base=NYAA_BASE, trusted=True)
        items = filtrar_uploader_confiavel(items)
        items = filtrar_qualidade(items)
        items.sort(key=lambda x: x.get("seeders", 0), reverse=True)

        # NOVO: percorre a lista COMPLETA, pulando conhecidos, ate max novos
        novos = 0
        for item in items:  # sem [:max] — preenche ate a meta
            ih = item["info_hash"]
            if ih in seen or ih in existentes:
                continue  # reconhece existente -> ignora -> proximo
            seen.add(ih)
            all_items.append({
                "magnet": item["magnet"],
                "title": item["title"],
                "category": categoria,
                "logo": "",
                "info_hash": ih,
                "seeders": item.get("seeders", 0),
            })
            novos += 1
            if novos >= max_por_termo:
                break

        if novos > 0:
            print(f"   [{categoria:<22}] {query[:40]:<42} → +{novos} novos")
        time.sleep(0.5)

    return all_items


def buscar_animes_por_categoria(max_sfw: int = 10,
                                hashes_existentes: set | None = None,
                                **_compat) -> list[dict]:
    """
    Coleta SFW apenas. Ecchi/Harem recebe prioridade na ordenacao.

    hashes_existentes: passado pelo enqueue_putio para que a coleta
    ignore o que ja esta no Put.io e busque conteudo novo.

    **_compat: aceita e ignora kwargs antigos (incluir_adulto, max_adult)
    para nao quebrar chamadas existentes.
    """
    items_sfw = buscar_categoria_sfw(
        max_por_termo=max_sfw,
        hashes_existentes=hashes_existentes,
    )

    sfw_priority = [i for i in items_sfw if i["category"] == "Ecchi e Harem"]
    sfw_outros = [i for i in items_sfw if i["category"] != "Ecchi e Harem"]
    todos = sfw_priority + sfw_outros

    print(f"\n{'-'*48}")
    print(f"  Ecchi/Harem       : {len(sfw_priority):>5}  (prioridade 1)")
    print(f"  Outros SFW        : {len(sfw_outros):>5}  (prioridade 2)")
    print(f"  Total novos       : {len(todos):>5}")
    print(f"{'-'*48}\n")

    return todos


if __name__ == "__main__":
    items = buscar_animes_por_categoria(max_sfw=10)
    print(f"\nOK {len(items)} magnets novos prontos para enqueue\n")
    from collections import Counter
    cats = Counter(item["category"] for item in items)
    for cat, n in cats.most_common():
        print(f"   {cat:<22} {n:>4}")
