"""
SUGOIAPI — enqueue_putio.py
Fase A do pipeline Put.io.

Coleta magnets do Nyaa.si e Sukebei (adulto), classifica por categoria
e envia para o Put.io.
"""

from nyaa_scraper import buscar_animes_por_categoria
from putio_integration import PutioOrchestrator


def main():
    print("╔═══════════════════════════════════════════╗")
    print("║  SUGOIAPI — Nyaa → Put.io Enqueuer        ║")
    print("╚═══════════════════════════════════════════╝\n")

    # 1. Buscar magnets classificados por categoria
    items = buscar_animes_por_categoria(
        incluir_adulto=True,   # Sukebei (Hentai, Milf, Netorare)
        max_sfw=10,            # até 10 torrents por anime SFW
        max_adult=5,           # até 5 torrents por busca adulta
    )

    if not items:
        print("⚠️  Nenhum magnet coletado — abortando")
        return

    # 2. Enviar para Put.io
    print("\n📡 Enviando para Put.io...\n")
    orch = PutioOrchestrator()
    novos = orch.enqueue(items)

    print(f"\n{'─'*48}")
    print(f"  Coletados do Nyaa : {len(items)}")
    print(f"  Novos no Put.io   : {novos}")
    print(f"  Já existentes     : {len(items) - novos}")
    print(f"{'─'*48}\n")


if __name__ == "__main__":
    main()