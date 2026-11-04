"""Etapa Primaria: fichas por ciclo, por curso o de toda la etapa (todo offline, datos de juguete)."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import pytest

from normativa_madrid import ErrorNormativa, cargar, consulta, limpiar_cache, salida

SINTETICOS = Path(__file__).parent / "datos_sinteticos"
HOY = date(2026, 10, 17)
FICHA_C2 = "fichas/primaria_mat_c2.json"


@pytest.fixture(scope="module")
def indice():
    return cargar(SINTETICOS)


def fallo(llamada) -> ErrorNormativa:
    with pytest.raises(ErrorNormativa) as info:
        llamada()
    return info.value


def pedir(indice, codigo, **filtros):
    return consulta.ficha(codigo, None, hoy=HOY, indice=indice, **filtros)


def cargar_modificado(tmp_path: Path, cambio) -> ErrorNormativa:
    raiz = tmp_path / "datos"
    shutil.copytree(SINTETICOS, raiz)
    ruta = raiz / FICHA_C2
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    cambio(datos)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    limpiar_cache()
    return fallo(lambda: cargar(raiz))


def test_ciclo_invalido(tmp_path):
    error = cargar_modificado(tmp_path, lambda d: d.update(ciclo="C4"))
    assert error.codigo == "DATOS_INVALIDOS" and "ciclo" in error.detalle


def test_ciclo_y_curso_a_la_vez(tmp_path):
    error = cargar_modificado(tmp_path, lambda d: d.update(curso="3"))
    assert error.codigo == "DATOS_INVALIDOS" and "ciclo" in error.detalle


def test_ciclo_fuera_de_primaria(tmp_path):
    error = cargar_modificado(tmp_path, lambda d: d.update(etapa="eso"))
    assert error.codigo == "DATOS_INVALIDOS" and "ciclo" in error.detalle


def test_curso_de_primaria_entre_1_y_6(tmp_path):
    def cambio(d):
        d.pop("ciclo")
        d["curso"] = "7"

    error = cargar_modificado(tmp_path, cambio)
    assert error.codigo == "DATOS_INVALIDOS" and "curso" in error.detalle


def test_la_ficha_carga_su_ciclo(indice):
    assert indice.fichas["MAD.EP.MAT.C2"].ciclo == "C2"
    assert indice.fichas["MAD.EP.VCE"].ciclo is None
    assert indice.fichas["MAD.EP.VCE"].curso == "5"


def test_ciclo_de_curso():
    assert [consulta.ciclo_de_curso(c) for c in range(1, 7)] == ["C1", "C1", "C2", "C2", "C3", "C3"]
    for malo in (0, 7):
        assert fallo(lambda m=malo: consulta.ciclo_de_curso(m)).codigo == "CURSO_SIN_DATOS"


def test_curso_a_ciclo(indice):
    assert pedir(indice, "MAD.EP.MAT", curso=3).codigo == "MAD.EP.MAT.C2"
    assert pedir(indice, "MAD.EP.MAT", curso="6").codigo == "MAD.EP.MAT.C3"
    assert pedir(indice, "MAD.EP.VCE", curso=5).codigo == "MAD.EP.VCE"
    assert pedir(indice, "MAD.EP.TYR", curso=4).codigo == "MAD.EP.TYR"
    error = fallo(lambda: pedir(indice, "MAD.EP.VCE", curso=2))
    assert error.codigo == "CURSO_SIN_DATOS"
    assert error.disponibles == ("5",)


def test_ciclo_pedido(indice):
    assert pedir(indice, "MAD.EP.MAT", ciclo="C3").codigo == "MAD.EP.MAT.C3"
    assert pedir(indice, "MAD.EP.VCE", ciclo="C3").codigo == "MAD.EP.VCE"
    assert pedir(indice, "MAD.EP.TYR", ciclo="C1").codigo == "MAD.EP.TYR"
    assert fallo(lambda: pedir(indice, "MAD.EP.VCE", ciclo="C2")).codigo == "CURSO_SIN_DATOS"


def test_ciclo_sin_ficha(indice):
    error = fallo(lambda: pedir(indice, "MAD.EP.MAT", curso=1))  # el sintético no trae C1
    assert error.codigo == "CURSO_SIN_DATOS"
    assert error.disponibles == ("C2", "C3")


def test_area_sin_curso_ni_ciclo(indice):
    error = fallo(lambda: pedir(indice, "MAD.EP.MAT"))
    assert error.codigo == "CURSO_SIN_DATOS"
    assert error.disponibles == ("MAD.EP.MAT.C2", "MAD.EP.MAT.C3")


def test_curso_o_ciclo_invalidos(indice):
    for filtros in ({"curso": 0}, {"curso": "7"}, {"curso": "x"}, {"ciclo": "C4"}, {"ciclo": "c"}):
        assert fallo(lambda f=filtros: pedir(indice, "MAD.EP.MAT", **f)).codigo == "CURSO_SIN_DATOS"
    # curso y ciclo que se contradicen
    assert fallo(lambda: pedir(indice, "MAD.EP.MAT", curso=1, ciclo="C3")).codigo == "CURSO_SIN_DATOS"
    assert pedir(indice, "MAD.EP.MAT", curso=5, ciclo="C3").codigo == "MAD.EP.MAT.C3"


def test_area_desconocida(indice):
    error = fallo(lambda: pedir(indice, "MAD.EP.XXX", curso=3))
    assert error.codigo == "NORMATIVA_SIN_DATOS"
    assert "MAD.EP.MAT" in error.disponibles and "MAD.EP.MAT.C2" in error.disponibles


def test_codigo_de_ficha_como_hasta_ahora(indice):
    assert pedir(indice, "MAD.EP.MAT.C2").codigo == "MAD.EP.MAT.C2"
    assert pedir(indice, "MAD.ESO.CCOMP.1").codigo == "MAD.ESO.CCOMP.1"
    assert pedir(indice, "MAD.EP.MAT.C2", curso=4).codigo == "MAD.EP.MAT.C2"
    assert fallo(lambda: pedir(indice, "MAD.EP.MAT.C2", curso=5)).codigo == "CURSO_SIN_DATOS"


def test_salida_de_ficha_dice_el_ciclo(indice):
    r = pedir(indice, "MAD.EP.MAT", curso=3)
    assert r.ciclo == "C2" and r.etapa == "primaria"
    documento = r.a_dict()
    salida.validar(documento)
    assert documento["ciclo"] == "C2"


def test_equivalencia_rd(indice):
    r = pedir(indice, "MAD.EP.MAT", ciclo="C2")
    assert r.elementos[0].datos == {"equivalencia_rd": "CMNSC.CE5"}
    documento = r.a_dict()
    salida.validar(documento)
    assert documento["elementos"][0]["datos"]["equivalencia_rd"] == "CMNSC.CE5"


def test_catalogo_por_etapa(indice):
    c = consulta.catalogo("2026-27", etapa="primaria", hoy=HOY, indice=indice)
    assert [f.codigo for f in c.fichas] == [
        "MAD.EP.MAT.C2",
        "MAD.EP.MAT.C3",
        "MAD.EP.TYR",
        "MAD.EP.VCE",
    ]
    assert {f.ciclo for f in c.fichas} == {"C2", "C3", None}
    salida.validar(c.a_dict())
    todo = consulta.catalogo("2026-27", hoy=HOY, indice=indice)
    assert len(todo.fichas) > len(c.fichas)
    error = fallo(lambda: consulta.catalogo("2026-27", etapa="infantil", hoy=HOY, indice=indice))
    assert error.codigo == "ETAPA_DESCONOCIDA"
    assert "primaria" in error.disponibles


def test_cli_primaria(monkeypatch, capsys):
    from normativa_madrid import cli

    monkeypatch.setattr(consulta, "cargar", lambda: cargar(SINTETICOS))
    monkeypatch.setattr(consulta, "hoy_en_madrid", lambda: HOY)

    def ejecutar(*argv):
        codigo = cli.main(list(argv))
        return codigo, json.loads(capsys.readouterr().out)

    codigo, doc = ejecutar("ficha", "MAD.EP.MAT", "--curso", "3")
    assert (codigo, doc["codigo"]) == (0, "MAD.EP.MAT.C2")
    codigo, doc = ejecutar("ficha", "MAD.EP.MAT", "--ciclo", "C3")
    assert (codigo, doc["codigo"]) == (0, "MAD.EP.MAT.C3")
    codigo, doc = ejecutar("ficha", "MAD.EP.VCE", "--curso", "2")
    assert (codigo, doc["error"]) == (2, "CURSO_SIN_DATOS")
    codigo, doc = ejecutar("catalogo", "--etapa", "primaria")
    assert codigo == 0 and len(doc["fichas"]) == 4
    codigo, doc = ejecutar("catalogo", "--etapa", "otra")
    assert (codigo, doc["error"]) == (2, "ETAPA_DESCONOCIDA")


@pytest.mark.parametrize("filtro", [{"curso": 3}, {"ciclo": "C2"}])
def test_curso_o_ciclo_en_una_ficha_que_no_es_de_primaria_es_error(indice, filtro):
    error = fallo(lambda: pedir(indice, "MAD.ESO.CCOMP.1", **filtro))
    assert error.codigo == "CURSO_SIN_DATOS"
    assert "no es de Primaria" in error.detalle
    salida.error_a_dict(error)
