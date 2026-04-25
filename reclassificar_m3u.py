"""
reclassificar_m3u.py
--------------------
Lê um arquivo .m3u, detecta entradas adultas por keywords
e corrige o group-title automaticamente.

Uso:
    python reclassificar_m3u.py input.m3u output.m3u
"""

import re
import sys

# ─── CONFIGURAÇÃO ──────────────────────────────────────────────────────────────

# Palavras-chave que identificam conteúdo adulto (case-insensitive)
# Adicione ou remova conforme necessário
ADULT_KEYWORDS = [
    "rickysroom", "intimatepov", "drewlivexxx", "xxx",
    "brazzers", "bangbros", "realitykings", "mofos",
    "teamskeet", "naughtyamerica", "adult", "porn",
    "sexo", "erotic", "hentai adult",
]

# Grupos que devem ter conteúdo adulto reclassificado
# (só aplica a correção se o item estiver nesses grupos)
GRUPOS_ALVO = [
    "Filmes | Geral",
    "Canais | Variados",
    "Series | Geral",
]

# Grupo de destino para conteúdo adulto detectado
GRUPO_ADULTO = "Filmes | Adulto"

# ───────────────────────────────────────────────────────────────────────────────


def detectar_adulto(linha_extinf: str) -> bool:
    """Retorna True se a linha #EXTINF contém indicadores de conteúdo adulto."""
    linha_lower = linha_extinf.lower()
    return any(kw in linha_lower for kw in ADULT_KEYWORDS)


def reclassificar(linha_extinf: str) -> str:
    """Substitui o group-title por GRUPO_ADULTO se detectado como adulto."""
    grupo_atual = re.search(r'group-title="([^"]*)"', linha_extinf)

    if not grupo_atual:
        return linha_extinf  # sem group-title, não altera

    if grupo_atual.group(1) not in GRUPOS_ALVO:
        return linha_extinf  # grupo fora do escopo, não altera

    if not detectar_adulto(linha_extinf):
        return linha_extinf  # não é adulto, não altera

    # Substitui o group-title
    nova_linha = re.sub(
        r'group-title="[^"]*"',
        f'group-title="{GRUPO_ADULTO}"',
        linha_extinf
    )
    return nova_linha


def processar(caminho_entrada: str, caminho_saida: str):
    with open(caminho_entrada, "r", encoding="utf-8", errors="replace") as f:
        linhas = f.readlines()

    total = 0
    corrigidos = 0
    saida = []

    i = 0
    while i < len(linhas):
        linha = linhas[i]

        if linha.startswith("#EXTINF"):
            total += 1
            nova = reclassificar(linha)
            if nova != linha:
                corrigidos += 1
            saida.append(nova)
        else:
            saida.append(linha)

        i += 1

    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.writelines(saida)

    print(f"✅ Concluído: {corrigidos}/{total} entradas reclassificadas.")
    print(f"📁 Arquivo salvo em: {caminho_saida}")


# ───────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python reclassificar_m3u.py <entrada.m3u> <saida.m3u>")
        sys.exit(1)

    processar(sys.argv[1], sys.argv[2])