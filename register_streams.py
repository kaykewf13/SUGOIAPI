"""
register_streams.py — Integração SUGOIAPI → m3u-proxy
Lê a playlist gerada pelo pipeline e registra cada stream no proxy
com failover automático por título.
"""

import re, os, json, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Configuração ──────────────────────────────────────────────────
PROXY_URL     = os.getenv("PROXY_URL",       "http://localhost:8085")
API_TOKEN     = os.getenv("PROXY_API_TOKEN", "")
M3U_PATH      = Path(__file__).parent / "output" / "playlist_validada.m3u"
HEALTH_PATH   = Path(__file__).parent / "output" / "health.json"
USER_AGENT    = "SUGOIAPI/1.0"
WORKERS       = 20

HEADERS = {"Content-Type": "application/json"}
if API_TOKEN:
    HEADERS["X-API-Token"] = API_TOKEN


# ─────────────────────────────────────────────────────────────────
# 1. Verificar se proxy está acessível
# ─────────────────────────────────────────────────────────────────

def proxy_online() -> bool:
    try:
        r = requests.get(f"{PROXY_URL}/health", timeout=8)
        return r.status_code == 200
    except:
        return False


# ─────────────────────────────────────────────────────────────────
# 2. Limpar streams anteriores
# ─────────────────────────────────────────────────────────────────

def limpar_streams_anteriores():
    try:
        r = requests.get(f"{PROXY_URL}/streams",
                         headers=HEADERS, timeout=10)
        streams = r.json() if r.status_code == 200 else []

        if not streams:
            print("   Nenhum stream anterior encontrado")
            return

        def deletar(stream_id):
            requests.delete(f"{PROXY_URL}/streams/{stream_id}",
                            headers=HEADERS, timeout=8)

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            ex.map(deletar, [s["id"] for s in streams])

        print(f"   {len(streams)} streams anteriores removidos")
    except Exception as e:
        print(f"   ⚠️  Erro ao limpar streams: {e}")


# ─────────────────────────────────────────────────────────────────
# 3. Parse da M3U preservando hierarquia completa
# ─────────────────────────────────────────────────────────────────

def parse_m3u(path: Path) -> list:
    """
    Lê a playlist mantendo toda a estrutura:
      Canais   → grupo | categoria | nome
      Séries   → grupo | categoria | título | temporada | episódio
      Filmes   → grupo | categoria | nome
    """
    streams = []
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            url = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if not url.startswith("http"):
                i += 1
                continue

            # Extrai atributos da linha EXTINF
            tvg_name = re.search(r'tvg-name="([^"]*)"',  line)
            tvg_type = re.search(r'tvg-type="([^"]*)"',  line)
            group    = re.search(r'group-title="([^"]*)"', line)
            title    = re.search(r',\s*(.+)$', line)

            tvg_name = tvg_name.group(1) if tvg_name else ""
            tvg_type = tvg_type.group(1) if tvg_type else "series"
            group    = group.group(1)    if group    else "Geral"
            title    = title.group(1)   if title    else ""

            # Descompõe group-title em hierarquia
            # Formato: "Grupo | Categoria | Título | Temporada"
            partes = [p.strip() for p in group.split("|")]
            grupo     = partes[0] if len(partes) > 0 else "Geral"
            categoria = partes[1] if len(partes) > 1 else "Geral"
            titulo    = partes[2] if len(partes) > 2 else tvg_name
            temporada = partes[3] if len(partes) > 3 else ""

            streams.append({
                "url"      : url,
                "tvg_name" : tvg_name,
                "tvg_type" : tvg_type,
                "grupo"    : grupo,
                "categoria": categoria,
                "titulo"   : titulo,
                "temporada": temporada,
                "episodio" : title,
            })
            i += 2
        else:
            i += 1

    return streams


# ─────────────────────────────────────────────────────────────────
# 4. Agrupar por título para montar failover
# ─────────────────────────────────────────────────────────────────

def agrupar_por_titulo(streams: list) -> dict:
    """
    Agrupa streams do mesmo conteúdo para criar failover automático.
    Chave: grupo|categoria|título|temporada
    Streams extras do mesmo conteúdo viram failover_urls.
    """
    grupos = {}
    for s in streams:
        chave = f"{s['grupo']}|{s['categoria']}|{s['titulo']}|{s['temporada']}"
        grupos.setdefault(chave, []).append(s)
    return grupos


# ─────────────────────────────────────────────────────────────────
# 5. Registrar um stream no proxy
# ─────────────────────────────────────────────────────────────────

def registrar_stream(itens: list) -> dict:
    """
    Recebe lista de streams do mesmo conteúdo.
    O primeiro é o principal, os demais são failover.
    """
    principal = itens[0]
    failovers = [i["url"] for i in itens[1:]]

    payload = {
        "url"          : principal["url"],
        "failover_urls": failovers,
        "user_agent"   : USER_AGENT,
        "metadata": {
            "grupo"    : principal["grupo"],
            "categoria": principal["categoria"],
            "titulo"   : principal["titulo"],
            "temporada": principal["temporada"],
            "episodio" : principal["episodio"],
            "tvg_name" : principal["tvg_name"],
            "tvg_type" : principal["tvg_type"],
        }
    }

    try:
        r = requests.post(
            f"{PROXY_URL}/streams",
            json=payload,
            headers=HEADERS,
            timeout=10
        )
        if r.status_code in (200, 201):
            data = r.json()
            return {
                "ok"        : True,
                "stream_id" : data.get("id", ""),
                "titulo"    : principal["titulo"],
                "failovers" : len(failovers),
            }
        return {"ok": False, "titulo": principal["titulo"],
                "erro": r.status_code}
    except Exception as e:
        return {"ok": False, "titulo": principal["titulo"], "erro": str(e)}


# ─────────────────────────────────────────────────────────────────
# 6. Gerar M3U do proxy (URLs servidas pelo proxy)
# ─────────────────────────────────────────────────────────────────

def gerar_m3u_proxy(resultados: list, streams_originais: dict):
    """
    Gera uma segunda playlist onde cada URL aponta para
    o proxy em vez do link original.
    Players que usarem essa versão terão failover automático.
    """
    m3u_proxy_path = Path(__file__).parent / "output" / "playlist_proxy.m3u"
    epg_url = "http://drewlive24.duckdns.org:8081/merged_epg.xml.gz"

    with open(m3u_proxy_path, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{epg_url}" m3u-type="m3u_plus"\n\n')

        for res in resultados:
            if not res.get("ok") or not res.get("stream_id"):
                continue

            stream_id = res["stream_id"]
            chave     = next(
                (k for k in streams_originais
                 if res["titulo"] in k), None
            )
            if not chave:
                continue

            itens = streams_originais[chave]
            s     = itens[0]
            nome  = re.sub(r'[^\w\s\-]', '', s["tvg_name"]).strip()
            tipo  = s["tvg_type"]
            grupo = s["grupo"]
            cat   = s["categoria"]
            titulo    = s["titulo"]
            temporada = s["temporada"]
            episodio  = s["episodio"]

            if tipo == "live":
                group_title = f"Canais | {cat}"
                label       = nome
                proxy_url   = f"{PROXY_URL}/hls/{stream_id}/playlist.m3u8"
            elif tipo == "movie":
                group_title = f"Filmes | {cat}"
                label       = nome
                proxy_url   = f"{PROXY_URL}/hls/{stream_id}/playlist.m3u8"
            else:
                group_title = f"Series | {cat} | {titulo} | {temporada}"
                label       = episodio or nome
                proxy_url   = f"{PROXY_URL}/hls/{stream_id}/playlist.m3u8"

            f.write(
                f'#EXTINF:-1 tvg-name="{nome}" tvg-type="{tipo}" '
                f'group-title="{group_title}", {label}\n'
            )
            f.write(f'{proxy_url}\n\n')

    print(f"   Playlist proxy → {m3u_proxy_path}")


# ─────────────────────────────────────────────────────────────────
# 7. Atualizar health.json com status do proxy
# ─────────────────────────────────────────────────────────────────

def atualizar_health(registrados: int, com_failover: int, falhas: int):
    if not HEALTH_PATH.exists():
        return
    try:
        with open(HEALTH_PATH) as f:
            data = json.load(f)
        data["proxy"] = {
            "url"          : PROXY_URL,
            "registrados"  : registrados,
            "com_failover" : com_failover,
            "falhas"       : falhas,
            "status"       : "ok" if falhas == 0 else "degraded"
        }
        with open(HEALTH_PATH, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"   ⚠️  health.json: {e}")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # Verifica proxy
    print(f"🔌 Verificando proxy em {PROXY_URL}...")
    if not proxy_online():
        print("❌ Proxy inacessível — abortando integração")
        exit(1)
    print("   ✅ Proxy online")

    # Verifica playlist
    if not M3U_PATH.exists():
        print("❌ playlist_validada.m3u não encontrada — rode pipeline.py primeiro")
        exit(1)

    # Limpa streams anteriores
    print("\n🧹 Limpando streams anteriores...")
    limpar_streams_anteriores()

    # Parse da playlist
    print("\n📋 Lendo playlist gerada...")
    streams = parse_m3u(M3U_PATH)
    print(f"   {len(streams)} streams encontrados")

    # Agrupa por título para failover
    grupos = agrupar_por_titulo(streams)
    com_failover = sum(1 for v in grupos.values() if len(v) > 1)
    print(f"   {len(grupos)} títulos únicos")
    print(f"   {com_failover} com failover configurado")

    # Registra no proxy em paralelo
    print(f"\n📡 Registrando no proxy ({WORKERS} workers)...")
    resultados = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = {ex.submit(registrar_stream, itens): chave
                   for chave, itens in grupos.items()}
        for f in as_completed(futuros):
            resultados.append(f.result())

    # Contagem
    ok     = [r for r in resultados if r.get("ok")]
    falhas = [r for r in resultados if not r.get("ok")]

    # Gera M3U com URLs do proxy
    print("\n📝 Gerando playlist_proxy.m3u...")
    gerar_m3u_proxy(ok, grupos)

    # Atualiza health.json
    atualizar_health(len(ok), com_failover, len(falhas))

    # Relatório final
    print(f"\n{'─'*42}")
    print(f"  Registrados   → {len(ok):>5}")
    print(f"  Com failover  → {com_failover:>5}")
    print(f"  Falhas        → {len(falhas):>5}")
    print(f"{'─'*42}")

    if falhas:
        print("\n⚠️  Streams com falha:")
        for r in falhas[:10]:
            print(f"   {r.get('titulo','?')} → {r.get('erro','?')}")
        if len(falhas) > 10:
            print(f"   ... e mais {len(falhas) - 10}")

    print(f"\n✅ Proxy configurado — {PROXY_URL}/streams\n")
