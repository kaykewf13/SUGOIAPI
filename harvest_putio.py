"""
SUGOIAPI - harvest_putio.py
Fase B do pipeline Put.io.

Modo dual:
  1. Harvest do state (transfers ainda no fluxo pending->ready)
  2. Full scan: varre TODA a pasta do Put.io para incluir arquivos
     baixados fora do pipeline ou orfaos no state.
"""

import os
from putio_integration import PutioOrchestrator


def main():
    print("=" * 50)
    print("  SUGOIAPI - Put.io Harvester")
    print("=" * 50 + "\n")

    orch = PutioOrchestrator()

    # 1. Harvest do state (transfers pendentes -> ready)
    items = orch.state.get("items", {})
    pending = sum(1 for i in items.values() if i.get("status") == "pending")
    ready   = sum(1 for i in items.values() if i.get("status") == "ready")
    error   = sum(1 for i in items.values() if i.get("status") == "error")

    print(f"Estado atual do state.json:")
    print(f"   Pending : {pending}")
    print(f"   Ready   : {ready}")
    print(f"   Error   : {error}\n")

    if pending > 0:
        print(f"Verificando {pending} transfers pendentes...\n")
        novos = orch.harvest()
        print(f"\n   {len(novos)} novos transfers prontos\n")

    # 2. Full scan: varre TODA a pasta raiz do Put.io
    # Inclui arquivos baixados fora do pipeline ou perdidos no state
    print("Iniciando full scan recursivo do Put.io...\n")
    orch.full_scan_export()


if __name__ == "__main__":
    main()