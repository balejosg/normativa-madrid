"""El paquete no depende de ningún producto ni lo menciona (salvo la línea de origen)."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).parents[1]
# «\btiza» y no «tiza»: «garantiza» o «autoriza» no son el producto.
PROHIBIDAS = re.compile(r"\btiza|moodle|aula virtual|mint docente", re.I)
SUFIJOS = {".py", ".toml", ".md"}
# El texto oficial no se altera: ni los datos ni los extractos del boletín se escanean.
EXCLUIDAS = (
    RAIZ / "src" / "normativa_madrid" / "datos",
    RAIZ / "herramientas" / "normativa" / "fuentes",
)
ESTE = Path(__file__).resolve()


def _ficheros():
    for carpeta in ("src", "herramientas", "tests", "docs", "skill"):
        for ruta in (RAIZ / carpeta).rglob("*"):
            if "__pycache__" in ruta.parts or ruta.suffix not in SUFIJOS or not ruta.is_file():
                continue
            if ruta.resolve() == ESTE or any(e in ruta.parents for e in EXCLUIDAS):
                continue
            yield ruta
    for nombre in ("README.md", "CHANGELOG.md", "AGENTS.md", "pyproject.toml"):
        if (RAIZ / nombre).is_file():
            yield RAIZ / nombre


def test_independencia():
    fallos = []
    for ruta in _ficheros():
        for n, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if linea.startswith("Origen:"):
                continue
            if PROHIBIDAS.search(linea):
                fallos.append(f"{ruta.relative_to(RAIZ)}:{n}: {linea.strip()}")
    assert not fallos, "\n".join(fallos)


def test_sin_dependencias_de_ejecucion():
    import tomllib

    proyecto = tomllib.loads((RAIZ / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert proyecto["dependencies"] == []
