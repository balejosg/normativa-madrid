"""Extractor de Primaria (`herramientas/normativa/extraer_primaria.py`).

La interpretación de las tablas y el paso a fichas, sobre eventos y datos de juguete (sin PDF ni
pdfplumber). La extracción real del Decreto 61/2022 solo corre con la variable
``NORMATIVA_CACHE`` apuntando a una caché con sus PDF y con pdfplumber instalado
(``uv run --group mantenimiento``); si no, se salta.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).parents[1]
REFERENCIA = Path(__file__).parent / "referencia" / "primaria-madrid-bd89f26.json"


@pytest.fixture(autouse=True)
def _herramientas_en_la_ruta(monkeypatch):
    monkeypatch.syspath_prepend(str(RAIZ))


def primaria() -> ModuleType:
    return importlib.import_module("herramientas.normativa.extraer_primaria")


# --- códigos ---------------------------------------------------------------------------------


def test_codigo_nuevo():
    nuevo = primaria().codigo_nuevo
    assert nuevo("MAT.1.1.C2") == "MAD.EP.MAT.C2.CR.1.1"
    assert nuevo("MAT.CE1") == "MAD.EP.MAT.C1.CE.1"
    assert nuevo("CS.10.12.C3") == "MAD.EP.CS.C3.CR.10.12"
    assert nuevo("VCE.2.3.C3") == "MAD.EP.VCE.CR.2.3"
    assert nuevo("VCE.CE4") == "MAD.EP.VCE.CE.4"
    assert nuevo("SLE.1.1.E") == "MAD.EP.SLE.CR.1.1"
    assert nuevo("TYR.CE6") == "MAD.EP.TYR.CE.6"
    assert nuevo("CCEC4") == "MAD.EP.DESC.CCEC4"


@pytest.mark.parametrize(
    "malo", ["MAT.1.1.E", "VCE.1.1.C2", "XXX.CE1", "MAT.CE", "CMNSC.CE5", "MAD.EP.MAT.C1.CE.1", ""]
)
def test_codigo_nuevo_rechaza_lo_que_no_es_de_primaria(malo):
    with pytest.raises(ValueError):
        primaria().codigo_nuevo(malo)


# --- interpretación de las tablas ------------------------------------------------------------

CABECERA_CE = (
    "fila",
    38,
    [(44, 203, "COMPETENCIAS ESPECÍFICAS"), (214, 552, "CRITERIOS DE EVALUACIÓN")],
)
CABECERA_CO = (
    "fila",
    38,
    [(38, 127, "BLOQUES"), (133, 557, "CONOCIMIENTOS, DESTREZAS Y ACTITUDES")],
)


def eventos_de_mat(ciclo_criterios: list) -> list:
    """El anexo II con todas las áreas vacías salvo Matemáticas, que trae ``ciclo_criterios``."""
    eventos = []
    for area in primaria().AREAS:
        eventos.append((40, ("area", area["codigo"])))
        if area["codigo"] == "MAT":
            eventos += ciclo_criterios
    return eventos


def test_criterios_y_contenidos_con_su_pagina():
    p = primaria()
    eventos = eventos_de_mat(
        [
            (40, ("ciclo", "C1")),
            (40, CABECERA_CE),
            (40, ("fila", 38, [(38, 209, "1. Contar\ncosas."), (209, 557, "1.1. Primero\nque sigue.\n1.2 Segundo")])),
            # la fila sigue en la página siguiente: la competencia y el criterio continúan
            (41, ("fila", 38, [(38, 209, "y más cosas."), (209, 557, "continúa.")])),
            (41, ("fila", 38, [(38, 209, ""), (209, 557, "")])),
            (41, ("fila", 38, [(38, 557, "CONTENIDOS")])),
            (41, CABECERA_CO),
            (41, ("fila", 38, [(38, 50, "A. Números"), (60, 127, "Conteo"), (133, 557, "- Uno\nsigue.\n(cid:2) Uno bis.\n(cid:3) Uno ter.\n- Dos.")])),
            (42, ("fila", 38, [(38, 50, ""), (60, 127, "Cantidad"), (133, 557, "- Tres.")])),
        ]
    )  # fmt: skip
    areas = p.leer_anexo_ii(eventos)
    mat = next(a for a in areas if a.codigo == "MAT")
    assert mat.competencias == {"C1": {1: "Contar cosas. y más cosas."}}
    assert mat.paginas_competencias == {"C1": {1: 40}}
    assert [(c["n"], c["m"], c["texto"], c["pagina"]) for c in mat.criterios] == [
        (1, 1, "Primero que sigue.", 40),
        (1, 2, "Segundo continúa.", 40),
    ]
    assert [(c["bloque"], c["subbloque"], c["nivel"], c["texto"], c["pagina"]) for c in mat.contenidos] == [
        ("A. Números", "Conteo", 1, "Uno sigue.", 41),
        ("A. Números", "Conteo", 2, "Uno bis.", 41),
        ("A. Números", "Conteo", 3, "Uno ter.", 41),
        ("A. Números", "Conteo", 1, "Dos.", 41),
        ("A. Números", "Cantidad", 1, "Tres.", 42),
    ]  # fmt: skip
    assert mat.paginas_bloques == {
        ("C1", "A. Números", None): 41,
        ("C1", "A. Números", "Conteo"): 41,
        ("C1", "A. Números", "Cantidad"): 42,
    }


@pytest.mark.parametrize(
    "fila",
    [
        # un criterio que no es de la competencia de su fila
        ("fila", 38, [(38, 209, "1. Contar."), (209, 557, "2.1. Fuera de sitio.")]),
        # texto de criterio sin numeración ni criterio anterior
        ("fila", 38, [(38, 209, "1. Contar."), (209, 557, "sin número")]),
        # dos celdas en la columna de los criterios
        ("fila", 38, [(38, 209, "1. Contar."), (209, 300, "1.1. A."), (310, 557, "1.2. B.")]),
    ],
)
def test_una_tabla_que_no_encaja_es_un_error(fila):
    p = primaria()
    eventos = eventos_de_mat([(40, ("ciclo", "C1")), (40, CABECERA_CE), (40, fila)])
    with pytest.raises(p.ErrorPrimaria, match="MAT"):
        p.leer_anexo_ii(eventos)


def test_un_contenido_sin_vineta_ni_anterior_es_un_error():
    p = primaria()
    eventos = eventos_de_mat(
        [
            (40, ("ciclo", "C1")),
            (41, ("fila", 38, [(38, 557, "CONTENIDOS")])),
            (41, CABECERA_CO),
            (41, ("fila", 38, [(38, 50, "A. Números"), (133, 557, "Sin viñeta.")])),
        ]
    )
    with pytest.raises(p.ErrorPrimaria, match="pág. 41"):
        p.leer_anexo_ii(eventos)


def test_faltan_areas_es_un_error():
    p = primaria()
    with pytest.raises(p.ErrorPrimaria, match="áreas"):
        p.leer_anexo_ii([(40, ("area", "MAT"))])


# --- de lo leído a las fichas ---------------------------------------------------------------


def leida(codigo="MAT", ciclos=("C1", "C2", "C3"), bloque="A. Números", sub="Conteo"):
    return {
        "codigo": codigo,
        "nombre": "Matemáticas",
        "ciclos": list(ciclos),
        "competencias": [
            {
                "codigo": f"{codigo}.CE1",
                "numero": 1,
                "texto": "Contar cosas.",
                "variantes": {ciclos[-1]: "Contar  más cosas."},
                "descriptores": ["STEM1", "CD2"],
                "equivalencia_rd": "CMNSC.CE5" if codigo == "CS" else None,
                "paginas": {c: 80 + i for i, c in enumerate(ciclos)},
            }
        ],
        "criterios": [
            {"codigo": f"{codigo}.1.{m}.{c}", "ciclo": c, "competencia": f"{codigo}.CE1",
             "texto": f"Criterio {m} de {c}.", "pagina": 80 + i}
            for i, c in enumerate(ciclos) for m in (1, 2)
        ],
        "contenidos": [
            {"ciclo": c, "bloque": bloque, "subbloque": sub, "nivel": nivel, "texto": texto,
             "pagina": 90}
            for c in ciclos
            for nivel, texto in ((1, "Uno."), (2, "Uno bis."), (3, "Uno ter."), (2, "Uno quater."), (1, "Dos."))
        ],
        "bloques": [
            {"ciclo": c, "bloque": bloque, "subbloque": s, "pagina": 89}
            for c in ciclos for s in (None, sub)
        ],
    }  # fmt: skip


def ficha(leido, ciclo):
    return primaria().ficha_de_area(
        leido,
        ciclo,
        norma="bocm-20220718-1",
        norma_rd="boe-a-2022-3296",
        cursos_academicos=["2026-27"],
    )


def test_ficha_de_un_ciclo():
    f = ficha(leida(), "C2")
    assert (f["codigo"], f["nombre"], f["etapa"], f["ciclo"], f["curso"]) == (
        "MAD.EP.MAT.C2", "Matemáticas, segundo ciclo", "primaria", "C2", None
    )  # fmt: skip
    assert f["normas"] == ["bocm-20220718-1", "boe-a-2022-3296"]
    filas = [(e["codigo"], e["tipo"], e["codigo_oficial"], e.get("padre")) for e in f["elementos"]]
    assert filas == [
        ("MAD.EP.MAT.C2.CE.1", "competencia_especifica", "1", None),
        ("MAD.EP.MAT.C2.CR.1.1", "criterio", "1.1", "MAD.EP.MAT.C2.CE.1"),
        ("MAD.EP.MAT.C2.CR.1.2", "criterio", "1.2", "MAD.EP.MAT.C2.CE.1"),
        ("MAD.EP.MAT.C2.CO.A", "bloque_contenidos", "A", None),
        ("MAD.EP.MAT.C2.CO.A.1", "bloque_contenidos", None, "MAD.EP.MAT.C2.CO.A"),
        ("MAD.EP.MAT.C2.CO.A.1.1", "contenido", None, "MAD.EP.MAT.C2.CO.A.1"),
        ("MAD.EP.MAT.C2.CO.A.1.1.1", "contenido", None, "MAD.EP.MAT.C2.CO.A.1.1"),
        ("MAD.EP.MAT.C2.CO.A.1.1.1.1", "contenido", None, "MAD.EP.MAT.C2.CO.A.1.1.1"),
        ("MAD.EP.MAT.C2.CO.A.1.1.2", "contenido", None, "MAD.EP.MAT.C2.CO.A.1.1"),
        ("MAD.EP.MAT.C2.CO.A.1.2", "contenido", None, "MAD.EP.MAT.C2.CO.A.1"),
    ]
    assert [e["orden"] for e in f["elementos"]] == list(range(1, 11))
    ce, cr, _, bloque, sub = f["elementos"][:5]
    assert ce["texto"] == "Contar cosas."  # la variante es de C3
    assert ce["relaciones"] == {"descriptores": ["MAD.EP.DESC.STEM1", "MAD.EP.DESC.CD2"]}
    assert "datos" not in ce
    assert ce["procedencia"] == {
        "norma": "bocm-20220718-1",
        "ubicacion": "anexo II, Matemáticas, segundo ciclo, competencias específicas",
        "pagina": 81,
    }
    assert cr["procedencia"]["ubicacion"] == "anexo II, Matemáticas, segundo ciclo, criterios"
    assert (bloque["texto"], sub["texto"], sub["procedencia"]["pagina"]) == (
        "Números",
        "Conteo",
        89,
    )
    assert bloque["procedencia"]["ubicacion"] == "anexo II, Matemáticas, segundo ciclo, contenidos"


def test_la_variante_del_ciclo_y_la_equivalencia_con_el_rd():
    ce = ficha(leida("CS"), "C3")["elementos"][0]
    assert ce["texto"] == "Contar más cosas."
    assert ce["datos"] == {"equivalencia_rd": "CMNSC.CE5"}


def test_vce_es_de_quinto_y_sle_de_toda_la_etapa():
    vce = ficha(leida("VCE", ("C3",), sub=None), "C3")
    assert (vce["codigo"], vce["curso"], "ciclo" in vce) == ("MAD.EP.VCE", "5", False)
    assert vce["nombre"] == "Educación en Valores Cívicos y Éticos, quinto curso"
    assert vce["elementos"][0]["procedencia"]["ubicacion"] == (
        "anexo II, Educación en Valores Cívicos y Éticos, competencias específicas"
    )
    # sin sub-bloque, los contenidos cuelgan del bloque
    assert [e["codigo"] for e in vce["elementos"] if e["tipo"] == "contenido"][:2] == [
        "MAD.EP.VCE.CO.A.1",
        "MAD.EP.VCE.CO.A.1.1",
    ]
    sle = ficha(leida("SLE", ("E",)), "E")
    assert (sle["codigo"], sle["curso"], "ciclo" in sle) == ("MAD.EP.SLE", None, False)
    assert sle["nombre"] == "Segunda Lengua Extranjera"
    assert sle["normas"] == ["bocm-20220718-1"]  # sus descriptores están en el propio decreto


def test_artistica_bloque_romano_y_sub_bloque_con_letra():
    f = ficha(leida("EA", bloque="BLOQUE I Música y danza", sub="A. Recepción y análisis"), "C1")
    bloque, sub = (e for e in f["elementos"] if e["tipo"] == "bloque_contenidos")
    assert (bloque["codigo"], bloque["codigo_oficial"], bloque["texto"]) == (
        "MAD.EP.EA.C1.CO.I", "I", "Música y danza"
    )  # fmt: skip
    assert (sub["codigo"], sub["codigo_oficial"], sub["texto"]) == (
        "MAD.EP.EA.C1.CO.I.1", "A", "Recepción y análisis"
    )  # fmt: skip


def test_un_contenido_que_salta_de_nivel_es_un_error():
    p = primaria()
    leido = leida()
    leido["contenidos"][0]["nivel"] = 2
    with pytest.raises(p.ErrorPrimaria, match="nivel 2"):
        ficha(leido, "C1")


def test_un_bloque_sin_letra_es_un_error():
    p = primaria()
    with pytest.raises(p.ErrorPrimaria, match="sin letra"):
        ficha(leida(bloque="Números"), "C1")


def test_ficha_de_descriptores():
    f = primaria().ficha_de_descriptores(
        [{"codigo": "CCL1", "competencia_clave": "CCL", "texto": "Se expresa.", "pagina": 29}],
        norma="bocm-20220718-1",
        cursos_academicos=["2026-27"],
    )
    assert f["codigo"] == "MAD.EP.DESC" and f["etapa"] == "primaria" and f["curso"] is None
    assert f["elementos"] == [
        {
            "codigo": "MAD.EP.DESC.CCL1",
            "tipo": "descriptor",
            "texto": "Se expresa.",
            "codigo_oficial": "CCL1",
            "procedencia": {
                "norma": "bocm-20220718-1",
                "ubicacion": "anexo I, descriptores",
                "pagina": 29,
            },
            "orden": 1,
        }
    ]


def test_unir_conserva_el_guion_de_un_compuesto():
    p = primaria()
    assert p.unir("contenidos sintáctico-", "discursivos") == "contenidos sintáctico-discursivos"
    assert p.unir("uno", "dos") == "uno dos"
    assert p.unir_lineas("verb-\n ing  y\nmás") == "verb-ing y más"


def test_fuentes_toml_declara_el_lector_y_lo_valida(tmp_path):
    comun = importlib.import_module("herramientas.normativa.comun")
    registros = comun.leer_fuentes()
    assert registros["bocm-20220718-1"]["lector"] == "pdfplumber"
    assert registros["bocm-20220726-2"]["lector"] is None
    assert "lector" not in comun.norma_para_el_paquete(registros["bocm-20220718-1"])
    base = Path(comun.RUTA_FUENTES).read_text(encoding="utf-8")
    malo = tmp_path / "fuentes.toml"
    malo.write_text(base.replace('lector = "pdfplumber"', 'lector = "ocr"'), encoding="utf-8")
    with pytest.raises(ValueError, match="lector desconocido"):
        comun.leer_fuentes(malo)


# --- la extracción real (solo con la caché y pdfplumber) ------------------------------------


def _cache() -> Path:
    cache = os.environ.get("NORMATIVA_CACHE")
    if not cache or not (Path(cache) / "bocm-20220718-1.pdf").is_file():
        pytest.skip("sin NORMATIVA_CACHE con el PDF del Decreto 61/2022")
    if not (Path(cache) / "boe-a-2022-3296.pdf").is_file():
        pytest.skip("sin el PDF del RD 157/2022 en NORMATIVA_CACHE")
    return Path(cache)


def test_la_extraccion_reproduce_la_referencia():
    """Lo leído del PDF es, campo a campo, la referencia (con las páginas del boletín)."""
    cache = _cache()
    pdfplumber = pytest.importorskip("pdfplumber")
    p = primaria()
    with (
        pdfplumber.open(cache / "bocm-20220718-1.pdf") as decreto,
        pdfplumber.open(cache / "boe-a-2022-3296.pdf") as rd,
    ):
        leido = p.extraer_curriculo(decreto, rd)
    referencia = json.loads(REFERENCIA.read_text(encoding="utf-8"))
    desfase = 14
    assert [
        {k: d[k] for k in ("codigo", "competencia_clave", "texto")} for d in leido["descriptores"]
    ] == referencia["descriptores"]
    for nuevo, viejo in zip(leido["areas"], referencia["areas"], strict=True):
        assert nuevo["codigo"] == viejo["codigo"]
        assert nuevo["ciclos"] == viejo["ciclos"]
        assert [
            {k: v for k, v in c.items() if k != "paginas"} for c in nuevo["competencias"]
        ] == viejo["competencias"]
        assert [{**c, "pagina": c["pagina"] - desfase} for c in nuevo["criterios"]] == viejo[
            "criterios"
        ]
        assert [{**c, "pagina": c["pagina"] - desfase} for c in nuevo["contenidos"]] == viejo[
            "contenidos"
        ]
