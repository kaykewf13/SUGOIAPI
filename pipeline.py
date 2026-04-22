"""
SUGOIAPI Pipeline Completo
Varredura + Validação + Classificação + Geração M3U
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

# ── Repositório SUGOIAPI ──────────────────────────────────────────
REPO_OWNER = "kaykewf13"
REPO_NAME  = "SUGOIAPI"
BRANCH     = "main"

# ── Fontes externas ───────────────────────────────────────────────
SOURCES_ANIME = [
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/JapanTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/DrewLiveVOD.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/PlutoTV.m3u8",
    "https://raw.githubusercontent.com/konanda-sg/DrewLive-1/main/TubiTV.m3u8",
    "https://raw.githubusercontent.com/L3uS-IPTV/Animes/main/animes.m3u",
    "https://raw.githubusercontent.com/Iptv-Animes/AutoUpdate/main/lista.m3u",
    "https://m3u.ibert.me/jp.m3u",
]

SOURCE_CANAIS_BR = \
    "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"

EPG_URL = "http://drewlive24.duckdns.org:8081/merged_epg.xml.gz"

# ── Extensões de mídia ────────────────────────────────────────────
FILTRO_MEDIA_URL = ['.m3u', '.m3u8', '.mp4', '.mkv', '.ts', 'get.php']

# ─────────────────────────────────────────────────────────────────
# FILTRO PORTUGUÊS
# ─────────────────────────────────────────────────────────────────

PT_KEYWORDS_NOME = [
    'DUBLADO', 'DUB', 'PT-BR', 'PT-PT', 'LEGENDADO', 'LEG',
    'PORTUGU', 'BRASIL', 'LUSOFONO',
]
PT_KEYWORDS_EXTINF = [
    'portuguese', 'pt-br', 'pt-pt', '"pt"',
    'tvg-country="br"', 'tvg-country="pt"',
]
PT_DOMINIOS = ['.com.br', '.tv.br', '/br/', '/pt/']


def tem_portugues(nome: str, url: str, extinf: str) -> bool:
    n = nome.upper()
    e = extinf.lower()
    if any(k in n for k in PT_KEYWORDS_NOME):
        return True
    if any(k in e for k in PT_KEYWORDS_EXTINF):
        return True
    if any(d in url.lower() for d in PT_DOMINIOS):
        return True
    return False

# ─────────────────────────────────────────────────────────────────
# FILTRO CANAIS BRASIL
# ─────────────────────────────────────────────────────────────────

BR_COUNTRYTAGS = ['BR', 'BRA', 'BRAZIL', 'BRASIL']
BR_TVGIDS      = ['globo', 'sbt', 'band', 'record', 'redetv', 'tvcultura',
                  'tvbrasil', 'globonews', 'bandnews', 'cnnbrasil', 'jovempan',
                  'tvescola', 'canal.gov', 'senado', 'camara', 'futura']
BR_NOMES       = ['GLOBO', 'SBT', 'BAND', 'RECORD', 'REDETV', 'TV BRASIL',
                  'TV CULTURA', 'GLOBO NEWS', 'BAND NEWS', 'CNN BRASIL',
                  'JOVEM PAN', 'TV ESCOLA', 'CANAL GOV', 'SENADO', 'CÂMARA',
                  'FUTURA', 'MULTISHOW', 'SPORTV', 'PREMIERE',
                  'TV APARECIDA', 'REDE VIDA', 'TERRA VIVA']


def is_canal_brasileiro(nome: str, url: str, extinf: str) -> bool:
    n = nome.upper()
    e = extinf.upper()
    country = re.search(r'TVG-COUNTRY="([^"]*)"', e)
    if country and any(br in country.group(1) for br in BR_COUNTRYTAGS):
        return True
    tvgid = re.search(r'tvg-id="([^"]*)"', extinf, re.IGNORECASE)
    if tvgid and any(br in tvgid.group(1).lower() for br in BR_TVGIDS):
        return True
    if any(br in n for br in BR_NOMES):
        return True
    if '.com.br' in url.lower() or '/br/' in url.lower():
        return True
    return False

# ─────────────────────────────────────────────────────────────────
# MAPEAMENTO COMPLETO DE CATEGORIAS
# ─────────────────────────────────────────────────────────────────

LIVE_KEYWORDS   = ['TV', 'LIVE', '24/7', 'AO VIVO', 'CANAL', 'CHANNEL', 'ONLINE']
MOVIE_KEYWORDS  = ['FILME', 'MOVIE', 'CINEMA', 'LONGA']
SERIES_KEYWORDS = ['SERIE', 'TEMPORADA', 'EPISODIO', 'EP.', ' S0', ' S1', ' S2',
                   'SEASON', 'EPISODE', 'OVA']

CATEGORIAS_SERIES = {
    "Shounen": [
        'NARUTO', 'ONE PIECE', 'DRAGON BALL', 'BLEACH', 'FAIRY TAIL',
        'DEMON SLAYER', 'KIMETSU', 'ATTACK ON TITAN', 'SHINGEKI',
        'HUNTER X HUNTER', 'FULLMETAL', 'MY HERO ACADEMIA', 'BOKU NO HERO',
        'JUJUTSU KAISEN', 'BLACK CLOVER', 'FIRE FORCE', 'SOUL EATER',
        'BLUE EXORCIST', 'INUYASHA', 'TORIKO', 'REBORN', 'HITMAN',
        'HAIKYUU', 'KUROKO', 'SLAM DUNK', 'EYESHIELD', 'PRINCE OF TENNIS',
        'CAPTAIN TSUBASA', 'BEYBLADE', 'BAKUGAN', 'YU-GI-OH', 'YU GI OH',
        'DIGIMON', 'POKEMON', 'MEDABOTS', 'ZATCH BELL', 'RAVE MASTER',
        'KATEKYO', 'D.GRAY', 'SHAMAN KING', 'MAR', 'KINNIKUMAN',
    ],
    "Shoujo": [
        'SAILOR MOON', 'CARDCAPTOR', 'FRUITS BASKET', 'OURAN', 'CLANNAD',
        'KAMISAMA', 'SKIP BEAT', 'VAMPIRE KNIGHT', 'KAICHOU WA MAID',
        'NANA', 'FULL MOON', 'TOKYO MEW MEW', 'SHUGO CHARA', 'MAGIC KNIGHT',
        'RAYEARTH', 'WEDDING PEACH', 'ULTRA MANIAC', 'MERMAID MELODY',
        'SPECIAL A', 'LOVELY COMPLEX', 'BOKURA GA ITA', 'PARADISE KISS',
    ],
    "Seinen": [
        'BERSERK', 'DEATH NOTE', 'TOKYO GHOUL', 'GANTZ', 'VINLAND SAGA',
        'MONSTER', 'VAGABOND', 'GHOST IN THE SHELL', 'COWBOY BEBOP',
        'TRIGUN', 'HELLSING', 'BLACK LAGOON', 'MADE IN ABYSS', 'DOROHEDORO',
        'GOLDEN KAMUY', 'DUNGEON MESHI', 'MUSHISHI', 'TEXHNOLYZE',
        'ERGO PROXY', 'HOMUNCULUS', 'BLAME', 'AKIRA', 'PLANETES',
    ],
    "Josei": [
        'CHIHAYAFURU', 'NODAME', 'HONEY AND CLOVER', 'WOTAKOI',
        'GEKKAN SHOUJO', 'PRINCESS JELLYFISH', 'ANTIQUE BAKERY',
    ],
    "Isekai": [
        'SWORD ART ONLINE', 'SAO', 'RE:ZERO', 'REZERO', 'OVERLORD',
        'TENSURA', 'SLIME', 'LOG HORIZON', 'NO GAME NO LIFE', 'KONOSUBA',
        'SHIELD HERO', 'MUSHOKU TENSEI', 'DANMACHI', 'TATE NO YUUSHA',
        'ARIFURETA', 'TENSEI', 'ISEKAI', 'JOBLESS', 'SKELETON KNIGHT',
        'VILLAINESS', 'REALIST HERO', 'WORLD TEACHER',
    ],
    "Mecha": [
        'GUNDAM', 'EVANGELION', 'NEON GENESIS', 'CODE GEASS', 'GURREN LAGANN',
        'MACROSS', 'VOLTRON', 'RAHXEPHON', 'EUREKA SEVEN', 'ALDNOAH ZERO',
        'DARLING IN THE FRANXX', 'FULL METAL PANIC', 'ESCAFLOWNE',
        'MAZINGER', 'GETTER ROBO', 'PATLABOR',
    ],
    "Terror e Suspense": [
        'HIGURASHI', 'SHIKI', 'ANOTHER', 'PARASYTE', 'KISEIJUU',
        'PROMISED NEVERLAND', 'MIRAI NIKKI', 'DEADMAN WONDERLAND',
        'HELL GIRL', 'JIGOKU SHOUJO', 'GHOST HUNT', 'BOOGIEPOP',
        'JUNJI ITO', 'BLOOD-C', 'UMINEKO',
    ],
    "Psicologico": [
        'SERIAL EXPERIMENTS', 'STEINS GATE', 'PARANOIA AGENT',
        'WELCOME TO NHK', 'KAKEGURUI', 'CLASSROOM OF THE ELITE',
        'TALENTLESS NANA', 'MORIARTY THE PATRIOT', 'ID INVADED',
    ],
    "Romance": [
        'TORADORA', 'ANGEL BEATS', 'ANOHANA', 'YOUR LIE IN APRIL',
        'SHIGATSU', 'OREGAIRU', 'GOLDEN TIME', 'NISEKOI', 'KAGUYA SAMA',
        'HORIMIYA', 'QUINTESSENTIAL', '5-TOUBUN', 'RENT A GIRLFRIEND',
        'YOUR NAME', 'KIMI NO NA WA', 'AO HARU RIDE', 'SAY I LOVE YOU',
        'PLASTIC MEMORIES', 'TRUE TEARS', 'SHUFFLE', 'AMAGAMI',
    ],
    "Slice of Life": [
        'BARAKAMON', 'SILVER SPOON', 'ARIA', 'LAID BACK CAMP', 'YURU CAMP',
        'NON NON BIYORI', 'K-ON', 'LUCKY STAR', 'AZUMANGA', 'NICHIJOU',
        'HIDAMARI SKETCH', 'YOTSUBA', 'ENCOURAGEMENT OF CLIMB',
    ],
    "Acao e Aventura": [
        'FULLMETAL', 'RUROUNI KENSHIN', 'SAMURAI X', 'FATE', 'STAY NIGHT',
        'JOJO', 'BIZARRE ADVENTURE', 'TOWER OF GOD', 'NANATSU NO TAIZAI',
        'SEVEN DEADLY SINS', 'RECORD OF RAGNAROK', 'CLAYMORE', 'DRIFTERS',
    ],
    "Esportes": [
        'HAIKYUU', 'KUROKO', 'SLAM DUNK', 'CAPTAIN TSUBASA', 'FREE',
        'YURI ON ICE', 'PING PONG', 'MAJOR', 'EYESHIELD 21',
        'PRINCE OF TENNIS', 'HAJIME NO IPPO', 'BLUE LOCK', 'SK8',
    ],
    "Fantasia": [
        'FAIRY TAIL', 'FRIEREN', 'ANCIENT MAGUS', 'LITTLE WITCH ACADEMIA',
        'SLAYERS', 'LODOSS WAR', 'GOBLIN SLAYER', 'GRIMGAR',
    ],
    "Sci-Fi": [
        'PSYCHO PASS', 'GHOST IN THE SHELL', 'COWBOY BEBOP', 'SPACE DANDY',
        'PLANETES', 'BEATLESS', 'VIVY', 'DIMENSION W', 'ALDNOAH',
    ],
    "Sobrenatural": [
        'YU YU HAKUSHO', 'NORAGAMI', 'KEKKAI SENSEN', 'TOILET BOUND',
        'NATSUME', 'XXXHOLIC', 'MUSHISHI', 'USHIO AND TORA',
    ],
    "Historico": [
        'RUROUNI KENSHIN', 'VAGABOND', 'VINLAND SAGA', 'GOLDEN KAMUY',
        'DORORO', 'HAKUOUKI', 'SENGOKU BASARA', 'DRIFTERS', 'ALTAIR',
    ],
    "Musica e Idols": [
        'K-ON', 'LOVE LIVE', 'IDOLMASTER', 'BOCCHI THE ROCK', 'GIVEN',
        'OSHI NO KO', 'MACROSS', 'SHOW BY ROCK', 'REVUE STARLIGHT',
        'BANG DREAM',
    ],
    "Comedia": [
        'GINTAMA', 'KONOSUBA', 'NICHIJOU', 'LUCKY STAR', 'SCHOOL RUMBLE',
        'PRISON SCHOOL', 'GRAND BLUE', 'SAIKI KUSUO', 'ONE PUNCH MAN',
        'HINAMATSURI', 'CAUTIOUS HERO', 'DOCTOR STONE', 'ASOBI ASOBASE',
    ],
    "Clasicos": [
        'DRAGON BALL Z', 'DRAGON BALL GT', 'CAVALEIROS DO ZODIACO',
        'SAINT SEIYA', 'YU GI OH', 'POKEMON', 'DIGIMON', 'SAILOR MOON',
        'CITY HUNTER', 'CANDY CANDY', 'RANMA', 'DORAEMON', 'LUPIN III',
        'LUPIN 3', 'COBRA', 'MAZINGER', 'GATCHAMAN', 'DEVILMAN',
        'CAPTAIN HARLOCK', 'GALAXY EXPRESS', 'SPEED RACER',
    ],
    "Ecchi e Harem": [
        'HIGHSCHOOL DXD', 'MONSTER MUSUME', 'TO LOVE RU', 'ROSARIO VAMPIRE',
        'SEKIREI', 'FREEZING', 'IKKITOUSEN', 'QUEENS BLADE', 'SHIMONETA',
        'SHINMAI MAOU', 'MAKEN KI', 'VALKYRIE DRIVE', 'INFINITE STRATOS',
        'YURAGI-SOU', 'DAKARA BOKU',
    ],
    "Dublado"  : ['DUBLADO', 'DUB', 'PT-BR'],
    "Legendado": ['LEGENDADO', 'LEG', 'PT-PT'],
}

CATEGORIAS_FILMES = {
    "Acao"     : ['ACTION', 'ACAO', 'BATTLE', 'FIGHT', 'GUERRA'],
    "Aventura" : ['ADVENTURE', 'AVENTURA', 'QUEST'],
    "Romance"  : ['ROMANCE', 'LOVE', 'AMOR', 'YOUR NAME', 'KIMI'],
    "Terror"   : ['HORROR', 'TERROR'],
    "Sci-Fi"   : ['SCI-FI', 'SCIFI', 'SPACE', 'MECHA', 'AKIRA'],
    "Fantasia" : ['FANTASY', 'FANTASIA', 'DRAGON', 'MAGIC'],
    "Comedia"  : ['COMEDY', 'COMEDIA', 'HUMOR'],
    "Ghibli"   : ['GHIBLI', 'MIYAZAKI', 'SPIRITED', 'MONONOKE', 'TOTORO',
                  'NAUSICAA', 'PORCO ROSSO', 'LAPUTA', 'PONYO', 'HOWL'],
    "Geral"    : [],
}

# ─────────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO
# ─────────────────────────────────────────────────────────────────

def detectar_categoria(nome_upper: str, mapa: dict) -> str:
    for cat, keywords in mapa.items():
        if any(k in nome_upper for k in keywords):
            return cat
    return "Geral"


def classificar_item(nome: str, url: str) -> dict:
    n = nome.upper()
    if any(k in n for k in LIVE_KEYWORDS):
        return {"grupo": "Canais", "categoria": "Geral", "tipo": "live"}
    if any(k in n for k in MOVIE_KEYWORDS):
        return {"grupo": "Filmes",
                "categoria": detectar_categoria(n, CATEGORIAS_FILMES),
                "tipo": "movie"}
    return {"grupo": "Series",
            "categoria": detectar_categoria(n, CATEGORIAS_SERIES),
            "tipo": "series"}


def parse_serie(nome: str) -> dict:
    m = re.search(r'[Ss](\d{1,2})[Ee](\d{1,3})', nome)
    if m:
        titulo    = nome[:m.start()].strip(" -_|")
        temporada = f"Temporada {int(m.group(1)):02d}"
        episodio  = f"Episodio {int(m.group(2)):03d}"
        return {"titulo": titulo or nome, "temporada": temporada, "episodio": episodio}
    m2 = re.search(r'(?:Temporada|Season)\s*(\d+)', nome, re.IGNORECASE)
    m3 = re.search(r'(?:Epis[oó]dio|Episode|EP\.?)\s*(\d+)', nome, re.IGNORECASE)
    temporada = f"Temporada {int(m2.group(1)):02d}" if m2 else "Temporada 01"
    episodio  = f"Episodio {int(m3.group(1)):03d}"  if m3 else "Episodio 001"
    titulo    = re.split(
        r'(?:Temporada|Season|Epis[oó]dio|Episode|EP\.?)\s*\d+',
        nome, flags=re.IGNORECASE)[0].strip(" -_|")
    return {"titulo": titulo or nome, "temporada": temporada, "episodio": episodio}

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

def extrair_links(raw_url: str, filtro_br: bool = False,
                  filtro_pt: bool = False) -> list:
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
            url    = lines[i + 1].strip() if i + 1 < len(lines) else ""
            nome_m = re.search(r',(.+)$', line)
            nome   = nome_m.group(1).strip() if nome_m else ""

            if not url.startswith('http'):
                continue
            if filtro_br and not is_canal_brasileiro(nome, url, line):
                continue
            if filtro_pt and not tem_portugues(nome, url, line):
                continue

            encontrados.append({"Nome": nome, "URL": url, "extinf": line})

        # URLs soltas com extensão de mídia
        urls_usadas = {i["URL"] for i in encontrados}
        for url in re.findall(r'(https?://\S+)', res.text):
            if url in urls_usadas:
                continue
            if any(f in url for f in FILTRO_MEDIA_URL):
                nome = url.split("/")[-1].split("?")[0]
                if filtro_pt and not tem_portugues(nome, url, ""):
                    continue
                encontrados.append({"Nome": nome, "URL": url, "extinf": ""})

        return encontrados

    except Exception as e:
        print(f"  ⚠️  {raw_url[:60]}: {e}")
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
# ETAPA 4 — Geração da M3U classificada
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
        item.update(classificar_item(item["Nome"], item["URL"]))

    # Separa grupos
    canais = sorted(
        [i for i in unicos if i["grupo"] == "Canais"],
        key=lambda x: x["Nome"].upper()
    )
    filmes = sorted(
        [i for i in unicos if i["grupo"] == "Filmes"],
        key=lambda x: (x["categoria"], x["Nome"].upper())
    )
    series = [i for i in unicos if i["grupo"] == "Series"]
    for s in series:
        s.update(parse_serie(s["Nome"]))
    series.sort(key=lambda x: (
        x["categoria"], x["titulo"].upper(), x["temporada"], x["episodio"]
    ))

    m3u_path = OUTPUT_DIR / "playlist_validada.m3u"

    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write(f'#EXTM3U x-tvg-url="{EPG_URL}" m3u-type="m3u_plus"\n\n')

        # ── CANAIS ────────────────────────────────────────────────
        f.write(f"### ══════════ CANAIS ({len(canais)}) ══════════\n\n")
        for item in canais:
            nome = re.sub(r'[^\w\s\-]', '', item["Nome"]).strip() or "Canal"
            cat  = item.get("categoria", "Geral")
            f.write(
                f'#EXTINF:-1 tvg-name="{nome}" tvg-type="live" '
                f'group-title="Canais | {cat}", {nome}\n'
            )
            f.write(f'{item["URL"]}\n\n')

        # ── SÉRIES ────────────────────────────────────────────────
        f.write(f"\n### ══════════ SÉRIES ({len(series)}) ══════════\n")
        cat_atual = None
        for item in series:
            if item["categoria"] != cat_atual:
                cat_atual = item["categoria"]
                f.write(f"\n## ── {cat_atual} ──\n\n")
            titulo    = item["titulo"]
            temporada = item["temporada"]
            episodio  = item["episodio"]
            tvg_name  = f"{titulo} | {temporada} | {episodio}"
            f.write(
                f'#EXTINF:-1 tvg-name="{tvg_name}" tvg-type="series" '
                f'group-title="Series | {cat_atual} | {titulo} | {temporada}"'
                f', {episodio}\n'
            )
            f.write(f'{item["URL"]}\n\n')

        # ── FILMES ────────────────────────────────────────────────
        f.write(f"\n### ══════════ FILMES ({len(filmes)}) ══════════\n")
        cat_atual = None
        for item in filmes:
            if item["categoria"] != cat_atual:
                cat_atual = item["categoria"]
                f.write(f"\n## ── {cat_atual} ──\n\n")
            nome = re.sub(r'[^\w\s\-]', '', item["Nome"]).strip() or "Filme"
            f.write(
                f'#EXTINF:-1 tvg-name="{nome}" tvg-type="movie" '
                f'group-title="Filmes | {cat_atual}", {nome}\n'
            )
            f.write(f'{item["URL"]}\n\n')

    # Resumo
    print(f"\n{'─'*42}")
    print(f"  Canais  → {len(canais):>5}")
    print(f"  Séries  → {len(series):>5}")
    print(f"  Filmes  → {len(filmes):>5}")
    print(f"  Total   → {len(unicos):>5} links reais validados")
    print(f"{'─'*42}")
    print(f"  EPG  → {EPG_URL}")
    print(f"  M3U  → {m3u_path}")
    print(f"{'─'*42}\n")

# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    acervo = []

    # 1. Varredura completa do repositório SUGOIAPI
    print("📂 Varrendo repositório SUGOIAPI...")
    arquivos = listar_arquivos_repo()
    print(f"   {len(arquivos)} arquivos encontrados")
    with ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(lambda u: extrair_links(u, filtro_pt=True), arquivos):
            acervo.extend(r)
    print(f"   {len(acervo)} links extraídos do repo")

    # 2. Fontes externas de anime (filtro PT)
    print(f"\n🎌 Fontes externas de anime ({len(SOURCES_ANIME)} fontes)...")
    with ThreadPoolExecutor(max_workers=5) as ex:
        for r in ex.map(lambda u: extrair_links(u, filtro_pt=True),
                        SOURCES_ANIME):
            acervo.extend(r)

    # 3. Canais Brasil — Free-TV/IPTV
    print("\n📺 Canais brasileiros (Free-TV)...")
    canais_br = extrair_links(SOURCE_CANAIS_BR, filtro_br=True)
    acervo.extend(canais_br)
    print(f"   {len(canais_br)} canais BR encontrados")

    print(f"\n📦 Total bruto: {len(acervo)} entradas")

    # 4. Validação real
    print("\n⚡ Validando links reais em paralelo...")
    validos = validar_em_paralelo(acervo)
    print(f"   {len(validos)} links confirmados vivos")

    # 5. Geração da M3U classificada
    print("\n📝 Gerando playlist classificada...")
    gerar_m3u(validos)
