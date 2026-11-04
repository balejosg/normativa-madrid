"""Migración de la Primaria de Madrid al formato común: no se pierde ningún código citable.

La referencia es una copia congelada del JSON de Primaria anterior a este paquete
(`tests/referencia/primaria-madrid-bd89f26.json`): áreas con competencias (y sus variantes de
redacción por ciclo), criterios y contenidos, más los descriptores del anexo I. Todo offline,
sobre los datos del paquete.

El JSON antiguo cuenta las páginas del PDF (la primera es la 1); las fichas citan la página que
imprime el boletín («Pág. 15» en la primera del Decreto 61/2022): hay 14 de diferencia.
"""

from __future__ import annotations

import importlib
import json
from collections import Counter
from pathlib import Path
from types import ModuleType

import pytest

from normativa_madrid import cargar, consulta

RAIZ = Path(__file__).parents[1]
REFERENCIA = Path(__file__).parent / "referencia" / "primaria-madrid-bd89f26.json"
DESFASE = 14  # página del boletín = página del PDF + 14
FICHAS_EP = 25  # 7 áreas por 3 ciclos, VCE, SLE, TYR y los descriptores


@pytest.fixture(autouse=True)
def _herramientas_en_la_ruta(monkeypatch):
    monkeypatch.syspath_prepend(str(RAIZ))


def herramienta(nombre: str) -> ModuleType:
    return importlib.import_module(f"herramientas.normativa.{nombre}")


@pytest.fixture(scope="module")
def referencia():
    return json.loads(REFERENCIA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def indice():
    return cargar()


def fichas_ep(indice):
    return {c: f for c, f in indice.fichas.items() if c.startswith("MAD.EP.")}


def plano(texto: str) -> str:
    """Normalizado como en `comprobar`: NFC y espacios simples."""
    return herramienta("comprobar")._plano(texto)


def ciclo_de(ficha) -> str:
    """El ciclo en que rige la ficha, como lo escribe el JSON antiguo («E»: toda la etapa)."""
    if ficha.ciclo is not None:
        return ficha.ciclo
    if ficha.curso is not None:
        return consulta.ciclo_de_curso(ficha.curso)
    return "E"


def unico(indice, codigo):
    hallados = [
        (f, e) for f in fichas_ep(indice).values() for e in f.elementos if e.codigo == codigo
    ]
    assert len(hallados) == 1, (codigo, len(hallados))
    return hallados[0]


def test_hay_todas_las_fichas(indice):
    assert len(fichas_ep(indice)) == FICHAS_EP


def test_migracion_primaria_sin_perdidas(indice, referencia):
    codigo_nuevo = herramienta("extraer_primaria").codigo_nuevo
    for area in referencia["areas"]:
        for c in area["criterios"]:
            ficha, e = unico(indice, codigo_nuevo(c["codigo"]))
            assert e.tipo == "criterio"
            assert plano(e.texto) == plano(c["texto"]), c["codigo"]
            assert ciclo_de(ficha) == c["ciclo"], c["codigo"]
            n, m = c["codigo"].split(".")[1:3]
            assert e.codigo_oficial == f"{n}.{m}", c["codigo"]
            assert e.procedencia.pagina == c["pagina"] + DESFASE, c["codigo"]
            assert e.padre == f"{ficha.codigo}.CE.{n}", c["codigo"]

        fichas_del_area = {
            ciclo_de(f): f
            for codigo, f in fichas_ep(indice).items()
            if codigo.split(".")[2] == area["codigo"]
        }
        assert sorted(fichas_del_area) == sorted(area["ciclos"]), area["codigo"]
        for ciclo, ficha in fichas_del_area.items():
            competencias = {
                e.codigo: e for e in ficha.elementos if e.tipo == "competencia_especifica"
            }
            assert len(competencias) == len(area["competencias"]), (ficha.codigo, ciclo)
            for comp in area["competencias"]:
                e = competencias[f"{ficha.codigo}.CE.{comp['numero']}"]
                esperado = comp["variantes"].get(ciclo, comp["texto"])
                assert plano(e.texto) == plano(esperado), (comp["codigo"], ciclo)
                assert e.codigo_oficial == str(comp["numero"])
                assert e.relaciones.get("descriptores", ()) == tuple(
                    f"MAD.EP.DESC.{d}" for d in comp["descriptores"]
                ), (comp["codigo"], ciclo)
                if comp["equivalencia_rd"] is None:
                    assert "equivalencia_rd" not in e.datos
                else:
                    assert e.datos["equivalencia_rd"] == comp["equivalencia_rd"]
            # el padre de cada criterio es la competencia de su número, en su ficha
            for e in ficha.elementos:
                if e.tipo == "criterio":
                    assert e.padre == f"{ficha.codigo}.CE.{e.codigo_oficial.split('.')[0]}"

            antiguos = Counter(
                (plano(c["texto"]), c["pagina"] + DESFASE)
                for c in area["contenidos"]
                if c["ciclo"] == ciclo
            )
            nuevos = Counter(
                (plano(e.texto), e.procedencia.pagina)
                for e in ficha.elementos
                if e.tipo == "contenido"
            )
            assert nuevos == antiguos, (ficha.codigo, antiguos - nuevos, nuevos - antiguos)

    descriptores = [e for e in indice.fichas["MAD.EP.DESC"].elementos if e.tipo == "descriptor"]
    assert len(descriptores) == len(referencia["descriptores"])
    for d, e in zip(referencia["descriptores"], descriptores, strict=True):
        assert e.codigo == f"MAD.EP.DESC.{d['codigo']}" == codigo_nuevo(d["codigo"])
        assert e.codigo_oficial == d["codigo"]
        assert plano(e.texto) == plano(d["texto"])


def test_competencia_antigua_va_al_primer_ciclo_en_que_aparece(indice, referencia):
    codigo_nuevo = herramienta("extraer_primaria").codigo_nuevo
    for area in referencia["areas"]:
        primero = area["ciclos"][0]
        for comp in area["competencias"]:
            ficha, e = unico(indice, codigo_nuevo(comp["codigo"]))
            assert ciclo_de(ficha) == primero
            assert plano(e.texto) == plano(comp["texto"])


def test_recuentos_primaria(indice):
    comprobar = herramienta("comprobar")
    fuentes = herramienta("comun").leer_fuentes()
    problemas = []
    assert len(fichas_ep(indice)) == FICHAS_EP
    for codigo, ficha in fichas_ep(indice).items():
        assert any(codigo in r["recuentos"] for r in fuentes.values()), codigo
        problemas += comprobar.comprobar_recuentos(ficha, fuentes)
    assert not problemas, [str(p) for p in problemas]


def test_contenidos_sin_codigo_oficial(indice):
    contenidos = [
        e for f in fichas_ep(indice).values() for e in f.elementos if e.tipo == "contenido"
    ]
    assert contenidos
    for e in contenidos:
        assert e.codigo_oficial is None, e.codigo


def test_estructura_de_los_contenidos(indice):
    """Bloques y sub-bloques son `bloque_contenidos`; cada contenido cuelga de uno o de otro
    contenido, con un código que empieza por el de su padre."""
    for ficha in fichas_ep(indice).values():
        por_codigo = {e.codigo: e for e in ficha.elementos}
        for e in ficha.elementos:
            if e.tipo not in ("bloque_contenidos", "contenido"):
                continue
            assert e.codigo.startswith(f"{ficha.codigo}.CO."), e.codigo
            if e.padre is None:
                assert e.tipo == "bloque_contenidos", e.codigo
                continue
            assert e.codigo.rsplit(".", 1)[0] == e.padre, e.codigo
            padre = por_codigo[e.padre]
            if e.tipo == "bloque_contenidos":  # un sub-bloque cuelga de su bloque
                assert padre.tipo == "bloque_contenidos" and padre.padre is None, e.codigo
            else:
                assert padre.tipo in ("bloque_contenidos", "contenido"), e.codigo


def test_descriptores_de_primaria_existen(indice):
    citados = 0
    for ficha in fichas_ep(indice).values():
        for e in ficha.elementos:
            for sigla in e.relaciones.get("descriptores", ()):
                citados += 1
                assert indice.elementos[sigla][0].codigo == "MAD.EP.DESC", (e.codigo, sigla)
    assert citados > 0


def test_ubicaciones(indice):
    ficha = indice.fichas["MAD.EP.MAT.C2"]
    criterio = next(e for e in ficha.elementos if e.tipo == "criterio")
    assert criterio.procedencia.ubicacion == "anexo II, Matemáticas, segundo ciclo, criterios"
    assert criterio.procedencia.norma == "bocm-20220718-1"
    desc = indice.fichas["MAD.EP.DESC"].elementos[0]
    assert desc.procedencia.ubicacion == "anexo I, descriptores"
    assert indice.fichas["MAD.EP.VCE"].curso == "5"
    assert indice.fichas["MAD.EP.SLE"].curso is None and indice.fichas["MAD.EP.SLE"].ciclo is None
