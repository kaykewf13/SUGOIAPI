from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

import requests
from openpyxl import Workbook
from openpyxl.styles import Font


BASE_URL = "https://urban-space-guide-pjxvjggw54pwcr6g6-1010.app.github.dev"
TIMEOUT = 30
OUTPUT_DIR = Path("output")


# Aliases manuais opcionais para nomes conhecidos
MANUAL_SLUG_ALIASES: dict[str, list[str]] = {
    "attack on titan": [
        "attack-on-titan",
        "shingeki-no-kyojin",
    ],
    "frieren": [
        "frieren",
        "sousou-no-frieren",
        "frieren-beyond-journeys-end",
    ],
    "sousou no frieren": [
        "sousou-no-frieren",
        "frieren",
        "frieren-beyond-journeys-end",
    ],
    "demon slayer": [
        "demon-slayer",
        "kimetsu-no-yaiba",
    ],
    "my hero academia": [
        "my-hero-academia",
        "boku-no-hero-academia",
    ],
    "one piece": [
        "one-piece",
    ],
    "naruto": [
        "naruto",
    ],
}


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def gerar_variacoes_slug(anime_name: str) -> list[str]:
    """
    Gera variações comuns de slug para aumentar a chance de sucesso.
    """
    original = anime_name.strip()
    normalized = normalize_name(anime_name)
    base_slug = slugify(original)

    variacoes: list[str] = []

    # principal
    variacoes.append(base_slug)

    # com underscore
    variacoes.append(base_slug.replace("-", "_"))

    # com espaço
    variacoes.append(base_slug.replace("-", " "))

    # só palavras principais longas
    palavras = [p for p in re.split(r"[\s\-_:]+", normalized) if p]
    if palavras:
        variacoes.append("-".join(palavras))

    # remove artigos comuns
    stopwords = {"the", "no", "of", "to", "wa", "ga"}
    palavras_filtradas = [p for p in palavras if p not in stopwords]
    if palavras_filtradas:
        variacoes.append("-".join(palavras_filtradas))

    # última parte ou última dupla de palavras
    if len(palavras) >= 1:
        variacoes.append(palavras[-1])
    if len(palavras) >= 2:
        variacoes.append("-".join(palavras[-2:]))

    # aliases manuais
    if normalized in MANUAL_SLUG_ALIASES:
        variacoes.extend(MANUAL_SLUG_ALIASES[normalized])

    # remove duplicados preservando ordem
    unicos: list[str] = []
    seen = set()

    for v in variacoes:
        v = v.strip()
        if not v:
            continue
        if v not in seen:
            seen.add(v)
            unicos.append(v)

    return unicos


def consultar_episodio(slug: str, season: int, episode: int) -> Any:
    url = f"{BASE_URL}/episode/{slug}/{season}/{episode}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def normalizar_resultados(
    payload: Any,
    anime_name: str,
    anime_slug_used: str,
    season: int,
    episode: int,
) -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []

    if not isinstance(payload, list):
        return linhas

    for provider_item in payload:
        if not isinstance(provider_item, dict):
            continue

        provider_name = (
            provider_item.get("provider")
            or provider_item.get("name")
            or "desconhecido"
        )
        provider_slug = provider_item.get("slug")
        has_ads = provider_item.get("has_ads")
        is_embed = provider_item.get("is_embed")

        episodes = provider_item.get("episodes", [])
        if not isinstance(episodes, list):
            continue

        for ep in episodes:
            if not isinstance(ep, dict):
                continue

            linhas.append(
                {
                    "anime_name": anime_name,
                    "anime_slug_used": anime_slug_used,
                    "season": season,
                    "episode": episode,
                    "provider_name": provider_name,
                    "provider_slug": provider_slug,
                    "has_ads": has_ads,
                    "is_embed": is_embed,
                    "title": ep.get("title"),
                    "url": ep.get("url"),
                    "error": ep.get("error"),
                }
            )

    return linhas


def linha_valida(linha: dict[str, Any]) -> bool:
    return bool(linha.get("url")) and linha.get("error") is not True


def deduplicar_linhas(linhas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unicas: list[dict[str, Any]] = []
    seen = set()

    for linha in linhas:
        chave = (
            linha.get("anime_name"),
            linha.get("season"),
            linha.get("episode"),
            linha.get("provider_name"),
            linha.get("title"),
            linha.get("url"),
        )
        if chave not in seen:
            seen.add(chave)
            unicas.append(linha)

    return unicas


def exportar_json(linhas: list[dict[str, Any]], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8") as f:
        json.dump(linhas, f, ensure_ascii=False, indent=2)


def exportar_excel(linhas: list[dict[str, Any]], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Links API"

    colunas = [
        "anime_name",
        "anime_slug_used",
        "season",
        "episode",
        "provider_name",
        "provider_slug",
        "has_ads",
        "is_embed",
        "title",
        "url",
        "error",
    ]

    ws.append(colunas)

    for cell in ws[1]:
        cell.font = Font(bold=True)

    for linha in linhas:
        ws.append([linha.get(col) for col in colunas])

    larguras = {
        "A": 28,
        "B": 24,
        "C": 10,
        "D": 10,
        "E": 22,
        "F": 22,
        "G": 10,
        "H": 10,
        "I": 45,
        "J": 90,
        "K": 18,
    }

    for coluna, largura in larguras.items():
        ws.column_dimensions[coluna].width = largura

    wb.save(caminho)


def exportar_m3u_por_anime(linhas: list[dict[str, Any]], pasta_saida: Path) -> None:
    pasta_saida.mkdir(parents=True, exist_ok=True)

    agrupado: dict[str, list[dict[str, Any]]] = {}

    for linha in linhas:
        anime_name = str(linha.get("anime_name") or "anime")
        anime_file = slugify(anime_name)
        agrupado.setdefault(anime_file, []).append(linha)

    for anime_file, itens in agrupado.items():
        caminho = pasta_saida / f"{anime_file}.m3u"

        with caminho.open("w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")

            for linha in itens:
                if not linha_valida(linha):
                    continue

                anime_name = linha.get("anime_name", anime_file)
                season = linha.get("season", 1)
                episode = linha.get("episode", 1)
                provider_name = linha.get("provider_name", "provider")
                title = linha.get("title") or f"{anime_name} S{season}E{episode}"
                url = linha.get("url")

                display_name = f"{title} | {provider_name}"
                group_title = f"Animes API/{slugify(str(anime_name))}"

                f.write(
                    f'#EXTINF:-1 group-title="{group_title}",{display_name}\n'
                )
                f.write(f"{url}\n")


def carregar_consultas_csv(caminho_csv: Path) -> list[dict[str, Any]]:
    consultas: list[dict[str, Any]] = []

    with caminho_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            anime = (row.get("anime") or row.get("name") or "").strip()
            season = row.get("season")
            episode = row.get("episode")

            if not anime or not season or not episode:
                continue

            consultas.append(
                {
                    "anime_name": anime,
                    "season": int(season),
                    "episode": int(episode),
                }
            )

    return consultas


def coletar_consultas_interativas() -> list[dict[str, Any]]:
    consultas: list[dict[str, Any]] = []

    print("Digite os animes para consulta.")
    print("Quando terminar, deixe o nome vazio e pressione Enter.\n")

    while True:
        anime = input("Anime: ").strip()
        if not anime:
            break

        season = input("Temporada: ").strip()
        episode = input("Episódio: ").strip()

        if not season.isdigit() or not episode.isdigit():
            print("Temporada e episódio devem ser números.\n")
            continue

        consultas.append(
            {
                "anime_name": anime,
                "season": int(season),
                "episode": int(episode),
            }
        )
        print("Consulta adicionada.\n")

    return consultas


def executar_consultas(consultas: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base_completa: list[dict[str, Any]] = []
    base_valida: list[dict[str, Any]] = []

    for item in consultas:
        anime_name = item["anime_name"]
        season = item["season"]
        episode = item["episode"]

        variacoes = gerar_variacoes_slug(anime_name)

        print(
            f"\nConsultando anime='{anime_name}' | temporada={season} | episódio={episode}"
        )
        print(f"Variações de slug: {variacoes}")

        encontrou_valido = False

        for slug_variacao in variacoes:
            print(f"  -> tentando slug: {slug_variacao}")

            try:
                payload = consultar_episodio(slug_variacao, season, episode)
                linhas = normalizar_resultados(
                    payload=payload,
                    anime_name=anime_name,
                    anime_slug_used=slug_variacao,
                    season=season,
                    episode=episode,
                )

                if linhas:
                    linhas = deduplicar_linhas(linhas)
                    base_completa.extend(linhas)

                    validas = [l for l in linhas if linha_valida(l)]
                    if validas:
                        base_valida.extend(validas)
                        encontrou_valido = True
                        print(f"     sucesso: {len(validas)} link(s) válido(s)")
                        break
                    else:
                        print("     retorno sem links válidos")
                else:
                    print("     sem resultados")
            except requests.HTTPError as e:
                print(f"     erro HTTP: {e}")
            except requests.RequestException as e:
                print(f"     erro de conexão: {e}")
            except Exception as e:
                print(f"     erro inesperado: {e}")

        if not encontrou_valido:
            base_completa.append(
                {
                    "anime_name": anime_name,
                    "anime_slug_used": None,
                    "season": season,
                    "episode": episode,
                    "provider_name": None,
                    "provider_slug": None,
                    "has_ads": None,
                    "is_embed": None,
                    "title": None,
                    "url": None,
                    "error": "Nenhuma variação retornou link válido",
                }
            )

    base_completa = deduplicar_linhas(base_completa)
    base_valida = deduplicar_linhas(base_valida)

    return base_completa, base_valida


def montar_nome_base(args: argparse.Namespace, total_consultas: int) -> str:
    if args.output_name:
        return slugify(args.output_name)

    if args.anime:
        return slugify(args.anime)

    return f"consulta_{total_consultas}_animes"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consulta a SUGOIAPI com variações de slug e exporta resultados."
    )
    parser.add_argument("--anime", type=str, help="Nome do anime")
    parser.add_argument("--season", type=int, help="Número da temporada")
    parser.add_argument("--episode", type=int, help="Número do episódio")
    parser.add_argument(
        "--csv",
        type=str,
        help="Arquivo CSV com colunas: anime,season,episode",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Modo interativo no terminal",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        help="Nome base dos arquivos de saída",
    )

    args = parser.parse_args()

    consultas: list[dict[str, Any]] = []

    if args.csv:
        consultas = carregar_consultas_csv(Path(args.csv))
    elif args.interactive:
        consultas = coletar_consultas_interativas()
    elif args.anime and args.season and args.episode:
        consultas = [
            {
                "anime_name": args.anime,
                "season": args.season,
                "episode": args.episode,
            }
        ]
    else:
        print(
            "Informe uma das opções:\n"
            "1) --anime 'Naruto' --season 1 --episode 1\n"
            "2) --csv consultas.csv\n"
            "3) --interactive"
        )
        return

    if not consultas:
        print("Nenhuma consulta válida encontrada.")
        return

    nome_base = montar_nome_base(args, len(consultas))

    output_json_all = OUTPUT_DIR / f"{nome_base}_completo.json"
    output_xlsx_all = OUTPUT_DIR / f"{nome_base}_completo.xlsx"

    output_json_valid = OUTPUT_DIR / f"{nome_base}_validos.json"
    output_xlsx_valid = OUTPUT_DIR / f"{nome_base}_validos.xlsx"

    output_m3u_dir = OUTPUT_DIR / f"{nome_base}_m3u_validos"

    base_completa, base_valida = executar_consultas(consultas)

    exportar_json(base_completa, output_json_all)
    exportar_excel(base_completa, output_xlsx_all)

    exportar_json(base_valida, output_json_valid)
    exportar_excel(base_valida, output_xlsx_valid)

    exportar_m3u_por_anime(base_valida, output_m3u_dir)

    print("\nConcluído.")
    print(f"JSON completo: {output_json_all}")
    print(f"Excel completo: {output_xlsx_all}")
    print(f"JSON válidos: {output_json_valid}")
    print(f"Excel válidos: {output_xlsx_valid}")
    print(f"M3U válidos por anime: {output_m3u_dir}")


if __name__ == "__main__":
    main()