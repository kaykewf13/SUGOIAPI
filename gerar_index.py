import re
import json
from datetime import datetime, timezone

WORKER_RE = re.compile(r"workers\.dev/\?id=(\d+)")
NAME_RE = re.compile(r'tvg-name="([^"]*)"')
GROUP_RE = re.compile(r'group-title="([^"]*)"')


def _limpar_nome(nome: str) -> str:
    nome = re.sub(r"\.(mkv|mp4|avi)$", "", nome, flags=re.IGNORECASE)
    return nome.strip()


def parse_playlist(caminho: str) -> dict:
    with open(caminho, "r", encoding="utf-8") as f:
        linhas = f.readlines()

    itens = []
    nome_atual = None
    grupo_atual = None
    vistos = set()

    for linha in linhas:
        linha = linha.strip()

        if linha.startswith("#EXTINF"):
            mn = NAME_RE.search(linha)
            mg = GROUP_RE.search(linha)
            nome_atual = mn.group(1).strip() if mn else None
            grupo_atual = mg.group(1).strip() if mg else ""
            continue

        m_id = WORKER_RE.search(linha)
        if not m_id or not nome_atual:
            nome_atual = None
            continue

        file_id = m_id.group(1)
        if file_id not in vistos:
            vistos.add(file_id)
            itens.append({
                "nome": _limpar_nome(nome_atual),
                "id": file_id,
                "grupo": grupo_atual,
            })
        nome_atual = None

    itens.sort(key=lambda x: x["nome"].lower())

    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "total": len(itens),
        "itens": itens,
    }


if __name__ == "__main__":
    import sys
    alvo = sys.argv[1] if len(sys.argv) > 1 else "output/playlist_validada.m3u"
    saida = sys.argv[2] if len(sys.argv) > 2 else "output/anime_index.json"

    idx = parse_playlist(alvo)

    with open(saida, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

    print(f"[index] {idx['total']} itens jogaveis -> {saida}")
