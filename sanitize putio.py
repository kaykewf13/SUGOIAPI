import re

WORKER_URL = "https://sugoiapi-putio-proxy.viraltechh.workers.dev"

PUTIO_RE = re.compile(
    r"https?://api\.put\.io/v2/files/(\d+)/stream(?:\?oauth_token=[A-Za-z0-9]+)?"
)


def sanitizar_linha(linha: str) -> str:
    return PUTIO_RE.sub(lambda m: f"{WORKER_URL}/?id={m.group(1)}", linha)


def sanitizar_playlist(caminho: str) -> int:
    with open(caminho, "r", encoding="utf-8") as f:
        conteudo = f.read()

    ocorrencias = len(PUTIO_RE.findall(conteudo))
    novo = PUTIO_RE.sub(lambda m: f"{WORKER_URL}/?id={m.group(1)}", conteudo)

    with open(caminho, "w", encoding="utf-8") as f:
        f.write(novo)

    return ocorrencias


if __name__ == "__main__":
    import sys
    alvo = sys.argv[1] if len(sys.argv) > 1 else "output/playlist_validada.m3u"
    n = sanitizar_playlist(alvo)
    print(f"[sanitize] {n} URLs do Put.io protegidas via Worker em {alvo}")
