"""
sanitize_putio.py
-----------------
Reescreve URLs do Put.io na playlist, trocando o token exposto pela
URL do Worker proxy. Roda como passo final do pipeline do SUGOIAPI,
antes de commitar o playlist_validada.m3u.

Antes:  https://api.put.io/v2/files/1585191887/stream?oauth_token=XXXX
Depois: https://sugoiapi-putio-proxy.viraltechh.workers.dev/?id=1585191887
"""

import re

# URL do Worker já publicado (ajuste se usar domínio custom)
WORKER_URL = "https://sugoiapi-putio-proxy.viraltechh.workers.dev"

# Captura o file ID de qualquer URL de stream do Put.io, com ou sem token
PUTIO_RE = re.compile(
    r"https?://api\.put\.io/v2/files/(\d+)/stream(?:\?oauth_token=[A-Za-z0-9]+)?"
)


def sanitizar_linha(linha: str) -> str:
    """Substitui URL do Put.io pela URL do Worker (sem token)."""
    return PUTIO_RE.sub(lambda m: f"{WORKER_URL}/?id={m.group(1)}", linha)


def sanitizar_playlist(caminho: str) -> int:
    """
    Reescreve o arquivo no lugar. Retorna quantas URLs foram sanitizadas.
    """
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
