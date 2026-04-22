"""
SUGOIAPI Pipeline v3
Classificação baseada na estrutura real da fonte:
- URL path: /live/ → Canal, /series/ → Série, /movie/ → Filme
- group-title existente preservado como subcategoria
- tvg-name com SxxExx → parse de título/temporada/episódio
"""

import re, requests, shutil, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import sentry_sdk
    sentry_sdk.init(dsn=os.getenv("SENTRY_DSN", ""), traces_sample_rate=0.2)
except ImportError:
    pass

import cloudscraper

# ── Diretórios ────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.absolute()
OUTPUT_DIR = SCRIPT_DIR / "output"
if OUTPUT_DIR.exists(): shutil.rmtree(OUTPUT_DIR)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPO_OWNER = "kaykewf13"
REPO_NAME  = "SUGOIAPI"
BRANCH     = "main"

SOURCES_ANIME = [
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/DrewLiveVOD.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/JapanTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/PlutoTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/TubiTV.m3u8",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u",
    "https://m3u.ibert.me/jp.m3u",
]

SOURCE_CANAIS_BR = \
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"

EPG_URL = "http://drewlive24.duckdns.org:8081/merged_epg.xml.gz"


# ─────────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO — baseada em URL path e group-title existente
# ─────────────────────────────────────────────────────────────────

def detectar_tipo_por_url(url: str) -> str:
    """Detecta tipo pelo path da URL."""
    u = url.lower()
    if "/live/"    in u: return "live"
    if "/series/"  in u: return "series"
    if "/movie/"   in u: return "movie"
    if "/vod/"     in u: return "movie"
    if ".ts"       == u[-3:]: return "live"
    if ".mp4"      == u[-4:]: return "movie"
    if ".m3u8"     == u[-5:]: return "live"
    return "unknown"


def classificar_item(nome: str, url: str, group_title: str) -> dict:
    """
    Classifica usando 3 camadas:
    1. URL path (mais confiável)
    2. group-title existente da fonte
    3. Fallback por keyword no nome
    """
    tipo = detectar_tipo_por_url(url)
    gt   = group_title.strip()

    # Normaliza group-title da fonte como subcategoria
    # Remove prefixos conhecidos: "Series | Netflix" → "Netflix"
    sub = gt
    for prefix in ["Series |", "Séries |", "Canais |", "Filmes |",
                   "Movies |", "VOD |"]:
        if sub.lower().startswith(prefix.lower()):
            sub = sub[len(prefix):].strip()
            break

    if tipo == "live":
        return {"grupo": "Canais", "categoria": sub or "Geral", "tipo": "live"}

    if tipo in ("movie", "vod"):
        return {"grupo": "Filmes", "categoria": sub or "Geral", "tipo": "movie"}

    if tipo == "series":
        return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}

    # Fallback: deduz pelo group-title
    gt_up = gt.upper()
    if any(k in gt_up for k in ["CANAL", "LIVE", "TV ", "CHANNEL"]):
        return {"grupo": "Canais", "categoria": sub or "Geral", "tipo": "live"}
    if any(k in gt_up for k in ["MOVIE", "FILME", "FILM", "VOD", "CINEMA"]):
        return {"grupo": "Filmes", "categoria": sub or "Geral", "tipo": "movie"}
    if any(k in gt_up for k in ["SERIE", "SERIES", "SEASON", "EPISODE"]):
        return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}

    # Último fallback: keyword no nome
    nome_up = nome.upper()
    if re.search(r'S\d{2}E\d{2,3}', nome):
        return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}

    return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}


# ─────────────────────────────────────────────────────────────────
# PARSE DE SÉRIE — extrai título, temporada, episódio do tvg-name
# ─────────────────────────────────────────────────────────────────

def parse_serie(nome: str) -> dict:
    """
    Suporta formatos reais:
      'Naruto S01E01'
      '100 Humanos S01E08'
      'Anime Temporada 2 Episodio 5'
    """
    # Formato padrão SxxExx
    m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', nome)
    if m:
        titulo    = nome[:m.start()].strip(" -_|")
        temporada = f"Temporada {int(m.group(1)):02d}"
        episodio  = f"E{int(m.group(2)):02d}"
        return {
            "titulo"   : titulo or nome,
            "temporada": temporada,
            "episodio" : episodio,
            "ep_label" : f"{titulo} {episodio}",
        }

    # Formato por extenso
    m2 = re.search(r'(?:Temporada|Season|T\.?)\s*(\d+)', nome, re.IGNORECASE)
    m3 = re.search(r'(?:Epis[oó]dio|Episode|Ep\.?|E\.?)\s*(\d+)', nome, re.IGNORECASE)
    if m2 or m3:
        temp_n    = int(m2.group(1)) if m2 else 1
        ep_n      = int(m3.group(1)) if m3 else 1
        temporada = f"Temporada {temp_n:02d}"
        episodio  = f"E{ep_n:02d}"
        corte     = min(
            m2.start() if m2 else len(nome),
            m3.start() if m3 else len(nome)
        )
        titulo = nome[:corte].strip(" -_|") or nome
        return {
            "titulo"   : titulo,
            "temporada": temporada,
            "episodio" : episodio,
            "ep_label" : f"{titulo} {episodio}",
        }

    # Sem indicador → episódio único
    return {
        "titulo"   : nome,
        "temporada": "Temporada 01",
        "episodio" : "E01",
        "ep_label" : nome,
    }


# ─────────────────────────────────────────────────────────────────
# FILTRO CANAIS BRASIL
# ─────────────────────────────────────────────────────────────────

BR_COUNTRYTAGS = ['BR', 'BRA', 'BRAZIL', 'BRASIL']
BR_NOMES = [
    'GLOBO', 'SBT', 'BAND', 'RECORD', 'REDETV', 'TV BRASIL', 'TV CULTURA',
    'GLOBO NEWS', 'BAND NEWS', 'CNN BRASIL', 'JOVEM PAN', 'TV ESCOLA',
    'CANAL GOV', 'SENADO', 'CÂMARA', 'FUTURA', 'MULTISHOW', 'SPORTV',
    'PREMIERE', 'REDE BRASIL', 'TV APARECIDA', 'REDE VIDA', 'ISTV',
]


def is_canal_brasileiro(nome: str, url: str, extinf: str) -> bool:
    n = nome.upper()
    e = extinf.upper()
    country = re.search(r'TVG-COUNTRY="([^"]*)"', e)
    if country and any(br in country.group(1) for br in BR_COUNTRYTAGS):
        return True
    tvgid = re.search(r'tvg-id="([^"]*)"', extinf, re.IGNORECASE)
    if tvgid and any(br in tvgid.group(1).lower() for br in
                     ['globo', 'sbt', 'band', 'record', 'redetv',
                      'tvcultura', 'tvbrasil', 'camara', 'senado']):
        return True
    if any(br in n for br in BR_NOMES):
        return True
    if any(d in url.lower() for d in ['.com.br', '.gov.br', '.org.br',
                                       'logicahost.com.br',
                                       'streamingdevideo.com.br']):
        return True
    return False


# ─────────────────────────────────────────────────────────────────
# ETAPA 1 — Varredura do repositório
# ─────────────────────────────────────────────────────────────────

def listar_arquivos_repo() -> list:
    url = (f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
           f"/git/trees/{BRANCH}?recursive=1")
    res = requests.get(url, timeout=15)
    tree = res.json().get("tree", [])
    return [
        f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}"
        f"/{BRANCH}/{i['path']}"
        for i in tree if i["type"] == "blob"
    ]


# ─────────────────────────────────────────────────────────────────
# ETAPA 2 — Extração de links
# ─────────────────────────────────────────────────────────────────

def extrair_links(raw_url: str, filtro_br: bool = False) -> list:
    try:
        scraper = cloudscraper.create_scraper()
        res = scraper.get(raw_url, timeout=15)
        if res.status_code != 200:
            return []

        encontrados = []
        lines = res.text.splitlines()

        for i, line in enumerate(lines):
            if not line.startswith('#EXTINF'):
                continue

            url_linha = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if not url_linha.startswith('http'):
                continue

            # Extrai tvg-name
            nome_m = re.search(r'tvg-name="([^"]*)"', line)
            nome   = nome_m.group(1).strip() if nome_m else ""

            # Fallback: pega o texto após a última vírgula na linha EXTINF
            if not nome:
                nome_m2 = re.search(r',([^,]+)$', line)
                nome = nome_m2.group(1).strip() if nome_m2 else ""

            if not nome or len(nome) < 2:
                continue

            # Descarta nomes que são apenas filename
            if re.match(r'^[\w\-\.]+\.(m3u8?|ts|mp4|mkv)$', nome.lower()):
                continue

            # Extrai group-title
            gt_m  = re.search(r'group-title="([^"]*)"', line)
            gt    = gt_m.group(1).strip() if gt_m else ""

            # Extrai tvg-logo
            logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            logo   = logo_m.group(1).strip() if logo_m else ""

            if filtro_br and not is_canal_brasileiro(nome, url_linha, line):
                continue

            encontrados.append({
                "Nome"       : nome,
                "URL"        : url_linha,
                "group_title": gt,
                "logo"       : logo,
                "extinf"     : line,
            })

        return encontrados

    except Exception as e:
        print(f"  ⚠️  {raw_url[:70]}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────
# ETAPA 3 — Validação real
# ─────────────────────────────────────────────────────────────────

def link_esta_vivo(url: str, timeout: int = 8) -> bool:
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True)
        if r.status_code == 405:
            r = requests.get(url, timeout=timeout, stream=True)
            r.close()
        return r.status_code < 400
    except:
        return False


def validar_em_paralelo(acervo: list, workers: int = 40) -> list:
    validos = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futuros = {ex.submit(link_esta_vivo, item["URL"]): item
                   for item in acervo}
        for f in as_completed(futuros):
            if f.result():
                validos.append(futuros[f])
    return validos


# ─────────────────────────────────────────────────────────────────
# ETAPA 4 — Geração da M3U
# ─────────────────────────────────────────────────────────────────

def gerar_m3u(validos: list):
    # Deduplica por URL
    vistos, unicos = set(), []
    for item in validos:
        if item["URL"] not in vistos:
            vistos.add(item["URL"])
            unicos.append(item)

    # Classifica cada item
    for item in unicos:
        item.update(classificar_item(
            item["Nome"], item["URL"], item.get("group_title", "")
        ))

    # Separa grupos
    canais = sorted(
        [i for i in unicos if i["grupo"] == "Canais"],
        key=lambda x: (x["categoria"], x["Nome"].upper())
    )

    filmes = sorted(
        [i for i in unicos if i["grupo"] == "Filmes"],
        key=lambda x: (x["categoria"], x["Nome"].upper())
    )

    # Séries: parse + ordenação hierárquica
    series_raw = [i for i in unicos if i["grupo"] == "Series"]
    for s in series_raw:
        s.update(parse_serie(s["Nome"]))
    series = sorted(
        series_raw,
        key=lambda x: (
            x["categoria"].upper(),
            x["titulo"].upper(),
            x["temporada"],
            x["episodio"],
        )
    )

    m3u_path = OUTPUT_DIR / "playlist_validada.m3u"

    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}" m3u-type="m3u_plus"\n\n')

        # ── CANAIS ────────────────────────────────────────────────
        # Estrutura: group-title="Canais | <categoria>"
        f.write(f"### ══════════ CANAIS ({len(canais)}) ══════════\n\n")
        for item in canais:
            nome = item["Nome"]
            cat  = item["categoria"]
            logo = item.get("logo", "")
            f.write(
                f'#EXTINF:-1 tvg-name="{nome}" tvg-logo="{logo}" '
                f'tvg-type="live" '
                f'group-title="Canais | {cat}", {nome}\n'
            )
            f.write(f'{item["URL"]}\n\n')

        # ── SÉRIES ────────────────────────────────────────────────
        # Estrutura: group-title="Series | <categoria> | <título> | <temporada>"
        # Label da entrada: título + episódio
        f.write(f"\n### ══════════ SÉRIES ({len(series)}) ══════════\n\n")

        cat_atual    = None
        titulo_atual = None
        temp_atual   = None

        for item in series:
            cat      = item["categoria"]
            titulo   = item["titulo"]
            temporada= item["temporada"]
            episodio = item["episodio"]
            logo     = item.get("logo", "")
            ep_label = f"{titulo} {episodio}"

            # Separadores visuais por categoria → título → temporada
            if cat != cat_atual:
                cat_atual    = cat
                titulo_atual = None
                temp_atual   = None
                f.write(f"\n## ── {cat} ──\n\n")

            if titulo != titulo_atual:
                titulo_atual = titulo
                temp_atual   = None

            if temporada != temp_atual:
                temp_atual = temporada

            # group-title hierárquico para o player
            group = f"Series | {cat} | {titulo} | {temporada}"

            f.write(
                f'#EXTINF:-1 tvg-name="{ep_label}" tvg-logo="{logo}" '
                f'tvg-type="series" '
                f'group-title="{group}", {ep_label}\n'
            )
            f.write(f'{item["URL"]}\n\n')

        # ── FILMES ────────────────────────────────────────────────
        # Estrutura: group-title="Filmes | <categoria>"
        f.write(f"\n### ══════════ FILMES ({len(filmes)}) ══════════\n\n")
        cat_atual = None
        for item in filmes:
            cat  = item["categoria"]
            nome = item["Nome"]
            logo = item.get("logo", "")

            if cat != cat_atual:
                cat_atual = cat
                f.write(f"\n## ── {cat} ──\n\n")

            f.write(
                f'#EXTINF:-1 tvg-name="{nome}" tvg-logo="{logo}" '
                f'tvg-type="movie" '
                f'group-title="Filmes | {cat}", {nome}\n'
            )
            f.write(f'{item["URL"]}\n\n')

    # Resumo
    print(f"\n{'─'*42}")
    print(f"  Canais  → {len(canais):>5}")
    print(f"  Séries  → {len(series):>5}")
    print(f"  Filmes  → {len(filmes):>5}")
    print(f"  Total   → {len(unicos):>5} links reais validados")
    print(f"{'─'*42}")
    print(f"  M3U  → {m3u_path}")
    print(f"{'─'*42}\n")


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    acervo = []

    # 1. Varredura repositório SUGOIAPI
    print("📂 Varrendo repositório SUGOIAPI...")
    arquivos = listar_arquivos_repo()
    print(f"   {len(arquivos)} arquivos encontrados")
    with ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(extrair_links, arquivos):
            acervo.extend(r)
    print(f"   {len(acervo)} links extraídos do repo")

    # 2. Fontes externas de anime
    print(f"\n🎌 Fontes externas ({len(SOURCES_ANIME)} fontes)...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        for r in ex.map(extrair_links, SOURCES_ANIME):
            acervo.extend(r)
    print(f"   Total acumulado: {len(acervo)}")

    # 3. Canais Brasil
    print("\n📺 Canais brasileiros (Free-TV)...")
    canais_br = extrair_links(SOURCE_CANAIS_BR, filtro_br=True)
    acervo.extend(canais_br)
    print(f"   {len(canais_br)} canais BR encontrados")

    print(f"\n📦 Total bruto: {len(acervo)} entradas")

    # 4. Validação
    print("\n⚡ Validando links reais...")
    validos = validar_em_paralelo(acervo)
    print(f"   {len(validos)} links confirmados vivos")

    # 5. Geração
    print("\n📝 Gerando playlist classificada...")
    gerar_m3u(validos)
