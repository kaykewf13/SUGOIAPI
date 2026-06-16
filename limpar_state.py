"""
SUGOIAPI — limpar_state.py
Manutencao do sources/putio_state.json.

Resolve dois problemas que travam o pipeline:
  1. Itens em "error" acumulados (peso morto que o harvest reprocessa a toa)
  2. Itens "pending" presos ha muito tempo (transfer que nunca completou)

Modos (via argumento):
  --stats          : so mostra o diagnostico, nao altera nada (padrao)
  --limpar-erros   : remove itens com status "error"
  --retry-presos N : reabre p/ re-enfileirar pendings parados ha mais de N horas
                     (na pratica: remove do state p/ o enqueue achar como "novo")
  --backup         : salva copia antes de alterar (recomendado, automatico)

Uso tipico no GitHub Actions ou local:
  python limpar_state.py --stats
  python limpar_state.py --limpar-erros --backup
"""

from __future__ import annotations
import json
import sys
import shutil
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

STATE_PATH = "sources/putio_state.json"


def carregar(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"FAIL state nao encontrado: {path}")
        sys.exit(1)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL state corrompido: {e}")
        sys.exit(1)


def salvar(path: str, state: dict, backup: bool):
    p = Path(path)
    if backup:
        bkp = p.with_suffix(f".bak-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json")
        shutil.copy(p, bkp)
        print(f"  Backup salvo: {bkp.name}")
    state["last_cleanup"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def stats(state: dict):
    items = state.get("items", {})
    total = len(items)
    por_status = Counter(v.get("status", "?") for v in items.values())
    print(f"\n{'='*48}")
    print(f"  Diagnostico do state ({total} itens)")
    print(f"{'='*48}")
    for st, n in por_status.most_common():
        pct = (n / total * 100) if total else 0
        print(f"  {st:<10} {n:>5}  ({pct:4.1f}%)")
    # Erros mais comuns
    erros = Counter(
        v.get("error", "sem detalhe")[:50]
        for v in items.values() if v.get("status") == "error"
    )
    if erros:
        print(f"\n  Top causas de erro:")
        for msg, n in erros.most_common(5):
            print(f"    {n:>4}x  {msg}")
    print(f"{'='*48}\n")


def limpar_erros(state: dict) -> int:
    items = state.get("items", {})
    antes = len(items)
    state["items"] = {k: v for k, v in items.items() if v.get("status") != "error"}
    removidos = antes - len(state["items"])
    print(f"  Removidos {removidos} itens em erro")
    return removidos


def retry_presos(state: dict, horas: int) -> int:
    """
    Remove do state pendings criados ha mais de `horas`.
    Removidos do state, voltam a ser "novos" para o enqueue tentar de novo.
    """
    items = state.get("items", {})
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    a_remover = []

    for ih, item in items.items():
        if item.get("status") != "pending":
            continue
        criado = item.get("created_at")
        if not criado:
            a_remover.append(ih)  # sem timestamp = antigo, libera
            continue
        try:
            dt = datetime.fromisoformat(criado)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt < limite:
                a_remover.append(ih)
        except ValueError:
            a_remover.append(ih)

    for ih in a_remover:
        del items[ih]

    print(f"  Liberados {len(a_remover)} pendings presos (> {horas}h) para nova tentativa")
    return len(a_remover)


def main():
    args = sys.argv[1:]
    path = STATE_PATH
    backup = "--backup" in args

    state = carregar(path)

    # Sempre mostra stats antes
    stats(state)

    alterou = False

    if "--limpar-erros" in args:
        limpar_erros(state)
        alterou = True

    if "--retry-presos" in args:
        idx = args.index("--retry-presos")
        horas = int(args[idx + 1]) if idx + 1 < len(args) and args[idx + 1].isdigit() else 24
        retry_presos(state, horas)
        alterou = True

    if alterou:
        salvar(path, state, backup)
        print("\n  Estado apos limpeza:")
        stats(state)
    else:
        print("  Modo --stats (somente leitura). Nada alterado.")
        print("  Use --limpar-erros e/ou --retry-presos N para modificar.\n")


if __name__ == "__main__":
    main()
