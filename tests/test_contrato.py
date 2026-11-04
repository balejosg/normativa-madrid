"""El contrato para agentes (docs/contrato.md) está al día con el código."""

from __future__ import annotations

import json
import re
import shlex
from pathlib import Path

import pytest

from normativa_madrid import ayuda, cli, salida

RAIZ = Path(__file__).parents[1]
CONTRATO = RAIZ / "docs" / "contrato.md"
FILA = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|", re.M)
EJEMPLO = re.compile(r"<!-- orden: (.+?) -->\s*```json\n(.*?)```", re.S)


def _seccion(texto: str, titulo: str) -> str:
    """El texto de la sección «## <titulo>» hasta la siguiente «## »."""
    m = re.search(rf"^## {re.escape(titulo)}\s*$(.*?)(?=^## |\Z)", texto, re.M | re.S)
    assert m, f"falta la sección «{titulo}» en docs/contrato.md"
    return m.group(1)


def test_contrato_al_dia():
    texto = CONTRATO.read_text(encoding="utf-8")
    errores = set(FILA.findall(_seccion(texto, "Códigos de error")))
    avisos = set(FILA.findall(_seccion(texto, "Códigos de aviso")))
    en_codigo_errores = set(salida.CODIGOS_ERROR) | set(ayuda.AYUDA)
    assert errores == en_codigo_errores, (
        f"sin documentar: {sorted(en_codigo_errores - errores)}; "
        f"documentados que no existen: {sorted(errores - en_codigo_errores)}"
    )
    assert avisos == set(salida.AVISOS), (
        f"sin documentar: {sorted(set(salida.AVISOS) - avisos)}; "
        f"documentados que no existen: {sorted(avisos - set(salida.AVISOS))}"
    )


def test_ejemplos_del_contrato_tienen_las_claves_reales(capsys):
    """Cada ejemplo trae las mismas claves de primer nivel que la salida real de su orden."""
    ejemplos = EJEMPLO.findall(CONTRATO.read_text(encoding="utf-8"))
    assert len(ejemplos) >= 8
    for orden, cuerpo in ejemplos:
        documentado = json.loads(cuerpo)
        argv = shlex.split(orden)
        if argv[0] == "comprobar":
            argv = ["comprobar", str(RAIZ / "README.md")]
        cli.main(argv)
        real = json.loads(capsys.readouterr().out)
        # `avisos` solo sale cuando hay elementos sin numerar; en el ejemplo es opcional
        assert set(documentado) - {"avisos"} == set(real) - {"avisos"}, orden


def test_cada_orden_tiene_ejemplo():
    ordenes = {shlex.split(o)[0] for o, _ in EJEMPLO.findall(CONTRATO.read_text(encoding="utf-8"))}
    ordenes.add("ficha")  # el ejemplo de error usa ficha
    assert {"catalogo", "ficha", "elemento", "norma", "buscar", "programacion", "comprobar"} <= (
        ordenes
    )
