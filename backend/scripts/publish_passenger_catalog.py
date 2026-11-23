"""Publica um catálogo revisado SOMENTE no emulador; sem credenciais de produção.

Uso: python scripts/publish_passenger_catalog.py caminho/catalogo.json
Não usa exports de contas, não altera documentos privados nem remove itens.
Para retirar uma linha, remova-a com uma ferramenta administrativa separada.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "functions"))
from passenger import validate_catalog, catalog_document
from emulator_rtdb import emulator_firestore_client


def main():
    """Valida todo o arquivo antes de gravar, com lote atômico limitado a 500 itens."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--project", default="loirinha-1a25f")
    args = parser.parse_args()
    catalog = validate_catalog(json.loads(args.catalog.read_text(encoding="utf-8")))
    if sum(map(len, catalog.values())) > 500:
        raise ValueError("Publicação limitada a 500 documentos por lote")
    db = emulator_firestore_client(args.project)
    # Só publica identificadores de veículos existentes; não cria uma frota fictícia.
    for bus in catalog["buses"]:
        if not db.collection("buses").document(bus["id"]).get().exists:
            raise ValueError(f"Ônibus inexistente: {bus['id']}")
    batch = db.batch()
    for group, name in {
        "lines": "public_lines",
        "stops": "public_stops",
        "buses": "public_buses",
        "notices": "public_notices",
    }.items():
        for item in catalog[group]:
            identifier = item["id"]
            batch.set(db.collection(name).document(identifier), catalog_document(item))
    batch.commit()
    print("Catálogo validado e publicado no emulador.")


if __name__ == "__main__":
    main()
