"""
SUGOIAPI - termos_categorias.py
Listas curadas de animes por categoria para busca no Nyaa.si

Cada categoria tem seus titulos conhecidos. O scraper busca cada um,
coleta o magnet e classifica pela categoria de origem.

Para conteudo adulto, usa o sukebei.nyaa.si (mirror adulto).
"""

# ----------------------------------------------------------------
# Categorias SFW - buscadas em nyaa.si
# ----------------------------------------------------------------

CATEGORIAS_SFW = {

    "Shounen": [
        "naruto", "naruto shippuden", "boruto",
        "one piece", "dragon ball", "dragon ball z", "dragon ball super",
        "bleach", "bleach thousand year",
        "demon slayer", "kimetsu no yaiba",
        "jujutsu kaisen",
        "my hero academia", "boku no hero",
        "attack on titan", "shingeki no kyojin",
        "black clover", "fire force", "soul eater",
        "blue exorcist", "fairy tail",
        "hunter x hunter", "fullmetal alchemist",
        "haikyuu", "kuroko no basket",
        "yu yu hakusho", "rurouni kenshin",
        "chainsaw man", "spy x family",
        "dr stone", "doctor stone",
        "mashle", "dandadan", "wind breaker",
        "blue lock", "undead unluck",
    ],

    "Ecchi e Harem": [
        "highschool dxd", "high school dxd",
        "monster musume", "to love ru", "to love-ru",
        "rosario vampire", "rosario+vampire",
        "sekirei", "freezing",
        "queens blade", "shimoneta",
        "shinmai maou no testament", "testament of sister new devil",
        "infinite stratos", "yuragi-sou",
        "interspecies reviewers", "ishuzoku reviewers",
        "worlds end harem", "shuumatsu no harem",
        "how not to summon a demon lord", "isekai maou",
        "rakudai kishi", "asterisk war",
        "absolute duo", "antimagic academy",
        "trinity seven", "date a live",
        "highschool of the dead",
        "kiss x sis", "yosuga no sora",
        "okusama ga seitokaichou",
        "peter grill",
        "redo of healer", "kaifuku jutsushi",
        "valkyrie drive",
        "kanokon", "ladies versus butlers",
        "manyuu hikenchou", "sin nanatsu no taizai",
        "qwaser of stigmata", "seikon no qwaser",
        "tsugumomo", "ane naru mono",
        "harem in the labyrinth", "isekai meikyuu",
        "campione", "demon king daimao",
        "maou-sama retry", "demon lord retry",
        "my wife is the student council president",
        "ladies vs butlers",
        "majikoi", "maji de watashi ni koishinasai",
        "love hina",
    ],

    "Suspense": [
        "death note", "monster",
        "psycho pass", "tokyo ghoul",
        "promised neverland", "yakusoku no neverland",
        "mirai nikki", "future diary",
        "another", "higurashi",
        "shiki", "parasyte", "kiseijuu",
        "deadman wonderland",
        "talentless nana",
        "id invaded", "wonder egg priority",
        "moriarty the patriot", "yuukoku no moriarty",
        "babylon", "boogiepop",
        "terror in resonance", "zankyou no terror",
        "darwins game", "btoom",
    ],

    "Luta": [
        "baki", "baki the grappler", "baki hanma",
        "kengan ashura", "kengan omega",
        "hajime no ippo",
        "megalo box", "ashita no joe",
        "rurouni kenshin",
        "samurai champloo", "afro samurai",
        "sword of the stranger",
        "shigurui",
        "tenjho tenge", "ikki tousen",
        "historys strongest disciple",
        "record of ragnarok",
        "fire force", "garo",
        "berserk",
    ],

    "Guerra": [
        "attack on titan", "shingeki no kyojin",
        "vinland saga",
        "code geass",
        "gundam", "mobile suit gundam",
        "86 eighty six",
        "violet evergarden",
        "fullmetal alchemist brotherhood",
        "saga of tanya the evil", "youjo senki",
        "kingdom",
        "drifters",
        "altair", "shoukoku no altair",
        "izetta the last witch",
        "valkyria chronicles",
        "girls und panzer",
        "black bullet", "aldnoah zero",
        "darling in the franxx",
    ],

    "Isekai": [
        "sword art online", "sao",
        "re zero", "re:zero",
        "overlord",
        "tensei shitara slime", "that time i got reincarnated as a slime",
        "log horizon", "no game no life",
        "konosuba",
        "shield hero", "rising of the shield hero",
        "mushoku tensei",
        "danmachi",
        "arifureta",
        "ascendance of a bookworm", "honzuki no gekokujou",
        "by the grace of the gods", "kamitachi ni hirowareta otoko",
        "in another world with my smartphone",
        "isekai cheat magician",
        "death march to the parallel world",
        "uncle from another world", "isekai ojisan",
        "ive been killing slimes",
        "skeleton knight in another world",
        "reincarnated as a sword", "tensei shitara ken",
    ],

    "Comedia": [
        "gintama", "konosuba",
        "grand blue", "saiki kusuo",
        "one punch man", "saitama",
        "asobi asobase", "nichijou",
        "lucky star", "azumanga daioh",
        "hinamatsuri",
        "great teacher onizuka", "gto",
        "prison school",
        "daily lives of high school boys", "danshi koukousei",
        "kaguya sama", "kaguya-sama",
        "horimiya",
        "monthly girls nozaki kun", "gekkan shoujo nozaki",
        "miss kobayashi", "kobayashi san",
        "gabriel dropout",
        "interview with monster girls", "demi chan",
        "kaichou wa maid sama",
        "ouran high school host club",
    ],
}

# ----------------------------------------------------------------
# Categorias adultas - buscadas em sukebei.nyaa.si
# ----------------------------------------------------------------

CATEGORIAS_ADULT = {

    "Hentai": [
        "bible black", "discipline",
        "stringendo", "beat angel escalayer",
        "resort boin", "boin lecture",
        "kanojo x kanojo x kanojo",
        "starless", "swing out sisters",
        "viper gts", "kuroinu",
        "taimanin", "taimanin asagi", "taimanin yukikaze",
        "youkoso sukebe elf",
        "mahou shoujo elena",
        "rance",
        "imouto",
        "oni chichi", "oni-chichi",
        "ane yome", "yome onna",
        "mankitsu happening",
        "euphoria",
        "tsumamigui",
        "pure mail", "pretty x cation",
        "shoujo ramune",
        "kuroinu kedakaki seijo",
        "princess limited",
        "saimin gakuen",
        "saimin kishi",
        "yokujou bazooka",
        "kowaremono",
        "tropical kiss",
        "akiba girls",
        "behind moon",
        "schoolgirl special",
        "yarima", "yariman",
        "succubus", "lilith",
        "elfen lied hentai",
        "queen bee",
        "milky animation label",
        "pink pineapple",
        "teaching feeling",
        "sansha mendan",
    ],

    "Milf": [
        "oyakodon", "tsuma",
        "hitozuma", "okusan",
        "milf hentai",
        "okaa-san", "okaasan",
        "mama hentai",
        "yarichin",
        "tsuma netori",
        "anejiru", "ane jiru",
        "tsumamigui",
        "oyako rankan",
        "kaa-chan", "kaachan",
        "haha sange",
        "boku no yayoi-san",
        "mama mama mama",
        "sansha mendan",
        "ano hi no kanojo",
        "shusaku replay",
        "mama no umi",
        "muma no machi cornelica",
    ],

    "Netorare": [
        "netorare", "ntr",
        "shoujo ramune",
        "tsumamigui",
        "swapping",
        "kanojo ga mimai",
        "saimin",
        "wife hentai",
        "yariman",
        "kanojo wa dare to demo",
        "boku no yayoi",
        "kanojo x kanojo",
        "shusaku",
        "wife eater",
        "hitozuma life",
        "anata no shiranai kango fu",
        "ntr legend",
        "hitozuma kasumi",
        "hitomi sensei",
        "kakushi dere",
        "kanojo wa dochira to tsukiau",
        "oni chichi rebuild",
        "imouto bitch",
    ],
}


# ----------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------

def termos_sfw_com_uploader(uploader: str = "subsplease") -> list:
    """
    Retorna lista de tuplas (query, categoria) para busca no nyaa.si.
    Ex: [("subsplease naruto", "Shounen"), ...]
    """
    out = []
    for cat, animes in CATEGORIAS_SFW.items():
        for anime in animes:
            out.append((f"{uploader} {anime}", cat))
    return out


def termos_adult() -> list:
    """
    Retorna lista de tuplas (query, categoria) para sukebei.nyaa.si.
    """
    out = []
    for cat, titulos in CATEGORIAS_ADULT.items():
        for titulo in titulos:
            out.append((titulo, cat))
    return out


def total_termos() -> dict:
    """Retorna contagem de termos por categoria."""
    counts = {}
    for cat, animes in CATEGORIAS_SFW.items():
        counts[cat] = len(animes)
    for cat, titulos in CATEGORIAS_ADULT.items():
        counts[cat] = len(titulos)
    return counts


if __name__ == "__main__":
    counts = total_termos()
    print("Cobertura por categoria:\n")
    total = 0
    for cat, n in counts.items():
        total += n
        print(f"   {cat:<22} {n:>4} termos")
    print(f"\n   TOTAL                 {total:>4} termos")