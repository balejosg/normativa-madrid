"""Genera la tabla de equivalencias entre los códigos antiguos de Primaria y los del formato común.

Lee la referencia congelada (``tests/referencia/primaria-madrid-bd89f26.json``) y aplica
:func:`extraer_primaria.codigo_nuevo` a cada criterio, competencia (también con su equivalente
del real decreto, ``CMNSC.CE1``). Escribe ``datos/equivalencias-primaria-2026.json``, que
``comprobar`` lee para sugerir el código nuevo. Los descriptores no entran: su código antiguo
(``CCL1``) no se distingue de una sigla corriente.

    python -m herramientas.normativa.equivalencias_primaria
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .extraer_primaria import codigo_nuevo

__all__ = ["equivalencias", "main"]

RAIZ = Path(__file__).parents[2]
REFERENCIA = RAIZ / "tests" / "referencia" / "primaria-madrid-bd89f26.json"
DESTINO = RAIZ / "src" / "normativa_madrid" / "datos" / "equivalencias-primaria-2026.json"


def equivalencias(referencia: dict) -> dict[str, str]:
    """Código antiguo -> código nuevo, ordenado por código antiguo."""
    tabla: dict[str, str] = {}
    for area in referencia["areas"]:
        for criterio in area["criterios"]:
            tabla[criterio["codigo"]] = codigo_nuevo(criterio["codigo"])
        for competencia in area["competencias"]:
            nuevo = codigo_nuevo(competencia["codigo"])
            tabla[competencia["codigo"]] = nuevo
            if competencia.get("equivalencia_rd"):
                tabla[competencia["equivalencia_rd"]] = nuevo
    return dict(sorted(tabla.items()))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--referencia", type=Path, default=REFERENCIA)
    ap.add_argument("--salida", type=Path, default=DESTINO)
    args = ap.parse_args(argv)
    referencia = json.loads(args.referencia.read_text(encoding="utf-8"))
    documento = {"equivalencias": equivalencias(referencia)}
    args.salida.write_text(
        json.dumps(documento, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
