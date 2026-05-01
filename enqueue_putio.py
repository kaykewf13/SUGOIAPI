"""
SUGOIAPI — enqueue_putio.py
Fase A do pipeline Put.io.

Coleta magnets do Nyaa.si e envia para o Put.io.
Roda como step do GitHub Actions, antes do harvest.
"""

from nyaa_scraper import buscar_animes_nyaa, TERMOS_PADRAO
from putio_integration import PutioOrchestrator


def main():
    print("╔═══════════════════════════════════════╗")
    print("║  SUGOIAPI — Nyaa → Put.io Enqueuer    ║")
    print("╚═══════════════════════════════════════╝\n")

    # 1. Buscar magnets no Nyaa
    items = buscar_animes_nyaa(TERMOS_PADRAO, qualidade="1080p", max_por_termo=20)

    if not items:
        print("⚠️  Nenhum magnet coletado — abortando")
        return

    # 2. Enviar para Put.io
    print("\n📡 Enviando para Put.io...\n")
    orch = PutioOrchestrator()
    novos = orch.enqueue(items)

    print(f"\n{'─'*46}")
    print(f"  Coletados do Nyaa : {len(items)}")
    print(f"  Novos no Put.io   : {novos}")
    print(f"  Já existentes     : {len(items) - novos}")
    print(f"{'─'*46}\n")


if __name__ == "__main__":
    main()