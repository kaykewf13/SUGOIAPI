"""
SUGOIAPI — enqueue_putio.py v2
Fase A do pipeline Put.io.

Coleta magnets do Nyaa.si (SFW), ignorando o que JA esta no Put.io
(via putio_state.json), e envia os novos para o Put.io.

A coleta adulta (Sukebei) foi removida do fluxo.
"""

from nyaa_scraper import buscar_animes_por_categoria
from putio_integration import PutioOrchestrator


def main():
    print("==================================================")
    print("  SUGOIAPI - Nyaa to Put.io Enqueuer")
    print("==================================================\n")

    # 1. Carrega o orquestrador (le putio_state.json com o que ja existe)
    orch = PutioOrchestrator()
    hashes_existentes = set(orch.state.get("items", {}).keys())
    print(f"  Estado: {len(hashes_existentes)} itens ja conhecidos no Put.io\n")

    # 2. Coleta magnets NOVOS — a coleta ignora hashes existentes e
    #    puxa o proximo do RSS ate completar a meta por termo.
    items = buscar_animes_por_categoria(
        max_sfw=10,
        hashes_existentes=hashes_existentes,
    )

    if not items:
        print("WARN  Nenhum magnet NOVO coletado — nada a enfileirar")
        return

    # 3. Envia para o Put.io
    print("\n Enviando para Put.io...\n")
    novos = orch.enqueue(items)

    print(f"\n{'-'*48}")
    print(f"  Coletados do Nyaa : {len(items)}")
    print(f"  Novos no Put.io   : {novos}")
    print(f"  Ja existentes     : {len(items) - novos}")
    print(f"{'-'*48}\n")


if __name__ == "__main__":
    main()
