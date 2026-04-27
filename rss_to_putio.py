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


def _canonical_key(nome_serie: str, episodio: str | int | None) -> str:
    """
    Gera uma chave canônica pra um episódio, usada na deduplicação.

    Normaliza o nome:
      • lowercase
      • remove acentos comuns (não trata todos os casos, mas cobre o grosso)
      • remove caracteres especiais (deixa só [a-z0-9 ])
      • colapsa espaços múltiplos

    Episódio vira inteiro com zero-padding pra evitar 'EP1' != 'EP01'.

    Exemplos que viram a mesma chave:
      "[SubsPlease] Frieren - 01 (1080p) [HASH]"     → "frieren|01"
      "[SubsPlease] Frieren - 01 (720p) [HASH]"      → "frieren|01"
      "[Erai-raws] Frieren - 01 [1080p][Multi-Sub]"  → "frieren|01"
    """
    nome = (nome_serie or "").lower()
    # Substitui acentos por equivalentes ASCII (cobertura básica)
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("ã", "a"), ("õ", "o"), ("â", "a"), ("ê", "e"), ("ô", "o"),
                 ("ç", "c"), ("ñ", "n")]:
        nome = nome.replace(a, b)
    # Remove tudo que não é alfanumérico ou espaço
    nome = re.sub(r"[^a-z0-9 ]+", " ", nome)
    # Colapsa espaços
    nome = re.sub(r"\s+", " ", nome).strip()

    if episodio is None or episodio == "":
        ep_norm = ""
    else:
        try:
            ep_norm = f"{int(episodio):02d}"
        except (ValueError, TypeError):
            ep_norm = str(episodio).strip().lower()

    return f"{nome}|{ep_norm}" if ep_norm else nome


# ─── Priorização por qualidade ────────────────────────────────────────────
#
# Política: PREFERIR 480p (mais barato em storage), aceitar 720p como
# fallback quando 480p não existe pra aquele episódio. Resoluções maiores
# (1080p, 2160p) e formatos sem resolução marcada são REJEITADOS.
#
# Comportamento:
#   • Score 0 (ou ausente em ALLOWED) = item descartado antes do dedup
#   • Maior score vence em duplicata
#   • 480p (score 100) > 720p (score 50) → 480 sempre ganha quando coexiste
#   • Se só 720p existe pra um episódio, ele é mantido
#
# Para alterar prioridade, edita os scores. Para aceitar 1080p como
# último recurso, adiciona "1080p": 10 a QUALITY_SCORES.

QUALITY_SCORES = {
    "480p":  100,   # PREFERIDO — economia máxima de storage
    "720p":   50,   # fallback aceitável quando 480p não existe
}

# Regex que captura tokens de resolução em qualquer parte do título.
_RESOLUTION_RE = re.compile(r"\b(360|480|540|720|1080|1440|2160)\s*p\b", re.IGNORECASE)


def _quality_score(titulo: str) -> tuple[int, str]:
    """
    Extrai a resolução do título e retorna (score, label).
    Score == 0 significa que a resolução não está nas aceitas (será descartado).
    """
    m = _RESOLUTION_RE.search(titulo or "")
    if not m:
        return 0, ""
    label = f"{m.group(1)}p".lower()
    return QUALITY_SCORES.get(label, 0), label


def coletar_itens_rss() -> list[dict]:
    """
    Varre todos os SOURCES e retorna lista de dicts no formato esperado
    por PutioOrchestrator.enqueue:
        {"magnet": str, "title": str, "category": str}

    Política de resolução: aceita apenas 480p (preferida) e 720p (fallback).
    Outras resoluções (1080p, 2160p, sem marca) são descartadas no filtro.

    Deduplicação inteligente: o mesmo episódio em múltiplas resoluções/fontes
    é detectado por chave canônica (nome+episódio normalizados). Em caso de
    duplicata, GANHA o item com maior `_quality_score` — que com a política
    atual significa: 480p sempre vence 720p quando coexistem.
    """
    # Fase 1: coletar TODOS os candidatos (sem filtrar duplicata ainda)
    candidatos: list[dict] = []
    estatisticas_fonte: dict[str, dict] = {}
    descartados_resolucao_total: int = 0

    for fonte, url in SOURCES.items():
        estatisticas_fonte[fonte] = {
            "total": 0, "com_magnet": 0, "rejeitados_qualidade": 0
        }
        root = _fetch_rss(url)
        if root is None:
            continue

        rss_items = root.findall(".//item")
        limite = LIMITE_POR_FONTE or len(rss_items)
        recortados = rss_items[:limite]
        estatisticas_fonte[fonte]["total"] = len(recortados)

        for it in recortados:
            titulo_raw = (it.findtext("title") or "").strip()
            if not titulo_raw:
                continue

            nome_serie, ep = _extrair_titulo_episodio(titulo_raw)
            if ep:
                titulo_norm = f"{nome_serie} - EP{int(ep):02d}"
            else:
                titulo_norm = nome_serie or titulo_raw

            magnet = _magnet_from_item(it, titulo_raw)
            if not magnet:
                continue

            score, qual_label = _quality_score(titulo_raw)

            # Filtra resoluções fora da política (só 480p e 720p passam).
            # Score 0 = título sem resolução marcada OU resolução não aceita
            # (1080p, 2160p, etc).
            if score == 0:
                estatisticas_fonte[fonte]["rejeitados_qualidade"] += 1
                descartados_resolucao_total += 1
                continue

            key = _canonical_key(nome_serie, ep)

            candidatos.append({
                "magnet": magnet,
                "title": titulo_norm,
                "title_raw": titulo_raw,
                "category": "Series | Anime",
                "fonte": fonte,
                "key": key,
                "score": score,
                "quality": qual_label or "?",
            })
            estatisticas_fonte[fonte]["com_magnet"] += 1

    # Fase 2: deduplicar por chave canônica, mantendo o de maior score.
    # Itens sem chave (sem episódio detectado) entram todos — não dedup.
    melhor_por_chave: dict[str, dict] = {}
    sem_chave: list[dict] = []
    duplicados_descartados: list[tuple[str, str, str]] = []  # (key, perdedor, vencedor)

    for cand in candidatos:
        key = cand.get("key")
        if not key:
            sem_chave.append(cand)
            continue

        atual = melhor_por_chave.get(key)
        if atual is None:
            melhor_por_chave[key] = cand
            continue

        if cand["score"] > atual["score"]:
            # Novo candidato é melhor → substitui
            duplicados_descartados.append(
                (key, f"{atual['fonte']}/{atual['quality']}",
                      f"{cand['fonte']}/{cand['quality']}")
            )
            melhor_por_chave[key] = cand
        else:
            # Atual permanece, novo é descartado
            duplicados_descartados.append(
                (key, f"{cand['fonte']}/{cand['quality']}",
                      f"{atual['fonte']}/{atual['quality']}")
            )

    # Fase 3: monta o output final, removendo metadados internos
    out: list[dict] = []
    for cand in list(melhor_por_chave.values()) + sem_chave:
        out.append({
            "magnet": cand["magnet"],
            "title": cand["title"],
            "category": cand["category"],
            "fonte": cand["fonte"],
        })

    # ─── Logs ──────────────────────────────────────────────────────────
    for fonte, st in estatisticas_fonte.items():
        rejeitados = st.get("rejeitados_qualidade", 0)
        msg = f"  {fonte}: {st['com_magnet']}/{st['total']} aceitos"
        if rejeitados:
            msg += f" ({rejeitados} rejeitados por resolução não-permitida)"
        msg += "."
        print(msg)

    if descartados_resolucao_total:
        aceitas = ", ".join(QUALITY_SCORES.keys())
        print(f"\n  📐 Política de resolução: aceita apenas [{aceitas}].")
        print(f"     {descartados_resolucao_total} itens descartados por estarem fora.")

    if duplicados_descartados:
        print(f"\n  🧹 Dedup: {len(duplicados_descartados)} duplicatas resolvidas.")
        # Mostra até 5 exemplos pra debug
        for key, perdedor, vencedor in duplicados_descartados[:5]:
            print(f"     • {key}: descartado {perdedor} (mantido {vencedor})")
        if len(duplicados_descartados) > 5:
            print(f"     ... e mais {len(duplicados_descartados) - 5}.")

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