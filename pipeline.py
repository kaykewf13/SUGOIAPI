"""
SUGOIAPI Pipeline v3.6
- Integração Put.io: importa transfers concluídos como entradas do acervo,
  classificadas pelo mesmo fluxo do pipeline (categorias.py).
- categorias.py separado — importa CATEGORIAS_ANIME, GT_GENERICOS, detectar_categoria_anime
- Validação separada: canais live validados, VOD sem validação
- Fontes consolidadas por tipo (SOURCES_LIVE / SOURCES_VOD)
- Parse completo: SxxExx, EP01, 2nd Season, Temporada N
- Grupos de canais por tipo + filmes por gênero
- CATEGORIAS_ANIME v2.0: 1079 keywords em 23 categorias
- Detecção com word-boundary (sem falsos positivos por substring)
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

EPG_URL = "http://drewlive24.duckdns.org:8081/merged_epg.xml.gz"

# Caminho do state Put.io (na raiz do repo, fora de output/)
PUTIO_STATE_PATH = SCRIPT_DIR / "putio_state.json"

# ─────────────────────────────────────────────────────────────────
# FONTES — separadas por tipo de conteúdo esperado
# ─────────────────────────────────────────────────────────────────

# Fontes de CANAIS AO VIVO — serão validados
SOURCES_LIVE = [
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/PlutoTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/TubiTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/JapanTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/DrewLiveVOD.m3u8",
    "https://m3u.ibert.me/jp.m3u",
]
SOURCE_CANAIS_BR = \
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"

# Fontes de SÉRIES/FILMES VOD — NÃO validados (link estável no CDN)
SOURCES_VOD = [
    # group-title = nome do anime, links mp4 via cdn.animeiat.tv
    "https://raw.githubusercontent.com/alzamer2/iptv/main/Anime.m3u",
    # animes PT-BR com episódios
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/JapanTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/DrewLiveVOD.m3u8",
    "https://m3u.ibert.me/jp.m3u",
]

# ─────────────────────────────────────────────────────────────────
# DETECÇÃO DE TIPO POR URL
# ─────────────────────────────────────────────────────────────────

def detectar_tipo_por_url(url: str) -> str:
    u = url.lower()
    if "/live/"   in u: return "live"
    if "/series/" in u: return "series"
    if "/movie/"  in u: return "movie"
    if "/vod/"    in u: return "movie"
    if u.endswith(".ts"):   return "live"
    if u.endswith(".mp4"):  return "vod"
    if u.endswith(".m3u8"): return "live"
    return "unknown"


def is_vod(url: str) -> bool:
    t = detectar_tipo_por_url(url)
    return t in ("vod", "movie", "series")

# ─────────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO DE CANAIS TV POR TIPO
# ─────────────────────────────────────────────────────────────────

CANAL_NOTICIAS = [
    'NEWS','NOTICIAS','NOTÍCIAS','JORNAL',
    'CNN','BBC NEWS','SKY NEWS','FOX NEWS','GLOBO NEWS',
    'BAND NEWS','JOVEM PAN NEWS','RECORD NEWS',
    'AL JAZEERA','EURONEWS','BLOOMBERG','REUTERS',
    'NBC NEWS','CBS NEWS','ABC NEWS','DW NEWS','FRANCE 24',
    'NHK WORLD','CGTN','RT NEWS','TRT WORLD',
]
CANAL_ESPORTES = [
    'ESPN','FOX SPORTS','SPORTV','PREMIERE','DAZN',
    'TNT SPORTS','BT SPORT','EUROSPORT','NFL','NBA','MLB',
    'NHL','UFC','COMBATE','ELEVEN SPORTS','GOLAZO',
    'FUTEBOL','FOOTBALL','SOCCER','SPORT TV','F1 CHANNEL',
]
CANAL_FILMES = [
    'MOVIE','MOVIES','CINEMA','FILM','FILMES','CINE ',
    'MOVIESPHERE','LIONSGATE','PLUTO TV ACTION MOVIES',
    'PLUTO TV HORROR','PLUTO TV COMEDY MOVIES',
    'PLUTO TV WESTERNS','PLUTO TV THRILLERS',
    'CLASSIC MOVIES','HALLMARK MOVIES','LIFETIME',
]
CANAL_INFANTIL = [
    'KIDS','INFANTIL','CARTOON','NICK JR','NICKELODEON',
    'DISNEY','BOOMERANG','BABY','MINI','ARTHUR','DORA',
    'PEPPA','LEGO','BARNEY','TELETUBBIES','RYAN',
    'STRAWBERRY','LITTLE ANGEL','FOREVER KIDS',
]
CANAL_ADULTOS = [
    'ADULTO','ADULT','XXX','EROTIC','HOCHU',
    'BABES TV','EROX','EXTASY','FAP TV',
    'BLUE HUSTLER','DORCEL','PENTHOUSE','PLAYBOY',
]
CANAL_MUSICA = [
    'MTV','VEVO','MUSIC','MUSICA','MÚSICA',
    'VH1','BET','XITE','CMT','TRACE','RADIO',
]
CANAL_DOCUMENTARIO = [
    'DISCOVERY','NATIONAL GEOGRAPHIC','NAT GEO','HISTORY',
    'SMITHSONIAN','PBS NATURE','DOCUMENTAR','DOC ',
    'ANIMAL PLANET','SCIENCE','NATURE',
]


def classificar_canal_tv(nome: str, group_title: str) -> str:
    texto = (nome + " " + group_title).upper()
    if any(k in texto for k in CANAL_ADULTOS):       return "Adultos"
    if any(k in texto for k in CANAL_NOTICIAS):      return "Noticias"
    if any(k in texto for k in CANAL_ESPORTES):      return "Esportes"
    if any(k in texto for k in CANAL_FILMES):        return "Filmes"
    if any(k in texto for k in CANAL_INFANTIL):      return "Infantil"
    if any(k in texto for k in CANAL_MUSICA):        return "Musica"
    if any(k in texto for k in CANAL_DOCUMENTARIO):  return "Documentario"
    return "Variados"

# ─────────────────────────────────────────────────────────────────
# CATEGORIZAÇÃO DE FILMES POR GÊNERO
# ─────────────────────────────────────────────────────────────────

FILME_ADULTO     = ['HENTAI','[XXX]','XXX','UNCENSORED','OVERFLOW','OPPAI']
FILME_ACAO       = ['ACTION','ACAO','AÇÃO','BATTLE','PLUTO TV ACTION','FLICKS OF FURY']
FILME_TERROR     = ['HORROR','TERROR','HAUNTED','GHOST','PARANORMAL','PLUTO TV HORROR']
FILME_COMEDIA    = ['COMEDY','COMEDIA','COMÉDIA','PLUTO TV COMEDY MOVIES']
FILME_ROMANCE    = ['ROMANCE','ROMANTIC','AMOR','HALLMARK','ROMANCE 365']
FILME_FICCAO     = ['SCI-FI','SCIFI','SCIENCE FICTION','SPACE','PLUTO TV SCI-FI']
FILME_SUSPENSE   = ['THRILLER','MYSTERY','CRIME','SUSPENSE','PLUTO TV THRILLERS']
FILME_ANIMACAO   = ['ANIMATION','ANIMACAO','ANIME MOVIE','GHIBLI','MIYAZAKI']
FILME_DOC        = ['DOCUMENTARY','DOCUMENTARIO','DOCUMENTÁRIO']
FILME_WESTERN    = ['WESTERN','COWBOY','PLUTO TV WESTERNS']


def classificar_filme(nome: str, group_title: str) -> str:
    texto = (nome + " " + group_title).upper()
    if any(k in texto for k in FILME_ADULTO):   return "Adulto"
    if any(k in texto for k in FILME_ANIMACAO): return "Animacao"
    if any(k in texto for k in FILME_TERROR):   return "Terror"
    if any(k in texto for k in FILME_ACAO):     return "Acao"
    if any(k in texto for k in FILME_FICCAO):   return "Sci-Fi"
    if any(k in texto for k in FILME_SUSPENSE): return "Suspense"
    if any(k in texto for k in FILME_ROMANCE):  return "Romance"
    if any(k in texto for k in FILME_COMEDIA):  return "Comedia"
    if any(k in texto for k in FILME_WESTERN):  return "Western"
    if any(k in texto for k in FILME_DOC):      return "Documentario"
    return "Geral"

# ─────────────────────────────────────────────────────────────────
# CATEGORIAS DE ANIME — importado de categorias.py
# ─────────────────────────────────────────────────────────────────

from categorias import CATEGORIAS_ANIME, GT_GENERICOS, detectar_categoria_anime

# Integração Put.io — leitura do state (sem precisar de PUTIO_TOKEN aqui)
from putio_integration import PutioState


def classificar_item(nome: str, url: str, group_title: str) -> dict:
    tipo = detectar_tipo_por_url(url)
    gt   = group_title.strip()

    sub = gt
    for prefix in ["Series |","Séries |","Canais |","Filmes |","Movies |","VOD |"]:
        if sub.lower().startswith(prefix.lower()):
            sub = sub[len(prefix):].strip()
            break

    if sub.lower() in GT_GENERICOS:
        sub = detectar_categoria_anime(nome)

    if tipo == "live":
        return {"grupo": "Canais",  "categoria": classificar_canal_tv(nome, gt), "tipo": "live"}
    if tipo in ("vod","movie"):
        return {"grupo": "Filmes",  "categoria": classificar_filme(nome, gt),    "tipo": "movie"}
    if tipo == "series":
        return {"grupo": "Series",  "categoria": sub or "Geral",                 "tipo": "series"}

    # Fallback por group-title
    gt_up = gt.upper()
    if any(k in gt_up for k in ["CANAL","LIVE","TV ","CHANNEL","AO VIVO"]):
        return {"grupo": "Canais", "categoria": classificar_canal_tv(nome, gt), "tipo": "live"}
    if any(k in gt_up for k in ["MOVIE","FILME","FILM","CINEMA","HENTAI","XXX"]):
        return {"grupo": "Filmes", "categoria": classificar_filme(nome, gt),    "tipo": "movie"}

    return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}

# ─────────────────────────────────────────────────────────────────
# PARSE DE SÉRIE
# ─────────────────────────────────────────────────────────────────

def extrair_temporada_do_titulo(titulo: str) -> tuple:
    m = re.search(r'\s+(\d+)(?:st|nd|rd|th)\s+season', titulo, re.IGNORECASE)
    if m:
        return titulo[:m.start()].strip(), f"Temporada {int(m.group(1)):02d}"
    m2 = re.search(r'\s+(?:season|temporada)\s+(\d+)', titulo, re.IGNORECASE)
    if m2:
        return titulo[:m2.start()].strip(), f"Temporada {int(m2.group(1)):02d}"
    return titulo, "Temporada 01"


def parse_serie(nome: str, group_title: str = "") -> dict:
    nome_clean = re.sub(
        r'\s*[\(\[]?\s*(dublado|legendado|dub|leg|pt-br|pt-pt)\s*[\)\]]?\s*$',
        '', nome, flags=re.IGNORECASE
    ).strip()

    # 1. SxxExx
    m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', nome_clean)
    if m:
        titulo    = nome_clean[:m.start()].strip(" -_|")
        temporada = f"Temporada {int(m.group(1)):02d}"
        episodio  = f"E{int(m.group(2)):02d}"
        titulo, _ = extrair_temporada_do_titulo(titulo)
        return {"titulo": titulo or nome_clean, "temporada": temporada,
                "episodio": episodio, "ep_label": f"{titulo or nome_clean} {episodio}"}

    # 2. "Anime - EP01"
    m_ep = re.search(r'\s*-?\s*EP\.?\s*(\d+)', nome_clean, re.IGNORECASE)
    if m_ep:
        titulo   = nome_clean[:m_ep.start()].strip(" -_|")
        ep_n     = int(m_ep.group(1))
        episodio = f"E{ep_n:02d}"
        titulo_base, temporada = extrair_temporada_do_titulo(titulo or nome_clean)
        if titulo_base != (titulo or nome_clean):
            titulo = titulo_base
        if temporada == "Temporada 01" and group_title:
            _, t_gt = extrair_temporada_do_titulo(group_title)
            if t_gt != "Temporada 01":
                temporada = t_gt
                titulo, _ = extrair_temporada_do_titulo(titulo)
        return {"titulo": titulo or nome_clean, "temporada": temporada,
                "episodio": episodio, "ep_label": f"{titulo or nome_clean} {episodio}"}

    # 3. Extenso: "Temporada X Episodio Y"
    m2 = re.search(r'(?:Temporada|Season|T\.?)\s*(\d+)', nome_clean, re.IGNORECASE)
    m3 = re.search(r'(?:Epis[oó]dio|Episode|Ep\.?|E\.?)\s*(\d+)', nome_clean, re.IGNORECASE)
    if m2 or m3:
        temp_n   = int(m2.group(1)) if m2 else 1
        ep_n     = int(m3.group(1)) if m3 else 1
        corte    = min(m2.start() if m2 else len(nome_clean),
                       m3.start() if m3 else len(nome_clean))
        titulo   = nome_clean[:corte].strip(" -_|") or nome_clean
        return {"titulo": titulo, "temporada": f"Temporada {temp_n:02d}",
                "episodio": f"E{ep_n:02d}", "ep_label": f"{titulo} E{ep_n:02d}"}

    # 4. Fallback — usa group_title como referência de título/temporada
    titulo_final    = nome_clean
    temporada_final = "Temporada 01"
    if group_title and group_title.lower() not in GT_GENERICOS:
        titulo_base, temporada_base = extrair_temporada_do_titulo(group_title)
        titulo_final    = titulo_base
        temporada_final = temporada_base
    return {"titulo": titulo_final, "temporada": temporada_final,
            "episodio": "E01", "ep_label": nome_clean}

# ─────────────────────────────────────────────────────────────────
# FILTRO CANAIS BRASIL
# ─────────────────────────────────────────────────────────────────

BR_NOMES = ['GLOBO','SBT','BAND','RECORD','REDETV','TV BRASIL','TV CULTURA',
            'GLOBO NEWS','BAND NEWS','CNN BRASIL','JOVEM PAN','TV ESCOLA',
            'CANAL GOV','SENADO','CÂMARA','FUTURA','MULTISHOW','SPORTV',
            'PREMIERE','REDE BRASIL','TV APARECIDA','REDE VIDA']


def is_canal_brasileiro(nome: str, url: str, extinf: str) -> bool:
    n = nome.upper()
    e = extinf.upper()
    country = re.search(r'TVG-COUNTRY="([^"]*)"', e)
    if country and any(br in country.group(1) for br in ['BR','BRA','BRAZIL','BRASIL']):
        return True
    if any(br in n for br in BR_NOMES):
        return True
    if any(d in url.lower() for d in ['.com.br','.gov.br','.org.br']):
        return True
    return False

# ─────────────────────────────────────────────────────────────────
# VALIDAÇÃO DE NOME
# ─────────────────────────────────────────────────────────────────

_NOME_INVALIDO   = re.compile(r'^[\w\-]+(\.m3u8?|\.ts|\.mp4|\.mkv)?$', re.IGNORECASE)
_RESIDUO_ANTERIOR = re.compile(r'(episodio\s*\d+|temporada\s*\d+|\bE\d{2}\b)', re.IGNORECASE)


def nome_valido(nome: str) -> bool:
    n = nome.strip()
    if len(n) < 3:              return False
    if _NOME_INVALIDO.match(n): return False
    if _RESIDUO_ANTERIOR.search(n): return False
    return True

# ─────────────────────────────────────────────────────────────────
# ETAPA 1 — Varredura do repositório (exclui output/)
# ─────────────────────────────────────────────────────────────────

def listar_arquivos_repo() -> list:
    url = (f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
           f"/git/trees/{BRANCH}?recursive=1")
    res = requests.get(url, timeout=15)
    tree = res.json().get("tree", [])
    return [
        f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/{i['path']}"
        for i in tree
        if i["type"] == "blob"
        and not i["path"].startswith("output/")
        and not i["path"].endswith(".m3u")
        and not i["path"].endswith(".m3u8")
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

            nome_m = re.search(r'tvg-name="([^"]*)"', line)
            nome   = nome_m.group(1).strip() if nome_m else ""
            if not nome:
                nome_m2 = re.search(r',([^,]+)$', line)
                nome = nome_m2.group(1).strip() if nome_m2 else ""

            if not nome_valido(nome):
                continue

            gt_m = re.search(r'group-title="([^"]*)"', line)
            gt   = gt_m.group(1).strip() if gt_m else ""

            logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            logo   = logo_m.group(1).strip() if logo_m else ""

            if filtro_br and not is_canal_brasileiro(nome, url_linha, line):
                continue

            encontrados.append({"Nome": nome, "URL": url_linha,
                                 "group_title": gt, "logo": logo})
        return encontrados

    except Exception as e:
        print(f"  ⚠️  {raw_url[:70]}: {e}")
        return []

# ─────────────────────────────────────────────────────────────────
# ETAPA 2.5 — Importação Put.io (transfers concluídos via state)
# ─────────────────────────────────────────────────────────────────

def carregar_itens_putio(state_path: Path = PUTIO_STATE_PATH) -> list:
    """
    Lê putio_state.json e retorna entradas no formato do acervo
    ({Nome, URL, group_title, logo}). Idempotente — não toca a API
    do Put.io, apenas consome o state já populado por harvest_putio.py.
    Se o state não existir ainda (primeira execução), retorna lista vazia.
    """
    if not Path(state_path).exists():
        return []

    state = PutioState(state_path)
    itens = []
    for _info_hash, rec in state.all_done():
        url = rec.get("stream_url")
        if not url:
            continue
        itens.append({
            "Nome":        rec.get("title", "Unknown"),
            "URL":         url,
            "group_title": rec.get("category") or "Series | Anime",
            "logo":        "",
        })
    return itens

# ─────────────────────────────────────────────────────────────────
# ETAPA 3 — Validação APENAS para canais ao vivo
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


def separar_e_validar(acervo: list) -> list:
    """
    Separa live de VOD.
    Live → valida link antes de incluir.
    VOD  → inclui direto (link estável no CDN).
    """
    live, vod = [], []
    for item in acervo:
        if is_vod(item["URL"]):
            vod.append(item)
        else:
            live.append(item)

    print(f"\n⚡ Validando {len(live)} canais ao vivo...")
    live_validos = []
    with ThreadPoolExecutor(max_workers=40) as ex:
        futuros = {ex.submit(link_esta_vivo, item["URL"]): item for item in live}
        for f in as_completed(futuros):
            if f.result():
                live_validos.append(futuros[f])

    print(f"   ✅ {len(live_validos)} canais live ativos  ({len(live) - len(live_validos)} offline descartados)")
    print(f"   📼 {len(vod)} entradas VOD incluídas direto (séries/filmes — sem validação)")

    return live_validos + vod

# ─────────────────────────────────────────────────────────────────
# ETAPA 4 — Geração da M3U
# ─────────────────────────────────────────────────────────────────

ORDEM_CANAIS = ["Noticias","Esportes","Filmes","Documentario","Musica","Infantil","Variados","Adultos"]
ORDEM_FILMES = ["Acao","Terror","Suspense","Sci-Fi","Romance","Comedia","Western","Animacao","Documentario","Adulto","Geral"]


def gerar_m3u(validos: list):
    vistos, unicos = set(), []
    for item in validos:
        if item["URL"] not in vistos:
            vistos.add(item["URL"])
            unicos.append(item)

    for item in unicos:
        item.update(classificar_item(item["Nome"], item["URL"], item.get("group_title","")))

    canais = sorted([i for i in unicos if i["grupo"] == "Canais"],
                    key=lambda x: (x["categoria"], x["Nome"].upper()))
    filmes = sorted([i for i in unicos if i["grupo"] == "Filmes"],
                    key=lambda x: (x["categoria"], x["Nome"].upper()))

    series_raw = [i for i in unicos if i["grupo"] == "Series"]
    for s in series_raw:
        s.update(parse_serie(s["Nome"], s.get("group_title","")))
    series = sorted(series_raw, key=lambda x: (
        x["categoria"].upper(), x["titulo"].upper(), x["temporada"], x["episodio"]))

    m3u_path = OUTPUT_DIR / "playlist_validada.m3u"

    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}" m3u-type="m3u_plus"\n\n')

        # ── CANAIS ────────────────────────────────────────────────
        f.write(f"### ══════════ CANAIS ({len(canais)}) ══════════\n\n")
        canais_por_tipo = {}
        for item in canais:
            canais_por_tipo.setdefault(item["categoria"], []).append(item)

        for tipo in ORDEM_CANAIS:
            grupo = canais_por_tipo.pop(tipo, [])
            if not grupo: continue
            f.write(f"\n## ── {tipo} ({len(grupo)}) ──\n\n")
            for item in grupo:
                f.write(f'#EXTINF:-1 tvg-name="{item["Nome"]}" tvg-logo="{item.get("logo","")}" '
                        f'tvg-type="live" group-title="Canais | {tipo}", {item["Nome"]}\n'
                        f'{item["URL"]}\n\n')
        for tipo, grupo in canais_por_tipo.items():
            f.write(f"\n## ── {tipo} ({len(grupo)}) ──\n\n")
            for item in grupo:
                f.write(f'#EXTINF:-1 tvg-name="{item["Nome"]}" tvg-logo="{item.get("logo","")}" '
                        f'tvg-type="live" group-title="Canais | {tipo}", {item["Nome"]}\n'
                        f'{item["URL"]}\n\n')

        # ── SÉRIES ────────────────────────────────────────────────
        f.write(f"\n### ══════════ SÉRIES ({len(series)}) ══════════\n\n")
        cat_atual = titulo_atual = temp_atual = None
        for item in series:
            cat, titulo = item["categoria"], item["titulo"]
            temporada, episodio = item["temporada"], item["episodio"]
            ep_label = item["ep_label"]
            if cat != cat_atual:
                cat_atual = cat; titulo_atual = temp_atual = None
                f.write(f"\n## ── {cat} ──\n\n")
            if titulo != titulo_atual: titulo_atual = titulo; temp_atual = None
            if temporada != temp_atual: temp_atual = temporada
            group = f"Series | {cat} | {titulo} | {temporada}"
            f.write(f'#EXTINF:-1 tvg-name="{ep_label}" tvg-logo="{item.get("logo","")}" '
                    f'tvg-type="series" group-title="{group}", {ep_label}\n'
                    f'{item["URL"]}\n\n')

        # ── FILMES ────────────────────────────────────────────────
        f.write(f"\n### ══════════ FILMES ({len(filmes)}) ══════════\n\n")
        filmes_por_genero = {}
        for item in filmes:
            filmes_por_genero.setdefault(item["categoria"], []).append(item)

        for genero in ORDEM_FILMES:
            grupo = filmes_por_genero.pop(genero, [])
            if not grupo: continue
            f.write(f"\n## ── {genero} ({len(grupo)}) ──\n\n")
            for item in grupo:
                f.write(f'#EXTINF:-1 tvg-name="{item["Nome"]}" tvg-logo="{item.get("logo","")}" '
                        f'tvg-type="movie" group-title="Filmes | {genero}", {item["Nome"]}\n'
                        f'{item["URL"]}\n\n')
        for genero, grupo in filmes_por_genero.items():
            f.write(f"\n## ── {genero} ({len(grupo)}) ──\n\n")
            for item in grupo:
                f.write(f'#EXTINF:-1 tvg-name="{item["Nome"]}" tvg-logo="{item.get("logo","")}" '
                        f'tvg-type="movie" group-title="Filmes | {genero}", {item["Nome"]}\n'
                        f'{item["URL"]}\n\n')

    # Resumo
    print(f"\n{'─'*48}")
    print(f"  CANAIS  → {len(canais):>5}")
    for tipo in ORDEM_CANAIS:
        n = sum(1 for c in canais if c["categoria"] == tipo)
        if n: print(f"    {tipo:<15} {n:>4}")
    print(f"  SÉRIES  → {len(series):>5}")
    print(f"  FILMES  → {len(filmes):>5}")
    for genero in ORDEM_FILMES:
        n = sum(1 for fi in filmes if fi["categoria"] == genero)
        if n: print(f"    {genero:<15} {n:>4}")
    print(f"  TOTAL   → {len(unicos):>5} entradas")
    print(f"{'─'*48}\n")
    print(f"  M3U → {m3u_path}\n")

# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    acervo = []

    # 1. Repositório SUGOIAPI (exclui output/)
    print("📂 Varrendo repositório SUGOIAPI...")
    arquivos = listar_arquivos_repo()
    print(f"   {len(arquivos)} arquivos encontrados")
    with ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(extrair_links, arquivos):
            acervo.extend(r)

    # 2. Fontes VOD — séries e filmes (sem validação posterior)
    print(f"\n🎌 Fontes VOD ({len(SOURCES_VOD)} fontes) — séries e filmes...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        for r in ex.map(extrair_links, SOURCES_VOD):
            acervo.extend(r)
    print(f"   {sum(1 for i in acervo if is_vod(i['URL']))} entradas VOD extraídas")

    # 3. Fontes ao vivo
    print(f"\n📡 Fontes ao vivo ({len(SOURCES_LIVE)} fontes)...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        for r in ex.map(extrair_links, SOURCES_LIVE):
            acervo.extend(r)

    # 4. Canais Brasil
    print("\n📺 Canais brasileiros (Free-TV)...")
    canais_br = extrair_links(SOURCE_CANAIS_BR, filtro_br=True)
    acervo.extend(canais_br)
    print(f"   {len(canais_br)} canais BR")

    # 5. Put.io — transfers concluídos via RSS → cloud
    print("\n☁️  Importando entradas Put.io concluídas...")
    putio_items = carregar_itens_putio()
    acervo.extend(putio_items)
    print(f"   {len(putio_items)} entradas Put.io importadas")

    print(f"\n📦 Total bruto: {len(acervo)} entradas")

    # 6. Validação separada por tipo
    validos = separar_e_validar(acervo)

    # 7. Geração
    print("\n📝 Gerando playlist classificada...")
    gerar_m3u(validos)