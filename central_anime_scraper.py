"""
SUGOIAPI — central_animes_scraper.py
Varre o catálogo completo de centraldeanimes.xyz e gera sources/central_animes.m3u

Proteções contra Cloudflare:
- cloudscraper (bypass automático de JS challenge)
- Delay aleatório entre requisições
- Rotação de User-Agent
- Referer: https://centraldeanimes.xyz em todas as requisições
- Retry com backoff exponencial

URL HLS confirmada:
  https://p1.animescomix.com/hls/animes/{letra}/{slug}/{ep}.mp4/index.m3u8
"""

import re
import os
import time
import random
import cloudscraper
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ─── Configurações ────────────────────────────────────────────────────────────

BASE_SITE    = "https://centraldeanimes.xyz"
CDN_BASE     = "https://p1.animescomix.com/hls/animes"
OUTPUT_FILE  = "sources/central_animes.m3u"

HEADERS = {
    "Referer"         : "https://centraldeanimes.xyz",
    "Origin"          : "https://centraldeanimes.xyz",
    "Accept-Language" : "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept"          : "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

DELAY_MIN    = 0.4   # segundos mínimo entre requests
DELAY_MAX    = 1.2   # segundos máximo entre requests
MAX_EP       = 200   # teto de episódios por anime
WORKERS      = 4     # paralelo por anime (baixo para não disparar Cloudflare)
RETRY_MAX    = 3     # tentativas por request

# ─── Scraper com bypass Cloudflare ───────────────────────────────────────────

def new_scraper() -> cloudscraper.CloudScraper:
    """Cria instância com User-Agent aleatório."""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    scraper.headers.update(HEADERS)
    scraper.headers.update({"User-Agent": random.choice(USER_AGENTS)})
    return scraper


def get_with_retry(scraper, url: str, timeout: int = 15) -> tuple:
    """
    Faz GET com retry e backoff. Retorna (status_code, text).
    Troca User-Agent a cada retry.
    """
    for attempt in range(RETRY_MAX):
        try:
            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            scraper.headers.update({"User-Agent": random.choice(USER_AGENTS)})
            res = scraper.get(url, timeout=timeout, allow_redirects=True)
            return res.status_code, res.text
        except Exception as e:
            wait = (attempt + 1) * 2
            print(f"  ⚠️  {url[:60]} — tentativa {attempt+1} falhou: {e} → aguardando {wait}s")
            time.sleep(wait)
    return 0, ""


def head_with_retry(scraper, url: str) -> int:
    """HEAD request para validar link HLS. Retorna status_code."""
    for attempt in range(RETRY_MAX):
        try:
            time.sleep(random.uniform(0.2, 0.5))
            scraper.headers.update({"User-Agent": random.choice(USER_AGENTS)})
            res = scraper.head(url, timeout=10, allow_redirects=True)
            if res.status_code == 405:
                res = scraper.get(url, timeout=10, stream=True)
                res.close()
            return res.status_code
        except Exception:
            time.sleep((attempt + 1) * 1.5)
    return 0

# ─── Descoberta do catálogo ───────────────────────────────────────────────────

# Padrões de slug em diferentes estruturas de sites de anime PT-BR
RE_SLUG = re.compile(
    r'href=["\'](?:https?://centraldeanimes\.xyz)?/(?:anime|animes)/([a-z0-9][a-z0-9\-]+)["\'/]',
    re.IGNORECASE
)

def fetch_slugs_page(scraper, page: int) -> tuple:
    """
    Busca slugs de uma página do listing.
    Retorna (slugs, has_next).
    Tenta múltiplos padrões de URL.
    """
    urls_to_try = [
        f"{BASE_SITE}/animes?page={page}",
        f"{BASE_SITE}/animes/page/{page}",
        f"{BASE_SITE}/anime?page={page}",
        f"{BASE_SITE}/anime/page/{page}",
    ]

    for url in urls_to_try:
        status, html = get_with_retry(scraper, url)
        if status == 200 and html:
            slugs = list(dict.fromkeys(RE_SLUG.findall(html)))  # dedupe mantendo ordem

            # Detecta próxima página
            has_next = bool(
                re.search(r'page[=/]' + str(page + 1), html) or
                re.search(r'rel=["\']next["\']', html) or
                re.search(r'class=["\'][^"\']*next[^"\']*["\']', html)
            )
            return slugs, has_next

    return [], False


def crawl_catalog(scraper) -> list:
    """Varre todas as páginas e retorna lista de slugs únicos."""
    print("📚 Varrendo catálogo de centraldeanimes.xyz...")

    # Primeiro tenta descobrir a estrutura da listagem
    status, html = get_with_retry(scraper, BASE_SITE)
    if status != 200:
        print(f"  ❌ Site inacessível (status {status})")
        return []

    all_slugs = []
    seen      = set()
    page      = 1
    max_pages = 500  # segurança

    while page <= max_pages:
        slugs, has_next = fetch_slugs_page(scraper, page)

        added = 0
        for s in slugs:
            if s not in seen and len(s) > 2:
                seen.add(s)
                all_slugs.append(s)
                added += 1

        print(f"  Página {page:>3} → {added:>3} novos slugs (total: {len(all_slugs)})")

        if not has_next or added == 0:
            print(f"  ✅ Catálogo completo — {page} páginas, {len(all_slugs)} animes\n")
            break

        page += 1
        time.sleep(random.uniform(0.5, 1.0))

    return all_slugs


# ─── Resolução de episódios ───────────────────────────────────────────────────

def slug_to_name(slug: str) -> str:
    """'naruto-shippuden' → 'Naruto Shippuden'"""
    return " ".join(w.capitalize() for w in slug.split("-"))


def letra_inicial(slug: str) -> str:
    """Retorna a letra inicial para montar o path do CDN."""
    c = slug[0].lower()
    return c if c.isalpha() else "0"


def build_hls_url(slug: str, ep: int) -> str:
    letra = letra_inicial(slug)
    return f"{CDN_BASE}/{letra}/{slug}/{ep:02d}.mp4/index.m3u8"


def fetch_logo(scraper, slug: str) -> str:
    """Tenta extrair a URL da capa do anime na página do site."""
    url = f"{BASE_SITE}/animes/{slug}"
    status, html = get_with_retry(scraper, url)
    if status != 200:
        url = f"{BASE_SITE}/anime/{slug}"
        status, html = get_with_retry(scraper, url)
    if status != 200 or not html:
        return ""

    # Tenta og:image primeiro
    m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html)
    if not m:
        m = re.search(r'content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\']', html)
    if not m:
        # Fallback: primeira img com "poster" ou "capa" no src
        m = re.search(r'<img[^>]+src=["\']([^"\']*(?:poster|capa|cover|thumb)[^"\']*)["\']', html, re.IGNORECASE)
    return m.group(1).strip() if m else ""


def process_anime(slug: str) -> list:
    """
    Para um slug, itera episódios até receber 404.
    Retorna lista de dicts com os dados de cada episódio.
    """
    scraper = new_scraper()
    nome    = slug_to_name(slug)
    logo    = fetch_logo(scraper, slug)
    entries = []

    for ep in range(1, MAX_EP + 1):
        url    = build_hls_url(slug, ep)
        status = head_with_retry(scraper, url)

        if status == 200 or status == 206:
            entries.append({
                "nome"    : nome,
                "slug"    : slug,
                "logo"    : logo,
                "ep"      : ep,
                "ep_label": f"{nome} - EP{ep:02d}",
                "url"     : url,
            })
        elif status == 404 or status == 0:
            # Fim dos episódios deste anime
            break
        else:
            # 403, 429, 5xx — tenta mais uma vez após pausa longa
            print(f"  ⚠️  {nome} EP{ep:02d} status={status} — aguardando 3s")
            time.sleep(3)
            status2 = head_with_retry(scraper, url)
            if status2 == 200:
                entries.append({
                    "nome"    : nome,
                    "slug"    : slug,
                    "logo"    : logo,
                    "ep"      : ep,
                    "ep_label": f"{nome} - EP{ep:02d}",
                    "url"     : url,
                })
            else:
                break

    return entries


# ─── Escrita da M3U ───────────────────────────────────────────────────────────

def write_m3u(all_entries: list):
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n\n")
        for e in all_entries:
            f.write(
                f'#EXTINF:-1 tvg-name="{e["ep_label"]}" '
                f'tvg-logo="{e["logo"]}" '
                f'group-title="{e["nome"]}",{e["ep_label"]}\n'
                f'{e["url"]}\n\n'
            )

    print(f"\n  ✅ {OUTPUT_FILE} — {len(all_entries)} entradas")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import time as _time
    start = _time.time()

    print("╔══════════════════════════════════════════╗")
    print("║  SUGOIAPI — Central Animes Scraper       ║")
    print("╚══════════════════════════════════════════╝\n")

    # 1. Descobre catálogo
    main_scraper = new_scraper()
    slugs = crawl_catalog(main_scraper)

    if not slugs:
        print("❌ Nenhum slug encontrado — abortando")
        exit(1)

    print(f"⚡ Processando {len(slugs)} animes com {WORKERS} workers...\n")

    # 2. Processa episódios em paralelo
    all_entries = []
    done        = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futuros = {ex.submit(process_anime, slug): slug for slug in slugs}
        for f in as_completed(futuros):
            slug    = futuros[f]
            entries = f.result()
            done   += 1

            if entries:
                all_entries.extend(entries)
                print(f"  [{done:>4}/{len(slugs)}] {slug_to_name(slug):<35} {len(entries):>3} eps")
            else:
                print(f"  [{done:>4}/{len(slugs)}] {slug_to_name(slug):<35}   0 eps (sem acesso)")

    # 3. Grava M3U
    write_m3u(all_entries)

    elapsed = round(_time.time() - start)
    print(f"\n{'─'*46}")
    print(f"  Animes processados : {len(slugs)}")
    print(f"  Entradas na M3U    : {len(all_entries)}")
    print(f"  Tempo total        : {elapsed//60}min {elapsed%60}s")
    print(f"{'─'*46}\n")