"""Manifiesto del lote (`herramientas/normativa/lote.toml`) y `regenerar.py`, sin caché ni pdftotext."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).parents[1]
FICHAS = RAIZ / "src" / "normativa_madrid" / "datos" / "fichas"


@pytest.fixture(autouse=True)
def _herramientas_en_la_ruta(monkeypatch):
    monkeypatch.syspath_prepend(str(RAIZ))


def regenerar() -> ModuleType:
    return importlib.import_module("herramientas.normativa.regenerar")


def test_cada_ficha_del_paquete_tiene_una_entrada_y_viceversa():
    manifiesto = regenerar().leer_lote()
    codigos = [f.codigo for f in manifiesto.fichas]
    assert len(codigos) == len(set(codigos)), "fichas repetidas en lote.toml"
    assert set(codigos) == {p.stem for p in FICHAS.glob("*.json")}


def _escribir(tmp_path, texto):
    ruta = tmp_path / "lote.toml"
    ruta.write_text(texto, encoding="utf-8")
    return ruta


BASE = 'revisada = "2026-10-18"\ncursos_academicos = ["2026-27"]\n'
ENTRADA = '[[ficha]]\ncodigo = "X"\nextractor = "lomloe"\nargumentos = []\n'


def test_el_manifiesto_se_lee_con_claves_cerradas(tmp_path):
    r = regenerar()
    assert [f.codigo for f in r.leer_lote(_escribir(tmp_path, BASE + ENTRADA)).fichas] == ["X"]
    for malo in (
        BASE + "otra = 1\n" + ENTRADA,
        BASE + ENTRADA + 'sobra = "x"\n',
        BASE + ENTRADA.replace("lomloe", "inventado"),
        BASE + ENTRADA.replace("argumentos = []", "argumentos = [1]"),
        BASE + ENTRADA + ENTRADA,
        'cursos_academicos = ["2026-27"]\n' + ENTRADA,
        BASE.replace("2026-10-18", "ayer") + ENTRADA,
    ):
        with pytest.raises(ValueError):
            r.leer_lote(_escribir(tmp_path, malo))


def test_regenerar_para_en_el_primer_error(tmp_path):
    r = regenerar()
    llamadas = []

    def ejecutor(modulo, argv):
        llamadas.append((modulo, argv[:3]))
        return 1 if modulo == "extraer_lomloe" else 0

    lote = r.leer_lote(_escribir(tmp_path, BASE + ENTRADA + ENTRADA.replace('"X"', '"Y"')))
    with pytest.raises(r.ErrorRegenerar):
        r.regenerar(lote, tmp_path, tmp_path / "salida", ejecutor)
    assert [m for m, _ in llamadas] == ["normas", "extraer_lomloe"]


PRIMARIA = (
    '[[ficha]]\ncodigo = "{codigo}"\nextractor = "primaria"\n'
    'argumentos = ["--norma", "{norma}", "--rd", "boe-a-2022-3296"]\n'
)


def test_la_primaria_se_extrae_una_sola_vez_para_todas_sus_fichas(tmp_path):
    r = regenerar()
    llamadas = []

    def ejecutor(modulo, argv):
        llamadas.append((modulo, argv))
        if modulo == "extraer_primaria":
            for codigo in ("MAD.EP.DESC", "MAD.EP.MAT.C1"):
                ruta = tmp_path / "salida" / "fichas" / f"{codigo}.json"
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text("{}", encoding="utf-8")
        return 0

    texto = BASE + "".join(
        PRIMARIA.format(codigo=c, norma="bocm-20220718-1") for c in ("MAD.EP.DESC", "MAD.EP.MAT.C1")
    )
    r.regenerar(r.leer_lote(_escribir(tmp_path, texto)), tmp_path, tmp_path / "salida", ejecutor)
    assert [m for m, _ in llamadas] == ["normas", "extraer_primaria"]
    argv = llamadas[1][1]
    assert argv[:4] == ["--norma", "bocm-20220718-1", "--rd", "boe-a-2022-3296"]
    assert argv[4:6] == ["--cursos-academicos", "2026-27"]
    assert argv[6:] == ["--cache", str(tmp_path), "--salida", str(tmp_path / "salida")]

    # una ficha que no se escribe es un error
    texto_con_otra = texto + PRIMARIA.format(codigo="MAD.EP.MAT.C2", norma="bocm-20220718-1")
    with pytest.raises(r.ErrorRegenerar, match="MAD.EP.MAT.C2"):
        r.regenerar(
            r.leer_lote(_escribir(tmp_path, texto_con_otra)),
            tmp_path,
            tmp_path / "salida",
            ejecutor,
        )
    # y unos argumentos distintos entre sus fichas, también
    distinto = texto + PRIMARIA.format(codigo="MAD.EP.MAT.C2", norma="bocm-20990101-1")
    with pytest.raises(r.ErrorRegenerar, match="mismos argumentos"):
        r.regenerar(
            r.leer_lote(_escribir(tmp_path, distinto)), tmp_path, tmp_path / "salida", ejecutor
        )
