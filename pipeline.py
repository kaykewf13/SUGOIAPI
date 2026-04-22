"""
SUGOIAPI Pipeline v3.1
Classificação por URL path + group-title da fonte + categoria por nome do anime
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
# CATEGORIAS DE ANIME POR NOME
# ─────────────────────────────────────────────────────────────────

CATEGORIAS_ANIME = {
    "Shounen": [
        'NARUTO','ONE PIECE','DRAGON BALL','BLEACH','FAIRY TAIL',
        'DEMON SLAYER','KIMETSU','ATTACK ON TITAN','SHINGEKI',
        'HUNTER X HUNTER','FULLMETAL','MY HERO ACADEMIA','BOKU NO HERO',
        'JUJUTSU KAISEN','BLACK CLOVER','FIRE FORCE','SOUL EATER',
        'BLUE EXORCIST','INUYASHA','HAIKYUU','KUROKO','SLAM DUNK',
        'EYESHIELD','CAPTAIN TSUBASA','BEYBLADE','YU GI OH','YU-GI-OH',
        'DIGIMON','POKEMON','ZATCH BELL','SHAMAN KING','KATEKYO','REBORN',
        'TORIKO','D.GRAY','MAR','RAVE MASTER','MEDABOTS',
    ],
    "Shoujo": [
        'SAILOR MOON','CARDCAPTOR','FRUITS BASKET','OURAN','CLANNAD',
        'KAMISAMA','SKIP BEAT','VAMPIRE KNIGHT','KAICHOU WA MAID',
        'NANA','FULL MOON','TOKYO MEW MEW','SHUGO CHARA','MAGIC KNIGHT',
        'RAYEARTH','WEDDING PEACH','ULTRA MANIAC','MERMAID MELODY',
        'SPECIAL A','LOVELY COMPLEX','BOKURA GA ITA','PARADISE KISS',
        'PEACH GIRL',
    ],
    "Seinen": [
        'BERSERK','DEATH NOTE','TOKYO GHOUL','GANTZ','VINLAND SAGA',
        'MONSTER','VAGABOND','GHOST IN THE SHELL','COWBOY BEBOP',
        'TRIGUN','HELLSING','BLACK LAGOON','MADE IN ABYSS','DOROHEDORO',
        'GOLDEN KAMUY','DUNGEON MESHI','MUSHISHI','ERGO PROXY','AKIRA',
        'PLANETES','ELFEN LIED','TEXHNOLYZE','SERIAL EXPERIMENTS LAIN',
        'HOMUNCULUS','BLAME','SANCTUARY','HOLYLAND',
    ],
    "Josei": [
        'CHIHAYAFURU','NODAME','HONEY AND CLOVER','WOTAKOI',
        'GEKKAN SHOUJO','PRINCESS JELLYFISH','ANTIQUE BAKERY','LOVELESS',
    ],
    "Isekai": [
        'SWORD ART ONLINE','SAO','RE:ZERO','REZERO','OVERLORD',
        'TENSURA','SLIME','LOG HORIZON','NO GAME NO LIFE','KONOSUBA',
        'SHIELD HERO','MUSHOKU TENSEI','DANMACHI','TATE NO YUUSHA',
        'ARIFURETA','ISEKAI','TENSEI','JOBLESS','SKELETON KNIGHT',
        'VILLAINESS','REALIST HERO','WORLD TEACHER','TRAPPED IN A DATING',
    ],
    "Mecha": [
        'GUNDAM','EVANGELION','NEON GENESIS','CODE GEASS',
        'GURREN LAGANN','TENGEN TOPPA','MACROSS','VOLTRON','RAHXEPHON',
        'EUREKA SEVEN','ALDNOAH ZERO','DARLING IN THE FRANXX','FRANXX',
        'FULL METAL PANIC','ESCAFLOWNE','MAZINGER','GETTER ROBO','PATLABOR',
    ],
    "Terror e Suspense": [
        'HIGURASHI','WHEN THEY CRY','SHIKI','ANOTHER','PARASYTE','KISEIJUU',
        'PROMISED NEVERLAND','MIRAI NIKKI','FUTURE DIARY','DEADMAN WONDERLAND',
        'HELL GIRL','JIGOKU SHOUJO','GHOST HUNT','BOOGIEPOP','JUNJI ITO',
        'BLOOD-C','UMINEKO','CORPSE PARTY',
    ],
    "Psicologico": [
        'SERIAL EXPERIMENTS','STEINS GATE','PARANOIA AGENT',
        'WELCOME TO NHK','KAKEGURUI','CLASSROOM OF THE ELITE',
        'TALENTLESS NANA','ID INVADED','MORIARTY THE PATRIOT',
    ],
    "Romance": [
        'TORADORA','ANGEL BEATS','ANOHANA','YOUR LIE IN APRIL',
        'SHIGATSU','OREGAIRU','GOLDEN TIME','NISEKOI','KAGUYA SAMA',
        'HORIMIYA','QUINTESSENTIAL','5-TOUBUN','RENT A GIRLFRIEND',
        'YOUR NAME','KIMI NO NA WA','AO HARU RIDE','SAY I LOVE YOU',
        'PLASTIC MEMORIES','TRUE TEARS','SHUFFLE','AMAGAMI',
        'ITAZURA NA KISS','WHITE ALBUM',
    ],
    "Slice of Life": [
        'BARAKAMON','SILVER SPOON','ARIA','LAID BACK CAMP','YURU CAMP',
        'NON NON BIYORI','K-ON','LUCKY STAR','AZUMANGA','NICHIJOU',
        'HIDAMARI SKETCH','YOTSUBA','ENCOURAGEMENT OF CLIMB',
        'FLYING WITCH','POCO UDON','SCHOOL RUMBLE',
    ],
    "Acao e Aventura": [
        'RUROUNI KENSHIN','SAMURAI X','FATE','STAY NIGHT','FATE ZERO',
        'FATE APOCRYPHA','JOJO','BIZARRE ADVENTURE','TOWER OF GOD',
        'NANATSU NO TAIZAI','SEVEN DEADLY SINS','RECORD OF RAGNAROK',
        'CLAYMORE','DRIFTERS','BLADE OF THE IMMORTAL',
    ],
    "Esportes": [
        'FREE','YURI ON ICE','PING PONG','MAJOR','CROSS GAME',
        'EYESHIELD 21','PRINCE OF TENNIS','HAJIME NO IPPO','BLUE LOCK',
        'SK8','WIND BREAKER','HARUKANA RECEIVE','BATTERY','DAYS',
    ],
    "Fantasia": [
        'FRIEREN','ANCIENT MAGUS','LITTLE WITCH ACADEMIA',
        'SLAYERS','LODOSS WAR','GOBLIN SLAYER','GRIMGAR',
        'RECORD OF GRANCREST','SCRAPPED PRINCESS','DELTORA QUEST',
    ],
    "Sci-Fi": [
        'PSYCHO PASS','SPACE DANDY','BEATLESS','VIVY',
        'DIMENSION W','QUALIDEA CODE','HEROIC AGE','TOWARD THE TERRA',
        'KNIGHT OF SIDONIA',
    ],
    "Sobrenatural": [
        'YU YU HAKUSHO','NORAGAMI','KEKKAI SENSEN','TOILET BOUND',
        'HANAKO KUN','NATSUME','XXXHOLIC','MUSHISHI','USHIO AND TORA',
        'NURARIHYON','NURA','TACTICS',
    ],
    "Historico": [
        'VAGABOND','DORORO','HAKUOUKI','ANGOLMOIS',
        'SWORD OF THE STRANGER','SENGOKU BASARA','NOBUNAGA',
        'ALTAIR','THE HEROIC LEGEND OF ARSLAN',
    ],
    "Musica e Idols": [
        'LOVE LIVE','IDOLMASTER','AKB0048','BOCCHI THE ROCK','GIVEN',
        'OSHI NO KO','SHOW BY ROCK','REVUE STARLIGHT','BANG DREAM',
        'CAROLE AND TUESDAY','PROMARE',
    ],
    "Comedia": [
        'GINTAMA','KONOSUBA','LUCKY STAR','PRISON SCHOOL',
        'GRAND BLUE','SAIKI KUSUO','ONE PUNCH MAN','HINAMATSURI',
        'CAUTIOUS HERO','DOCTOR STONE','ASOBI ASOBASE','CROMARTIE',
        'DAILY LIVES',
    ],
    "Clasicos": [
        'DRAGON BALL Z','DRAGON BALL GT','CAVALEIROS DO ZODIACO',
        'SAINT SEIYA','SAILOR MOON','CITY HUNTER','CANDY CANDY',
        'RANMA','URUSEI YATSURA','MAISON IKKOKU','DORAEMON',
        'LUPIN III','LUPIN 3','COBRA','MAZINGER','GETTER ROBO',
        'GATCHAMAN','CASSHERN','DEVILMAN','CUTEY HONEY',
        'CAPTAIN HARLOCK','GALAXY EXPRESS','SPEED RACER','ASTRO BOY',
        'VOLTRON',
    ],
    "Ecchi e Harem": [
        'HIGHSCHOOL DXD','MONSTER MUSUME','TO LOVE RU','ROSARIO VAMPIRE',
        'SEKIREI','FREEZING','IKKITOUSEN','QUEENS BLADE','SHIMONETA',
        'SHINMAI MAOU','MAKEN KI','VALKYRIE DRIVE','INFINITE STRATOS',
        'YURAGI-SOU','DAKARA BOKU','HYBRID X HEART','HUNDRED',
        'MASOU GAKUEN',
    ],
    "Hentai": [
        'HENTAI','[XXX]','UNCENSORED','BOIN','OVERFLOW',
        'OPPAI','FUTANARI','NIGHT SHIFT NURSES','EROGE',
    ],
    "Dublado": ['DUBLADO','DUB','PT-BR'],
    "Legendado": ['LEGENDADO','LEG','PT-PT'],
}

# Group-titles genéricos que não têm informação de categoria útil
GT_GENERICOS = {
    'animes vod', 'anime', 'animes', 'vod', 'series', 'séries',
    'filmes', 'movies', 'geral', 'others', 'outros', 'general',
    'misc', 'uncategorized', '',
}


def detectar_categoria_anime(nome: str) -> str:
    n = nome.upper()
    for cat, keywords in CATEGORIAS_ANIME.items():
        if any(k in n for k in keywords):
            return cat
    return "Geral"


# ─────────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO
# ─────────────────────────────────────────────────────────────────

def detectar_tipo_por_url(url: str) -> str:
    u = url.lower()
    if "/live/"   in u: return "live"
    if "/series/" in u: return "series"
    if "/movie/"  in u: return "movie"
    if "/vod/"    in u: return "movie"
    if u.endswith(".ts"):   return "live"
    if u.endswith(".mp4"):  return "movie"
    if u.endswith(".m3u8"): return "live"
    return "unknown"


def classificar_item(nome: str, url: str, group_title: str) -> dict:
    tipo = detectar_tipo_por_url(url)
    gt   = group_title.strip()

    # Extrai subcategoria do group-title da fonte
    sub = gt
    for prefix in ["Series |", "Séries |", "Canais |", "Filmes |",
                   "Movies |", "VOD |"]:
        if sub.lower().startswith(prefix.lower()):
            sub = sub[len(prefix):].strip()
            break

    # Se o group-title é genérico, detecta categoria pelo nome do anime
    if sub.lower() in GT_GENERICOS:
        sub = detectar_categoria_anime(nome)

    # Classificação por URL path (mais confiável)
    if tipo == "live":
        return {"grupo": "Canais", "categoria": sub or "Geral", "tipo": "live"}
    if tipo in ("movie", "vod"):
        return {"grupo": "Filmes", "categoria": sub or "Geral", "tipo": "movie"}
    if tipo == "series":
        return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}

    # Fallback: deduz pelo group-title original
    gt_up = gt.upper()
    if any(k in gt_up for k in ["CANAL","LIVE","TV ","CHANNEL","AO VIVO"]):
        return {"grupo": "Canais", "categoria": sub or "Geral", "tipo": "live"}
    if any(k in gt_up for k in ["MOVIE","FILME","FILM","CINEMA","HENTAI","[XXX]","XXX"]):
        return {"grupo": "Filmes", "categoria": sub or "Geral", "tipo": "movie"}

    # Padrão: série
    return {"grupo": "Series", "categoria": sub or "Geral", "tipo": "series"}


# ─────────────────────────────────────────────────────────────────
# PARSE DE SÉRIE
# ─────────────────────────────────────────────────────────────────

def parse_serie(nome: str) -> dict:
    # Remove sufixos de idioma antes de parsear
    nome_clean = re.sub(
        r'\s*[\(\[]?\s*(dublado|legendado|dub|leg|pt-br|pt-pt)\s*[\)\]]?\s*$',
        '', nome, flags=re.IGNORECASE
    ).strip()

    # Formato SxxExx
    m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', nome_clean)
    if m:
        titulo    = nome_clean[:m.start()].strip(" -_|")
        temporada = f"Temporada {int(m.group(1)):02d}"
        episodio  = f"E{int(m.group(2)):02d}"
        return {
            "titulo"   : titulo or nome_clean,
            "temporada": temporada,
            "episodio" : episodio,
            "ep_label" : f"{titulo or nome_clean} {episodio}",
        }

    # Formato por extenso: Temporada X Episodio Y
    m2 = re.search(r'(?:Temporada|Season|T\.?)\s*(\d+)', nome_clean, re.IGNORECASE)
    m3 = re.search(r'(?:Epis[oó]dio|Episode|Ep\.?|E\.?)\s*(\d+)', nome_clean, re.IGNORECASE)
    if m2 or m3:
        temp_n    = int(m2.group(1)) if m2 else 1
        ep_n      = int(m3.group(1)) if m3 else 1
        temporada = f"Temporada {temp_n:02d}"
        episodio  = f"E{ep_n:02d}"
        corte     = min(
            m2.start() if m2 else len(nome_clean),
            m3.start() if m3 else len(nome_clean)
        )
        titulo = nome_clean[:corte].strip(" -_|") or nome_clean
        return {
            "titulo"   : titulo,
            "temporada": temporada,
            "episodio" : episodio,
            "ep_label" : f"{titulo} {episodio}",
        }

    # Sem indicador de episódio
    return {
        "titulo"   : nome_clean,
        "temporada": "Temporada 01",
        "episodio" : "E01",
        "ep_label" : nome_clean,
    }


# ─────────────────────────────────────────────────────────────────
# FILTRO CANAIS BRASIL
# ─────────────────────────────────────────────────────────────────

BR_COUNTRYTAGS = ['BR', 'BRA', 'BRAZIL', 'BRASIL']
BR_NOMES = [
    'GLOBO','SBT','BAND','RECORD','REDETV','TV BRASIL','TV CULTURA',
    'GLOBO NEWS','BAND NEWS','CNN BRASIL','JOVEM PAN','TV ESCOLA',
    'CANAL GOV','SENADO','CÂMARA','FUTURA','MULTISHOW','SPORTV',
    'PREMIERE','REDE BRASIL','TV APARECIDA','REDE VIDA','ISTV',
]


def is_canal_brasileiro(nome: str, url: str, extinf: str) -> bool:
    n = nome.upper()
    e = extinf.upper()
    country = re.search(r'TVG-COUNTRY="([^"]*)"', e)
    if country and any(br in country.group(1) for br in BR_COUNTRYTAGS):
        return True
    tvgid = re.search(r'tvg-id="([^"]*)"', extinf, re.IGNORECASE)
    if tvgid and any(br in tvgid.group(1).lower()
                     for br in ['globo','sbt','band','record','redetv',
                                'tvcultura','tvbrasil','camara','senado']):
        return True
    if any(br in n for br in BR_NOMES):
        return True
    if any(d in url.lower() for d in ['.com.br','.gov.br','.org.br',
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

            # tvg-name
            nome_m = re.search(r'tvg-name="([^"]*)"', line)
            nome   = nome_m.group(1).strip() if nome_m else ""
            if not nome:
                nome_m2 = re.search(r',([^,]+)$', line)
                nome = nome_m2.group(1).strip() if nome_m2 else ""

            if not nome or len(nome) < 2:
                continue

            # Descarta entradas cujo nome é apenas filename
            if re.match(r'^[\w\-\.]+\.(m3u8?|ts|mp4|mkv)$', nome.lower()):
                continue

            # group-title
            gt_m = re.search(r'group-title="([^"]*)"', line)
            gt   = gt_m.group(1).strip() if gt_m else ""

            # tvg-logo
            logo_m = re.search(r'tvg-logo="([^"]*)"', line)
            logo   = logo_m.group(1).strip() if logo_m else ""

            if filtro_br and not is_canal_brasileiro(nome, url_linha, line):
                continue

            encontrados.append({
                "Nome"       : nome,
                "URL"        : url_linha,
                "group_title": gt,
                "logo"       : logo,
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

    # Classifica
    for item in unicos:
        item.update(classificar_item(
            item["Nome"], item["URL"], item.get("group_title", "")
        ))

    # Separa grupos
    canais = sorted(
        [i for i in unicos if i["grupo"] == "Canais"],
        key=lambda x: (x["categoria"].upper(), x["Nome"].upper())
    )
    filmes = sorted(
        [i for i in unicos if i["grupo"] == "Filmes"],
        key=lambda x: (x["categoria"].upper(), x["Nome"].upper())
    )

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
        # group-title="Canais | <categoria>"
        # label = nome do canal
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
        # group-title="Series | <categoria> | <título> | <temporada>"
        # label = título + episódio  ex: "Naruto E01"
        f.write(f"\n### ══════════ SÉRIES ({len(series)}) ══════════\n\n")

        cat_atual    = None
        titulo_atual = None
        temp_atual   = None

        for item in series:
            cat      = item["categoria"]
            titulo   = item["titulo"]
            temporada= item["temporada"]
            episodio = item["episodio"]
            ep_label = item["ep_label"]
            logo     = item.get("logo", "")

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

            group = f"Series | {cat} | {titulo} | {temporada}"

            f.write(
                f'#EXTINF:-1 tvg-name="{ep_label}" tvg-logo="{logo}" '
                f'tvg-type="series" '
                f'group-title="{group}", {ep_label}\n'
            )
            f.write(f'{item["URL"]}\n\n')

        # ── FILMES ────────────────────────────────────────────────
        # group-title="Filmes | <categoria>"
        # label = nome do filme
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
