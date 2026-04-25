# SUGOIAPI Pipeline v3.5
# - Validação separada: canais live validados, VOD sem validação
# - Fontes consolidadas por tipo (SOURCES_LIVE / SOURCES_VOD)
# - Parse completo: SxxExx, EP01, 2nd Season, Temporada N
# - Grupos de canais por tipo + filmes por gênero
# - CATEGORIAS_ANIME v2.0: 1079 keywords em 23 categorias
# - Detecção com word-boundary (sem falsos positivos por substring)


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
# CATEGORIAS DE ANIME
# ─────────────────────────────────────────────────────────────────

CATEGORIAS_ANIME = {

    # ── SHOUNEN ──────────────────────────────────────────────────
    # Alta cobertura — mantém e expande com títulos recentes
    "Shounen": [
        # Big Three clássico
        'NARUTO','BORUTO','ONE PIECE','DRAGON BALL','BLEACH',
        # Nova geração
        'DEMON SLAYER','KIMETSU','JUJUTSU KAISEN','MY HERO ACADEMIA',
        'BOKU NO HERO','ATTACK ON TITAN','SHINGEKI','BLACK CLOVER',
        'FAIRY TAIL','HUNTER X HUNTER','FULLMETAL','FIRE FORCE',
        'SOUL EATER','BLUE EXORCIST','INUYASHA','HAIKYUU',
        'KUROKO','SLAM DUNK','EYESHIELD','CAPTAIN TSUBASA',
        'BEYBLADE','YU GI OH','DIGIMON','POKEMON',
        'SHAMAN KING','TORIKO','D.GRAY','MAR','RAVE MASTER',
        'MEDABOTS','KATEKYO','REBORN','ZATCH BELL',
        # 2020+
        'CHAINSAW MAN','SPY X FAMILY','DR STONE','DOCTOR STONE',
        'TOILET BOUND','HANAKO KUN','WIND BREAKER',
        'MASHLE','DANDADAN','UNDEAD UNLUCK','WITCH WATCH',
        'AYASHIMON','AKANE BANASHI','WITCH HAT',
    ],

    # ── SHOUJO ───────────────────────────────────────────────────
    "Shoujo": [
        'SAILOR MOON','CARDCAPTOR','FRUITS BASKET','OURAN',
        'CLANNAD','KAMISAMA','SKIP BEAT','VAMPIRE KNIGHT',
        'KAICHOU WA MAID','NANA','FULL MOON','TOKYO MEW MEW',
        'SHUGO CHARA','MAGIC KNIGHT','RAYEARTH','WEDDING PEACH',
        'MERMAID MELODY','SPECIAL A','LOVELY COMPLEX',
        'BOKURA GA ITA','PARADISE KISS','PEACH GIRL',
        # Expandido
        'YONA OF THE DAWN','AKATSUKI NO YONA','FUSHIGI YUGI',
        'KAMIKAZE KAITOU JEANNE','ULTRA MANIAC','GAKUEN ALICE',
        'ABSOLUTE BOYFRIEND','ABSOLUTE BOY FRIEND',
        'ITAZURA NA KISS','BOYS OVER FLOWERS','HANA YORI DANGO',
        'BOKURA GA ITA','HIGH SCHOOL DEBUT','ZETTAI KARESHI',
        'SUGAR SUGAR RUNE','PRETEAR','FULL MOON',
        'ORE MONOGATARI','MY LOVE STORY','WOLF GIRL',
        'HIRUNAKA NO RYUUSEI','DAYTIME SHOOTING STAR',
    ],

    # ── SEINEN ───────────────────────────────────────────────────
    "Seinen": [
        'BERSERK','DEATH NOTE','TOKYO GHOUL','GANTZ','VINLAND SAGA',
        'MONSTER','VAGABOND','GHOST IN THE SHELL','COWBOY BEBOP',
        'TRIGUN','HELLSING','BLACK LAGOON','MADE IN ABYSS','DOROHEDORO',
        'GOLDEN KAMUY','DUNGEON MESHI','MUSHISHI','ERGO PROXY','AKIRA',
        'PLANETES','ELFEN LIED','HOMUNCULUS','BLAME',
        # Expandido
        'ODD TAXI','DEVILMAN CRYBABY','CYBER CITY','TEXHNOLYZE',
        'LAND OF THE LUSTROUS','HOUSEKI NO KUNI','PUNPUN',
        'SHIGURUI','BIOMEGA','NIHEI','GHOST HOUND',
        'KOUKYOUSHIHEN EUREKA SEVEN','TERROR IN RESONANCE',
        'ZANKYOU NO TERROR','JIN ROH','DRAGON HEAD',
        'PRISON SCHOOL','GRAND BLUE'
        'SHIMONETA','RAINBOW','RAINBOW NISHA',
        'WAVE LISTEN TO ME','NAMI YO KIITEKURE',
        'BARTENDER','OISHINBO','DROPS OF GOD',
        'MUSHOKU TENSEI','DUNGEON MESHI','DELICIOUS IN DUNGEON',
    ],

    # ── JOSEI ────────────────────────────────────────────────────
    # Categoria fraca — expansão agressiva
    "Josei": [
        'CHIHAYAFURU','NODAME','HONEY AND CLOVER','WOTAKOI',
        'GEKKAN SHOUJO','PRINCESS JELLYFISH','ANTIQUE BAKERY',
        # Expandido
        'USAGI DROP','BUNNY DROP','KIMI WA PET','TRAMPS LIKE US',
        'LOVELESS','SKIP BEAT','PARADISE KISS',
        'NANA','OOKU THE INNER CHAMBERS','BASARA',
        'JOSEI','RISTORANTE PARADISO','BUTTERFLIES FLOWERS',
        'MIDNIGHT SECRETARY','VOICE OR NOISE',
        'HATARAKI MAN','WORKING WOMAN','SUPPLI',
        'SWEET REIN','SETONA MIZUSHIRO',
        'PURE TRANCE','OTOMEN',
    ],

    # ── ISEKAI ───────────────────────────────────────────────────
    "Isekai": [
        'SWORD ART ONLINE','SAO','RE:ZERO','REZERO','OVERLORD',
        'TENSURA','SLIME','LOG HORIZON','NO GAME NO LIFE','KONOSUBA',
        'SHIELD HERO','MUSHOKU TENSEI','DANMACHI','TATE NO YUUSHA',
        'ARIFURETA','ISEKAI','TENSEI','JOBLESS',
        'SKELETON KNIGHT','VILLAINESS','REALIST HERO',
        # Expandido
        'ASCENDANCE OF A BOOKWORM','HONZUKI NO GEKOKUJOU',
        'THAT TIME I GOT REINCARNATED','SLIME DIARIES',
        'BY THE GRACE OF THE GODS','KAMIATA DE ISEKAI',
        'IN ANOTHER WORLD WITH MY SMARTPHONE','ISEKAI WA',
        'DEATH MARCH','SWORD ART ONLINE ALICIZATION',
        'RISING OF THE SHIELD HERO',
        'OTOME GAME NO HAMETSU FLAG','BAKARINA',
        'MY NEXT LIFE AS A VILLAINESS',
        'TRAPPED IN A DATING SIM','ISEKAI OJISAN',
        'UNCLE FROM ANOTHER WORLD',
        'THE GREATEST DEMON LORD IS REBORN',
        'SEIREI GENSOUKI','SPIRIT CHRONICLES',
        'LONER LIFE IN ANOTHER WORLD',
        'MAKE MY ABILITIES AVERAGE',
        'DIDN T I SAY TO MAKE MY ABILITIES AVERAGE',
        'REINCARNATED AS A SWORD','TENSAI OUJI',
        'THE GENIUS PRINCE',
        'FARMING LIFE IN ANOTHER WORLD',
        'CAMPFIRE COOKING IN ANOTHER WORLD',
        'BANISHED FROM THE HERO S PARTY',
        'I VE BEEN KILLING SLIMES',
    ],

    # ── MECHA ────────────────────────────────────────────────────
    "Mecha": [
        'GUNDAM','EVANGELION','NEON GENESIS','CODE GEASS',
        'GURREN LAGANN','TENGEN TOPPA','MACROSS','VOLTRON',
        'EUREKA SEVEN','ALDNOAH','DARLING IN THE FRANXX',
        'FULL METAL PANIC','MAZINGER','GETTER ROBO',
        # Expandido
        'ESCAFLOWNE','VISION OF ESCAFLOWNE','RAHXEPHON',
        'BRAIN POWERD','PATLABOR','GHOST IN THE SHELL',
        'ARMORED TROOPER VOTOMS','VOTOMS',
        'HEAVY METAL L-GAIM','ZETA GUNDAM','ZZ GUNDAM',
        'CHAR S COUNTERATTACK','UNICORN GUNDAM','IRON BLOODED',
        'TEKKETSU NO ORPHANS','RECONGUISTA','BUILD FIGHTERS',
        'WING GUNDAM','GUNDAM SEED','DESTINY',
        'KNIGHT OF SIDONIA','SIDONIA NO KISHI',
        'CAPTAIN EARTH','STAR DRIVER','AQUARION',
        'INFINITE RYVIUS','VANDREAD','NADESICO',
        'INFINITE STRATOS','CROSS ANGE',
    ],

    # ── TERROR E SUSPENSE ────────────────────────────────────────
    "Terror e Suspense": [
        'HIGURASHI','WHEN THEY CRY','SHIKI','ANOTHER','PARASYTE',
        'KISEIJUU','PROMISED NEVERLAND','MIRAI NIKKI','FUTURE DIARY',
        'DEADMAN WONDERLAND','HELL GIRL','JIGOKU SHOUJO','GHOST HUNT',
        'JUNJI ITO','BLOOD-C','UMINEKO',
        # Expandido
        'DEVILMAN CRYBABY','BLOOD THE LAST VAMPIRE',
        'BOOGIEPOP','BOOGIEPOP PHANTOM',
        'CORPSE PARTY','TERRA FORMARS',
        'SCHOOL LIVE','GAKKOU GURASHI',
        'SCHOOL-LIVE','HAPPY SUGAR LIFE',
        'MAGICAL GIRL SITE','MAHOU SHOUJO SITE',
        'MAGICAL GIRL RAISING PROJECT',
        'MAGICAL GIRL SPEC-OPS ASUKA',
        'BTOOOM','BTOOM','DARWIN S GAME','DARWIN NO GAME',
        'EVIL OR LIVE','ANIME DE WAKARU',
        'PUPA','YAMISHIBAI','JAPANESE GHOST STORIES',
        'PETSHOP OF HORRORS','REQUIEM FROM THE DARKNESS',
        'SHIGURUI DEATH FRENZY',
        'GENOCIDAL ORGAN',
    ],

    # ── PSICOLÓGICO ──────────────────────────────────────────────
    # Categoria fraca — expansão forte
    "Psicologico": [
        'SERIAL EXPERIMENTS','STEINS GATE','PARANOIA AGENT',
        'WELCOME TO NHK','KAKEGURUI','CLASSROOM OF THE ELITE',
        'TALENTLESS NANA','ID INVADED',
        # Expandido
        'PERFECT BLUE','LAIN','SERIAL EXPERIMENTS LAIN',
        'TATAMI GALAXY','YOJOUHAN SHINWA TAIKEI','YOJOUHAN',
        'PENGUINDRUM','MAWARU PENGUINDRUM',
        'WONDER EGG PRIORITY','SONNY BOY',
        'ODD TAXI','TEXHNOLYZE',
        'FLOWERS OF EVIL','AKU NO HANA',
        'BOOGIEPOP','ASTRA LOST IN SPACE',
        'LINK CLICK','SHIGUANG DAILIREN',
        'THE PROMISED NEVERLAND','YAKUSOKU NO NEVERLAND',
        'MORIARTY THE PATRIOT','YUUKOKU NO MORIARTY',
        'VANITAS NO CARTE','CASE STUDY OF VANITAS',
        'NO LONGER HUMAN','NINGEN SHIKKAKU',
        'BEAUTIFUL BONES','SAKURAKO SAN',
        'RAMPO KITAN','RANPO KITAN GAME OF LAPLACE',
        'NOBLESSE','KUBIKIRI CYCLE',
    ],

    # ── ROMANCE ──────────────────────────────────────────────────
    "Romance": [
        'TORADORA','ANGEL BEATS','ANOHANA','YOUR LIE IN APRIL',
        'SHIGATSU','OREGAIRU','GOLDEN TIME','NISEKOI','KAGUYA SAMA',
        'HORIMIYA','QUINTESSENTIAL','5-TOUBUN','RENT A GIRLFRIEND',
        'YOUR NAME','KIMI NO NA WA','AO HARU RIDE','PLASTIC MEMORIES',
        'ITAZURA NA KISS','WHITE ALBUM',
        # Expandido
        'CLANNAD','CLANNAD AFTER STORY','KANON','AIR',
        'LITTLE BUSTERS','CHARLOTTE','ANGEL BEATS',
        'MYSELF YOURSELF','TRUE TEARS','EF A TALE OF',
        'SPICE AND WOLF','OOKAMI TO KOUSHINRYOU',
        'NAGI NO ASUKARA','A LULL IN THE SEA',
        'KOKORO CONNECT','TSUKI GA KIREI',
        'JUST BECAUSE','YAGATE KIMI NI NARU',
        'BLOOM INTO YOU','CITRUS','YURU YURI',
        'TAKAGI-SAN','KARAKAI JOUZU','TEASING MASTER',
        'MY DRESS UP DARLING','SONO BISQUE DOLL',
        'MORE THAN A MARRIED COUPLE',
        'AHAREN-SAN','DO YOU LOVE YOUR MOM',
        'RASCAL DOES NOT DREAM','BUNNY GIRL SENPAI',
        'SEISHUN BUTA YAROU','MASAMUNE-KUN',
        'ORESHURA','RAKUDAI KISHI','GAMERS',
        'DATE A LIVE','HIGHSCHOOL DXD',
        'SWORD ART ONLINE','SAO',
        'FRUITS BASKET','VAMPIRE KNIGHT',
    ],

    # ── SLICE OF LIFE ────────────────────────────────────────────
    "Slice of Life": [
        'BARAKAMON','SILVER SPOON','ARIA','LAID BACK CAMP','YURU CAMP',
        'NON NON BIYORI','K-ON','LUCKY STAR','AZUMANGA','NICHIJOU',
        'HIDAMARI SKETCH','FLYING WITCH','HIMOUTO',        # Expandido
        'A-CHANNEL','TAMAKO MARKET','TAMAKO LOVE STORY',
        'GEKKAN SHOUJO NOZAKI','MONTHLY GIRLS NOZAKI',
        'NEW GAME','SHIROBAKO','SAKURA QUEST',
        'WORKING','WAGNARIA','SERVANT X SERVICE',
        'HANAYAMATA','KINIRO MOSAIC','GOLDEN MOSAIC',
        'YUYUSHIKI','GOCHUUMON WA USAGI','GOCHUUMON',
        'IS THE ORDER A RABBIT','GOCHIUSA',
        'YAMA NO SUSUME','ENCOURAGEMENT OF CLIMB',
        'YURUCAMP','IMOUTO SHO','TONIKAKU KAWAII',
        'KAWAII DAKE JA NAI','SHIKIMORI',
        'SLOW LOOP','TAISHOU OTOME','TAISHO OTOME',
        'AQUATOPE','HEIKE MONOGATARI',
        'KAGEKI SHOUJO','REVUE STARLIGHT',
        'SABIKUI BISCO','PARIPI KOUMEI','YA BOY KONGMING',
        'KOMI CAN T COMMUNICATE',
        'KOMI-SAN','SOREDEMO AYUMU','EVEN THOUGH',
        'AKEBI SAILOR UNIFORM','AKEBI-CHAN',
    ],

    # ── AÇÃO E AVENTURA ──────────────────────────────────────────
    "Acao e Aventura": [
        'RUROUNI KENSHIN','SAMURAI X','FATE','STAY NIGHT','FATE ZERO',
        'FATE APOCRYPHA','JOJO','BIZARRE ADVENTURE','TOWER OF GOD',
        'NANATSU NO TAIZAI','SEVEN DEADLY SINS','RECORD OF RAGNAROK',
        'CLAYMORE','DRIFTERS',
        # Expandido
        'ARSLAN SENKI','HEROIC LEGEND OF ARSLAN',
        'MAGI THE LABYRINTH','MAGI THE KINGDOM',
        'AKAME GA KILL','OWARI NO SERAPH','SERAPH OF THE END',
        'GOD EATER','KABANERI OF THE IRON FORTRESS',
        'KOUTETSUJOU NO KABANERI','RADIANT',
        'WORLD TRIGGER','MUGEN NO JUUNIN','BLADE OF THE IMMORTAL',
        'DORORO','SWORD OF THE STRANGER','BASILISK',
        'NINJA SCROLL','GARO','HAKUOKI',
        'CHROME SHELLED REGIOS','FREEZING',
        'INFINITE STRATOS','ASTERISK WAR','ASTERISK',
        'RAKUDAI KISHI','CHIVALRY OF A FAILED KNIGHT',
        'CAMPIONE','SEIKEN TSUKAI NO WORLD BREAK',
        'ABSOLUTE DUO','ANTIMAGIC ACADEMY',
        'BLACK BULLET','BRYNHILDR IN THE DARKNESS',
        'LOST SONG','MAHOU SHOUJO IKUSEI',
        'SELECTOR INFECTED WIXOSS','WIXOSS',
        'YUKI YUNA IS A HERO','YUUKI YUUNA',
        'REWRITE','CHAOS DRAGON','CHAOS HEAD',
        'OCCULTIC NINE','PUNCH LINE',
    ],

    # ── ESPORTES ─────────────────────────────────────────────────
    # Categoria fraca — expansão necessária
    "Esportes": [
        'FREE','YURI ON ICE','PING PONG','MAJOR','CROSS GAME',
        'EYESHIELD 21','PRINCE OF TENNIS','HAJIME NO IPPO',
        'BLUE LOCK','SK8','WIND BREAKER',
        # Expandido
        'ACE OF DIAMOND','DIAMOND NO ACE','DAIYA NO ACE',
        'DAYS','TSURUNE','AHIRU NO SORA','BABY STEPS',
        'CHEER BOYS','HIT THE ICE','BAMBOO BLADE',
        'BREAKER','HANEBADO','OVERTAKE','DRIVE HEAD',
        'SHAKUNETSU NO TAKKYUU MUSUME','SHAKUNETSU',
        'INAZUMA ELEVEN','GIANT KILLING','AREA NO KISHI',
        'AOKANA FOUR RHYTHM','AOKANA',
        'TEPPU','KEIJO','HARUKANA RECEIVE',
        'ATTACKER YOU','VOLLEYBALL','HINOMARU SUMO',
        'MEGALO BOX','MEGALOBOX','ASHITA NO JOE',
        'HAJIME NO IPPO','FIGHTING SPIRIT',
        'ALL OUT','RUGBY','BURNING KABADDI',
        'BAKUTEN','SHAO YAO','NUMBER24',
        'SKATE LEADING STARS','PLAYERS',
        'ORIENT','KUROKO NO BASUKE','KUROKO NO BASKET',
        'SLAM DUNK','CAPETA','F1 RACE',
    ],

    # ── FANTASIA ─────────────────────────────────────────────────
    # Categoria fraca — expansão forte
    "Fantasia": [
        'FRIEREN','ANCIENT MAGUS','LITTLE WITCH ACADEMIA',
        'SLAYERS','LODOSS WAR','GOBLIN SLAYER','GRIMGAR',
        # Expandido
        'MAGI','THE LABYRINTH OF MAGIC',
        'RECORD OF LODOSS WAR','OUTLAW STAR',
        'SPICE AND WOLF','GRIMGAR OF FANTASY AND ASH',
        'CHAIKA THE COFFIN PRINCESS','CHAIKA',
        'LOG HORIZON','MAHOUKA KOUKOU','IRREGULAR AT MAGIC',
        'ROKKA NO YUUSHA','BRAVES OF THE SIX FLOWERS',
        'AKASHIC RECORDS','ROKUDENASHI',
        'ZERO NO TSUKAIMA','FAMILIAR OF ZERO',
        'MONDAIJI','PROBLEM CHILDREN','MONDAIJI-TACHI',
        'THE DEVIL IS A PART-TIMER','HATARAKU MAOU-SAMA',
        'DRAGON QUEST','DRAGON QUEST DAI',
        'ENDRO','SLEEPY PRINCESS','MAOUSAMA RETRY',
        'DEMON KING RETRY','MAOU GAKUIN','MISFIT OF DEMON KING',
        'BY THE GRACE OF THE GODS','KUMA KUMA KUMA BEAR',
        'KUMA BEAR','DIDN T I SAY MAKE MY ABILITIES',
        'HONZUKI NO GEKOKUJOU',
        'SOMALI AND THE FOREST SPIRIT','SOMALI',
        'RADIANT','MAOUJOU DE OYASUMI','SLEEPY PRINCESS IN THE DEMON CASTLE',
        'OTHERSIDE PICNIC','URASEKAI PICNIC',
        'WITCH HAT ATELIER','MAHOUTSUKAI NO YOME',
        'ANCIENT MAGUS BRIDE',
    ],

    # ── SCI-FI ───────────────────────────────────────────────────
    # Categoria fraca — expansão forte
    "Sci-Fi": [
        'PSYCHO PASS','PSYCHO-PASS','COWBOY BEBOP','SPACE DANDY','BEATLESS',
        'VIVY','DIMENSION W','KNIGHT OF SIDONIA',
        # Expandido
        'SERIAL EXPERIMENTS LAIN','GHOST IN THE SHELL',
        'TEXHNOLYZE','ERGO PROXY','TRIGUN',
        'OUTLAW STAR','GURREN LAGANN',
        'KILL LA KILL','LITTLE WITCH ACADEMIA',
        'ALDNOAH ZERO','SIDONIA NO KISHI',
        'CAPTAIN EARTH','CAPTAIN HARLOCK','GALAXY EXPRESS',
        'SPACE BATTLESHIP YAMATO','YAMATO','UCHUU SENKAN',
        'PLANETES','MOONLIGHT MILE',
        'TERRA FORMARS','BLAME','BIOMEGA',
        'EXPELLED FROM PARADISE','EXPELLED',
        'GENOCIDAL ORGAN','HARMONY',
        'FROM THE NEW WORLD','SHINSEKAI YORI',
        'DARLING IN THE FRANXX',
        'ANOHANA','EDEN OF THE EAST',
        'CHAOS CHILD','OCCULTIC NINE',
        'ISLAND','HIMOTE HOUSE',
        'ASTRA LOST IN SPACE','KANATA NO ASTRA',
        'INFINITE RYVIUS','RAHXEPHON',
        'NOW AND THEN HERE AND THERE',
        'ARIA THE SCARLET AMMO','HIDAN NO ARIA',
        'GUILTY CROWN','EUREKA SEVEN','AO',
        'RINNE NO LAGRANGE','VIVIDRED OPERATION',
        'MAJESTIC PRINCE','GARGANTIA','SUISEI NO GARGANTIA',
        'VALVRAVE THE LIBERATOR',
    ],

    # ── SOBRENATURAL ─────────────────────────────────────────────
    "Sobrenatural": [
        'YU YU HAKUSHO','YUYU HAKUSHO','YU-YU HAKUSHO','NORAGAMI','KEKKAI SENSEN','TOILET BOUND',
        'HANAKO KUN','NATSUME','XXXHOLIC','MUSHISHI','USHIO AND TORA',
        # Expandido
        'GHOST HUNT','PETSHOP OF HORRORS','XXXHOLIC',
        'VAMPIRE KNIGHT','ROSARIO VAMPIRE',
        'BLOOD LUST','BLOOD+','BLOOD C',
        'BLUE EXORCIST','AO NO EXORCIST',
        'NORAGAMI','STRAY GODS',
        'INUYASHA','HALF-DEMON PRINCESS',
        'YASHAHIME','RIN-NE','KYOUKAI NO RINNE',
        'SOUL EATER','SOUL EATER NOT',
        'D GRAY MAN','PANDORA HEARTS',
        'ANGEL BEATS','ANOHANA',
        'AYAKASHI','REQUIEM FROM THE DARKNESS',
        'BEYOND THE BOUNDARY','KYOUKAI NO KANATA',
        'KEKKAI SENSEN','BLOOD BLOCKADE BATTLEFRONT',
        'OWARI NO SERAPH','SERAPH OF THE END',
        'ROKKA NO YUUSHA','SERAPH',
        'INTERVAL OF EVIL','YURAGI-SOU',
        'KONOHANA KITAN','KAKURIYO',
        'INU X BOKU SS','INU X BOKU',
        'SERVAMP','FUKIGEN NA MONONOKEAN',
        'MOROSE MONONOKEAN',
        'MONONOKE','SPIRITED AWAY','SEN TO CHIHIRO',
        'PRINCESS MONONOKE','MONONOKE HIME','NAUSICAA',
        'HOWL S MOVING CASTLE','CASTLE IN THE SKY',
        'MY NEIGHBOR TOTORO',
    ],

    # ── HISTÓRICO ────────────────────────────────────────────────
    # Categoria fraca — expansão forte
    "Historico": [
        'DORORO','HAKUOUKI','SENGOKU BASARA',
        'ALTAIR','ARSLAN','ANGOLMOIS',
        # Expandido
        'RUROUNI KENSHIN','SAMURAI X','GINTAMA',
        'THERMAE ROMAE','VINLAND SAGA',
        'GOLDEN KAMUY','KATANAGATARI',
        'SHIGURUI','PEACEMAKER KUROGANE','PEACEMAKER',
        'SEIREI NO MORIBITO','MORIBITO','GUARDIAN',
        'PRINCESS PRINCIPAL','JOKER GAME',
        'IZETTA THE LAST WITCH','IZETTA',
        'MORIARTY THE PATRIOT','YUUKOKU NO MORIARTY',
        'THE ROSE OF VERSAILLES','VERSAILLES NO BARA',
        'LADY OSCAR','BAREFOOT GEN',
        'GRAVE OF THE FIREFLIES','HOTARU NO HAKA',
        'PUMPKIN SCISSORS','HORO MUSUKO',
        'KINGDOM','HEIKE MONOGATARI',
        'TOEI OTOGI MANGA CALENDAR',
        'SAMURAI CHAMPLOO','SWORD OF THE STRANGER',
        'NINJA SCROLL','BASILISK','SHURA NO TOKI',
        'MUSHIBUGYO','BRAVE 10',
        'LAS LINDAS','OOKU',
        'WHEN SUPERNATURAL BATTLES','INUSHINDE',
    ],

    # ── MÚSICA E IDOLS ───────────────────────────────────────────
    # Categoria fraca — expansão forte
    "Musica e Idols": [
        'LOVE LIVE','IDOLMASTER','AKB0048','BOCCHI THE ROCK','GIVEN',
        'OSHI NO KO','SHOW BY ROCK','REVUE STARLIGHT','BANG DREAM',
        'CAROLE AND TUESDAY',
        # Expandido
        'HIBIKE EUPHONIUM','SOUND EUPHONIUM','SOUND! EUPHONIUM',
        'PIANO NO MORI','FOREST OF PIANO',
        'CLASSICALOID','CLASSIC LOID',
        'NANA','BECK','BECK MONGOLIAN CHOP SQUAD',
        'WHITE ALBUM','FUUKA',
        'PARIPI KOUMEI','YA BOY KONGMING',
        'ZOMBIE LAND SAGA','ZOMBIE LAND SAGA REVENGE',
        'D4DJ','D4 DJ FIRST MIX',
        'MACROSS','MACROSS FRONTIER','MACROSS DELTA',
        'MACROSS 7','FIRE BOMBER',
        'SHE AND HER CAT','KIMIIRO FOCUS',
        'LISTENERS','VIVY','FLUORITE EYES SONG',
        'POP TEAM EPIC','BLEND S',
        'DEEMO THE MOVIE','KENSHIN SINGING',
        'AIKATSU','PRETTY RHYTHM','PRIPARA','PRIPRI CHII CHAN',
        'FUTURE CARD BUDDYFIGHT',
        'STAR TWINKLE PRECURE','PRECURE',
        'SYMPHOGEAR','SENKI ZESSHOU SYMPHOGEAR',
        'MACROSS PLUS','DYRL',
        'KARAOKE','OSHI',
    ],

    # ── COMÉDIA ──────────────────────────────────────────────────
    "Comedia": [
        'GINTAMA','KONOSUBA','LUCKY STAR','PRISON SCHOOL',
        'GRAND BLUE','SAIKI KUSUO','ONE PUNCH MAN','HINAMATSURI',
        'CAUTIOUS HERO','DOCTOR STONE','ASOBI ASOBASE','CROMARTIE',
        # Expandido
        'DAILY LIVES OF HIGH SCHOOL BOYS','NICHIBROS',
        'DANSHI KOUKOUSEI','BAKA AND TEST','BAKA TO TEST',
        'SKET DANCE','OURAN','OURAN HIGH SCHOOL',
        'GEKKAN SHOUJO NOZAKI','MONTHLY GIRLS NOZAKI KUN',
        'GABRIEL DROPOUT',
        'TOHRU','DRAGON MAID','KOBAYASHI SAN',
        'MISS KOBAYASHI','INTERVIEW WITH MONSTER GIRLS',
        'DEMI-CHAN','INTERVIEWS WITH MONSTER GIRLS',
        'SERVANT X SERVICE','WORKING','WAGNARIA',
        'THE DEVIL IS A PART TIMER','HATARAKU MAOU',
        'ISEKAI IZAKAYA','ISEKAI SHOKUDOU','RESTAURANT TO ANOTHER',
        'SPACE PATROL LULUCO','INFERNO COP',
        'NICHIJOU','MY ORDINARY LIFE',
        'AZUMANGA DAIOH','SCHOOL RUMBLE',
        'KERORO GUNSO','SGT FROG','PANI PONI DASH',
        'HAIYORE NYARUKO','NYARUKO SAN',
        'EBITEN','DANNA GA NANI','MY HUSBAND WON T FIT',
        'B GATA H KEI','YAMADA S FIRST TIME',
        'SEITOKAI YAKUINDOMO','STUDENT COUNCIL',
        'SABAGEBU','SURVIVAL GAME CLUB',
        'ASOBI NI IKUYO','CAT PLANET CUTIES',
        'NOUCOME','MY MENTAL CHOICES',
        'NAZO NO KANOJO X','MYSTERIOUS GIRLFRIEND X',
    ],

    # ── CLÁSSICOS ────────────────────────────────────────────────
    "Clasicos": [
        'DRAGON BALL Z','DRAGON BALL GT','CAVALEIROS DO ZODIACO',
        'SAINT SEIYA','SAILOR MOON','CITY HUNTER','CANDY CANDY',
        'RANMA','URUSEI YATSURA','DORAEMON','LUPIN III','LUPIN 3',
        'COBRA','MAZINGER','GATCHAMAN','DEVILMAN','CAPTAIN HARLOCK',
        'GALAXY EXPRESS','SPEED RACER','ASTRO BOY','VOLTRON',
        # Expandido
        'SPACE ADVENTURE COBRA','DR SLUMP','ARALE',
        'CAT S EYE','TOUCH','MAISON IKKOKU',
        'KIMAGURE ORANGE ROAD','ORANGE ROAD',
        'MAGICAL ANGEL CREAMY MAMI','CREAMY MAMI',
        'MAGICAL STAR MAGICAL EMI',
        'GEGEGE NO KITARO','KITARO',
        'HAKABA KITARO','YOKAI WATCH',
        'NAUSICAA','FUTURE BOY CONAN',
        'HEIDI GIRL OF THE ALPS','HEIDI',
        'MARCO','3000 LEAGUES IN SEARCH OF MOTHER',
        'ANNE OF GREEN GABLES','REMI NOBODY S BOY',
        'NOBODY S GIRL REMI','TREASURE ISLAND',
        'TOM SAWYER','DOG OF FLANDERS',
        'PRINCESS KNIGHT','RIBBON NO KISHI',
        'CYBORG 009','DEVILMAN LADY',
        'CUTEY HONEY','HURRICANE POLYMAR',
        'CASSHAN','CASSHERN','SCIENCE NINJA TEAM',
        'GETTER ROBO','GREAT MAZINGER','COMBATTLER V',
        'VOLTES V','DALTANIOUS','ZANBOT 3',
        'IDEON','DOUGRAM','MOSPEADA',
        'ORGUSS','SOUTHERN CROSS',
    ],

    # ── ECCHI E HAREM ────────────────────────────────────────────
    "Ecchi e Harem": [
        'HIGHSCHOOL DXD','MONSTER MUSUME','TO LOVE RU',
        'ROSARIO VAMPIRE','SEKIREI','FREEZING','QUEENS BLADE',
        'SHIMONETA','SHINMAI MAOU','VALKYRIE DRIVE',
        'INFINITE STRATOS','YURAGI-SOU','DAKARA BOKU',
        # Expandido
        'TESTAMENT OF SISTER DEVIL','SHINMAI MAOU NO TESTAMENT',
        'RAKUDAI KISHI','CHIVALRY OF A FAILED KNIGHT',
        'ASTERISK WAR','GAKUSEN TOSHI ASTERISK',
        'ABSOLUTE DUO','ANTIMAGIC ACADEMY',
        'WORLD S END HAREM','SHUUMATSU NO HAREM',
        'INTERSPECIES REVIEWERS','ISHUZOKU REVIEWERS',
        'PETER GRILL','PETER GRILL TO KENJA NO JIKAN',
        'HOW NOT TO SUMMON A DEMON LORD','ISEKAI MAOU',
        'MASTER OF RAGNAROK','MASTER OF RAGNAROK BLESSER OF EINHERJAR',
        'PLUNDERER','HYAKUREN NO HAOU',
        'ARIFURETA','TRAPPED IN A DATING SIM',
        'MY WIFE IS THE STUDENT COUNCIL PRESIDENT',
        'NAKAIMO','MY LITTLE SISTER IS AMONG THEM',
        'OniAI','ONII-CHAN DAKEDO AI SA EE',
        'KISS X SIS','YOSUGA NO SORA',
        'OKUSAMA GA SEITOKAICHOU','WIFE IS STUDENT COUNCIL',
        'MAKEN-KI','STRIKE THE BLOOD',
        'DATE A LIVE','UNLIMITED FAFNIR',
        'DRAGONAR ACADEMY','WIND X BLADE X',
    ],

    # ── HENTAI ───────────────────────────────────────────────────
    "Hentai": [
        'HENTAI','[XXX]','UNCENSORED','OVERFLOW','BOIN',
        'OPPAI','FUTANARI','18+','ADULT ANIME',
        'BIBLE BLACK','DISCIPLINE','STRINGENDO',
        'STRINGENDO AND ACCELERANDO','BEAT ANGEL ESCALAYER',
        'GOLDEN BOY','RESORT BOIN',
    ],

    # ── DUBLADO / LEGENDADO ──────────────────────────────────────
    "Dublado":   ['DUBLADO','DUB','PT-BR','PORTUGUESE DUB',
                  'BRAZILIAN DUB','DUBBED','AUDIO PT'],
    "Legendado": ['LEGENDADO','LEG','PT-PT','SUBTITLED',
                  'LEGENDAS','LEGENDA','SUB PT','SUB PORTUGUES'],
}

# ─────────────────────────────────────────────────────────────────
# Group-titles genéricos (sem info útil de categoria)
# ─────────────────────────────────────────────────────────────────

GT_GENERICOS = {
    'animes vod','anime','animes','vod','series','séries',
    'filmes','movies','geral','others','outros','general',
    'misc','uncategorized','all','todo','todos','',
}


def detectar_categoria_anime(nome: str, group_title: str = "") -> str:
    """
    Detecta a categoria do anime pelo nome e/ou group-title.
    Usa word-boundary para evitar falsos positivos por substring.
    Ex: 'MAR' não captura 'uMARu'; 'MONONOKE' não captura títulos errados.
    """
    if group_title and group_title.strip().lower() not in GT_GENERICOS:
        texto = (group_title + " " + nome).upper()
    else:
        texto = nome.upper()

    # Normaliza hífens/underlines → espaço; padding para word-boundary
    texto = re.sub(r'[-_]', ' ', texto)
    texto = f" {texto} "

    for cat, keywords in CATEGORIAS_ANIME.items():
        for kw in keywords:
            kw_norm = re.sub(r'[-_]', ' ', kw)
            if re.search(r'(?<!\w)' + re.escape(kw_norm) + r'(?!\w)', texto):
                return cat
    return "Geral"

# ─────────────────────────────────────────────────────────────────
# CLASSIFICAÇÃO GERAL
# ─────────────────────────────────────────────────────────────────

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

    print(f"\n📦 Total bruto: {len(acervo)} entradas")

    # 5. Validação separada por tipo
    validos = separar_e_validar(acervo)

    # 6. Geração
    print("\n📝 Gerando playlist classificada...")
    gerar_m3u(validos)