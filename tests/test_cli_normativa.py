"""CLI `normativa-madrid`: un documento JSON por consulta, sin red ni carpeta de trabajo."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from normativa_madrid import ayuda, cli
from normativa_madrid import ErrorNormativa, cargar, consulta, salida

SINTETICOS = Path(__file__).parent / "datos_sinteticos"
HOY = date(2026, 10, 17)
MATERIA = "MAD.ESO.CCOMP.1"
ELEMENTO = f"{MATERIA}.CE.2"  # «Diseña una solución sencilla a un problema dado.»


@pytest.fixture
def datos(monkeypatch):
    """Los datos sintéticos y el día fijo, en el punto por el que consulta los toma."""
    monkeypatch.setattr(consulta, "cargar", lambda: cargar(SINTETICOS))
    monkeypatch.setattr(consulta, "hoy_en_madrid", lambda: HOY)


def ejecutar(capsys, argv: list[str]) -> tuple[int, dict]:
    codigo = cli.main(argv)
    documento = json.loads(capsys.readouterr().out)  # exactamente un documento
    return codigo, documento


def test_cli_ficha_json_valido(datos, capsys):
    codigo, documento = ejecutar(capsys, ["ficha", MATERIA])
    assert codigo == 0
    salida.validar(documento)
    assert documento["consulta"] == "ficha"
    assert documento["codigo"] == MATERIA


def test_cli_error_es_json(datos, capsys):
    codigo, documento = ejecutar(capsys, ["elemento", "MAD.NO.EXISTE"])
    assert codigo == 2
    assert documento["error"] == "CODIGO_DESCONOCIDO"
    salida.validar(documento)


def test_cli_utf8_en_consola_cp1252(tmp_path, monkeypatch):
    # Los datos sintéticos no traen «º»: se copian y se añade uno al texto del elemento.
    copia = tmp_path / "datos"
    shutil.copytree(SINTETICOS, copia)
    ficha_json = copia / "fichas" / "materia_ccomp_1.json"
    original = "Diseña una solución sencilla a un problema dado."
    texto_json = ficha_json.read_text(encoding="utf-8")
    assert original in texto_json
    ficha_json.write_text(
        texto_json.replace(original, "Diseña una solución al problema 1º."), encoding="utf-8"
    )
    monkeypatch.setattr(consulta, "cargar", lambda: cargar(copia))
    monkeypatch.setattr(consulta, "hoy_en_madrid", lambda: HOY)

    flujo = io.BytesIO()
    consola = io.TextIOWrapper(flujo, encoding="cp1252", write_through=True)
    monkeypatch.setattr(sys, "stdout", consola)
    assert cli.main(["elemento", ELEMENTO]) == 0
    texto = flujo.getvalue().decode("utf-8")
    assert json.loads(texto)["elemento"]["texto"] == "Diseña una solución al problema 1º."
    assert "º" in texto


def test_cli_curso_academico_en_todos(datos, capsys):
    pedidos = [
        (["catalogo"], "catalogo"),
        (["ficha", MATERIA], "ficha"),
        (["elemento", ELEMENTO], "elemento"),
        (["buscar", "solución", "--en", MATERIA], "buscar"),
        (["programacion", "eso"], "programacion"),
    ]
    for argumentos, consulta_esperada in pedidos:
        codigo, documento = ejecutar(
            capsys, [*argumentos, "--curso-academico", "2026-27"]
        )
        assert codigo == 0, consulta_esperada
        assert documento["consulta"] == consulta_esperada
        assert documento["curso_academico"] == "2026-27"
        assert documento["curso_en_vigor"] is True
        salida.validar(documento)


def test_cli_norma_no_admite_curso_academico(datos):
    with pytest.raises(SystemExit) as info:
        cli.main(["norma", "Decreto 27/2025", "--curso-academico", "2026-27"])
    assert info.value.code == 2


def test_cli_no_escribe_ficheros(datos, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    codigo, _ = ejecutar(capsys, ["catalogo"])
    assert codigo == 0
    assert list(tmp_path.iterdir()) == []


def test_cli_sin_datos_da_error_json(tmp_path, monkeypatch, capsys):
    vacio = tmp_path / "datos"
    (vacio / "normas").mkdir(parents=True)
    (vacio / "fichas").mkdir()
    monkeypatch.setattr(consulta, "cargar", lambda: cargar(vacio))
    codigo, documento = ejecutar(capsys, ["ficha", MATERIA])
    assert codigo == 2
    assert documento["error"] == "NORMATIVA_SIN_DATOS"
    assert documento["disponibles"] == []
    salida.validar(documento)
    # Con los datos reales vacíos, catalogo también falla: así lo fija la consulta (tarea 3).
    codigo, documento = ejecutar(capsys, ["catalogo"])
    assert codigo == 2
    assert documento["error"] == "NORMATIVA_SIN_DATOS"


def test_cli_detalle_sin_caracteres_de_control(monkeypatch, capsys):
    def con_basura(*_args, **_kwargs):
        raise ErrorNormativa("CODIGO_DESCONOCIDO", "malo\x07 con\u200b ruido\n", ("x\x00y",))

    monkeypatch.setattr(consulta, "elemento", con_basura)
    codigo, documento = ejecutar(capsys, ["elemento", "X"])
    assert codigo == 2
    assert documento == {
        "error": "CODIGO_DESCONOCIDO",
        "detalle": "malo con ruido",
        "disponibles": ["xy"],
    }


def test_cli_salida_invalida_no_da_traceback(datos, monkeypatch, capsys):
    def no_valida(_documento):
        raise salida.ErrorSalida("TIPO_INCORRECTO", "prueba")

    monkeypatch.setattr(salida, "validar", no_valida)
    codigo, documento = ejecutar(capsys, ["catalogo"])
    assert codigo == 2
    assert documento == {"error": "SALIDA_INVALIDA", "detalle": "", "disponibles": []}


def test_normativa_no_carga_modulos_de_red():
    codigo = (
        "import sys\n"
        "import normativa_madrid.consulta\n"
        "for modulo in ('requests', 'urllib.request', 'http.client', 'socket'):\n"
        "    assert modulo not in sys.modules, modulo + ' cargado'\n"
    )
    subprocess.run([sys.executable, "-c", codigo], check=True)


def test_todo_codigo_de_error_tiene_ayuda():
    assert set(ayuda.AYUDA) >= salida.CODIGOS_ERROR


def test_normativa_ayuda_en_espanol(capsys):
    with pytest.raises(SystemExit) as info:
        cli.main(["--help"])
    assert info.value.code == 0
    texto = capsys.readouterr().out
    for consulta_nombre in ("catalogo", "ficha", "elemento", "norma", "buscar", "programacion"):
        assert consulta_nombre in texto


def test_cli_norma_con_cita_valida(datos, capsys):
    codigo, documento = ejecutar(capsys, ["norma", "Decreto 27/2025"])
    assert codigo == 0
    assert documento["consulta"] == "norma"
    salida.validar(documento)


@pytest.mark.parametrize(
    "invisible",
    ["\x00", "\n", "\x7f", "\x85", "\x9b", "\u00ad", "\u200b", "\u202e", "\u2066", "\ufeff"],
)
def test_la_salida_rechaza_los_mismos_invisibles_que_el_cargador(invisible):
    # C0 y DEL (Cc), C1 (Cc) y formato (Cf: guion blando, cero ancho, marcas bidi)
    malo = {"error": "CODIGO_DESCONOCIDO", "detalle": f"a{invisible}b", "disponibles": []}
    with pytest.raises(salida.ErrorSalida):
        salida.validar(malo)
    malo = {"error": "CODIGO_DESCONOCIDO", "detalle": "a", "disponibles": [f"x{invisible}"]}
    with pytest.raises(salida.ErrorSalida):
        salida.validar(malo)


# --- codigo_oficial y aviso de numeración no oficial (datos reales del paquete) ---------------


def test_codigo_oficial_de_criterio(capsys):
    codigo, documento = ejecutar(
        capsys, ["elemento", "MAD.ESO.TECDIG.2.CR.1.1", "--curso-academico", "2026-27"]
    )
    assert codigo == 0
    salida.validar(documento)
    assert documento["elemento"]["codigo_oficial"] == "1.1"


def test_aviso_numeracion_no_oficial(capsys):
    codigo, documento = ejecutar(
        capsys, ["elemento", "MAD.ESO.TECDIG.2.CO.A.1", "--curso-academico", "2026-27"]
    )
    assert codigo == 0
    salida.validar(documento)
    assert documento["elemento"]["codigo_oficial"] is None
    assert [a["codigo"] for a in documento["avisos"]] == ["NUMERACION_NO_OFICIAL"]
    assert "no lo presentes como numeración oficial" in documento["avisos"][0]["detalle"]

    codigo, documento = ejecutar(
        capsys, ["elemento", "MAD.ESO.TECDIG.2.CR.1.1", "--curso-academico", "2026-27"]
    )
    assert documento["avisos"] == []


def test_aviso_en_ficha_y_busqueda_solo_si_hay_elementos_sin_numerar(capsys):
    _, ficha = ejecutar(capsys, ["ficha", "MAD.ESO.TECDIG.2", "--curso-academico", "2026-27"])
    salida.validar(ficha)
    assert [a["codigo"] for a in ficha["avisos"]] == ["NUMERACION_NO_OFICIAL"]
    _, busqueda = ejecutar(
        capsys, ["buscar", "definir problemas", "--en", "MAD.ESO.TECDIG.2", "--curso-academico", "2026-27"]
    )
    salida.validar(busqueda)
    codigos = {r["codigo"]: r["codigo_oficial"] for r in busqueda["resultados"]}
    assert codigos["MAD.ESO.TECDIG.2.CR.1.1"] == "1.1"


def test_la_salida_rechaza_un_aviso_inventado(capsys):
    _, documento = ejecutar(
        capsys, ["elemento", "MAD.ESO.TECDIG.2.CO.A.1", "--curso-academico", "2026-27"]
    )
    documento["avisos"][0]["detalle"] = "otra cosa"
    with pytest.raises(salida.ErrorSalida):
        salida.validar(documento)
