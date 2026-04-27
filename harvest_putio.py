#!/usr/bin/env python3
"""
harvest_putio.py — Fase B do pipeline SUGOIAPI ↔ Put.io.

Roda no GitHub Actions após exportar_links_api_v3.py ter feito o enqueue.
Atualiza putio_state.json com os transfers concluídos e gera/atualiza
um arquivo de playlist com as entradas Put.io.

Saída:
  - putio_state.json (atualizado in place)
  - putio_entries.m3u (playlist parcial só com entradas Put.io)

O arquivo putio_entries.m3u é um *fragmento* — você decide se mescla
com playlist_premium.m3u no script principal ou consome separadamente.
"""

from __future__ import annotations

import sys
from pathlib import Path

from putio_integration import PutioOrchestrator


STATE_PATH = "putio_state.json"
M3U_FRAGMENT_PATH = "putio_entries.m3u"


def main() -> int:
    orch = PutioOrchestrator(state_path=STATE_PATH)

    novos = orch.harvest()
    print(f"[harvest] novos transfers concluídos: {len(novos)}")
    for n in novos:
        print(f"  + {n['title']}  →  {n['stream_url'][:60]}...")

    lines = orch.export_m3u_lines()
    header = "#EXTM3U"
    Path(M3U_FRAGMENT_PATH).write_text(
        "\n".join([header, *lines]) + "\n",
        encoding="utf-8",
    )
    print(f"[harvest] {len(lines) // 2} entradas escritas em {M3U_FRAGMENT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
