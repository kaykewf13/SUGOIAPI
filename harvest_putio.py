"""
SUGOIAPI — harvest_putio.py
Fase B do pipeline Put.io.

Verifica todos os transfers pendentes, identifica os que completaram,
gera URLs de streaming e exporta sources/putio_entries.m3u.

Roda como step do GitHub Actions, separado da fase de enqueue.
"""

from putio_integration import PutioOrchestrator


def main():
    print("╔═══════════════════════════════════════╗")
    print("║  SUGOIAPI — Put.io Harvester          ║")
    print("╚═══════════════════════════════════════╝\n")

    orch = PutioOrchestrator()

    # Status atual
    items = orch.state.get("items", {})
    pending = sum(1 for i in items.values() if i.get("status") == "pending")
    ready   = sum(1 for i in items.values() if i.get("status") == "ready")
    error   = sum(1 for i in items.values() if i.get("status") == "error")

    print(f"📊 Estado atual:")
    print(f"   Pending : {pending}")
    print(f"   Ready   : {ready}")
    print(f"   Error   : {error}\n")

    if pending == 0:
        print("ℹ️  Nenhum transfer pendente para verificar.")
    else:
        print(f"⚡ Verificando {pending} transfers no Put.io...\n")
        novos = orch.harvest()
        print(f"\n   {len(novos)} novos transfers prontos\n")

    # Sempre regenera M3U com todos os ready
    orch.export_m3u()


if __name__ == "__main__":
    main()