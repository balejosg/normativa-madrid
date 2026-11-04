"""``comprobar``: los códigos citados en un documento existen (md, txt, docx y odt).

Los documentos se generan aquí con ``zipfile``; no hace falta ningún programa de ofimática.
"""

from __future__ import annotations

import io
import json
import zipfile
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from normativa_madrid import ErrorNormativa, cargar, cli, consulta, salida
from normativa_madrid.documentos import leer_texto

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CR = "MAD.EP.MAT.C2.CR.1.1"
CO = "MAD.ESO.TECDIG.2.CO.A.1"
DESC = "EST.ESO.DESC.CCL1"


def comprobar(*textos, curso=None):
    return consulta.comprobar({f"f{i}.md": t for i, t in enumerate(textos)}, curso)


def ejecutar(capsys, *argv):
    codigo = cli.main(["comprobar", *argv])
    return codigo, json.loads(capsys.readouterr().out)


def parrafo(*trozos):
    runs = "".join(f"<w:r><w:t>{t}</w:t></w:r>" for t in trozos)
    return f"<w:p>{runs}</w:p>"


def docx(ruta: Path, cuerpo="", **partes) -> Path:
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="{W}"><w:body>{cuerpo}</w:body></w:document>')
        for nombre, xml in partes.items():
            raiz = {"footnotes": "w:footnotes", "header1": "w:hdr", "footer1": "w:ftr"}[nombre]
            z.writestr(f"word/{nombre}.xml", f'<{raiz} xmlns:w="{W}">{xml}</{raiz}>')
    return ruta


def test_comprobar_limpio(tmp_path, capsys):
    f = tmp_path / "a.md"
    f.write_text(f"Trabajamos {CR}, {CO} y {DESC}.\nOtra vez {CR}.", encoding="utf-8")
    codigo, doc = ejecutar(capsys, str(f))
    assert codigo == 0
    assert doc["consulta"] == "comprobar"
    (fichero,) = doc["ficheros"]
    assert fichero["conocidos"] == [CR, CO, DESC]
    assert fichero["desconocidos"] == []


def test_comprobar_desconocido(tmp_path, capsys):
    f = tmp_path / "a.md"
    f.write_text(f"Criterio MAD.EP.MAT.C2.CR.9.9 y {CR}.", encoding="utf-8")
    codigo, doc = ejecutar(capsys, str(f))
    assert codigo == 1
    (fichero,) = doc["ficheros"]
    assert fichero["conocidos"] == [CR]
    (d,) = fichero["desconocidos"]
    assert d["codigo"] == "MAD.EP.MAT.C2.CR.9.9"
    assert d["sugerencias"] and len(d["sugerencias"]) <= 3
    assert all(s.startswith("MAD.EP.MAT.C2.") for s in d["sugerencias"])


def test_comprobar_docx_tablas(tmp_path, capsys):
    celda = f"<w:tbl><w:tr><w:tc>{parrafo(CR)}</w:tc></w:tr></w:tbl>"
    ruta = docx(
        tmp_path / "p.docx",
        parrafo("Programación") + celda,
        footnotes=f'<w:footnote w:id="1">{parrafo("Véase ", CO)}</w:footnote>',
        header1=parrafo("Unidad ", DESC),
    )
    codigo, doc = ejecutar(capsys, str(ruta))
    assert codigo == 0
    assert sorted(doc["ficheros"][0]["conocidos"]) == sorted([CR, CO, DESC])


def test_comprobar_docx_codigo_partido_en_runs(tmp_path):
    ruta = docx(tmp_path / "p.docx", parrafo("MAD.EP.MAT.", "C2.CR.", "1.1"))
    assert CR in leer_texto(str(ruta))


def test_comprobar_docx_no_une_parrafos(tmp_path):
    ruta = docx(tmp_path / "p.docx", parrafo("MAD.EP.MAT.C2.CR.1") + parrafo("1"))
    assert CR not in leer_texto(str(ruta))


def test_comprobar_odt(tmp_path):
    ns = (
        'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
    )
    contenido = (
        f"<office:document-content {ns}><office:body><office:text>"
        "<text:p>Criterio <text:span>MAD.EP.MAT.C2.</text:span>CR.1.1</text:p>"
        f"<table:table><table:table-row><table:table-cell><text:p>{CO}</text:p>"
        "</table:table-cell></table:table-row></table:table>"
        "</office:text></office:body></office:document-content>"
    )
    ruta = tmp_path / "p.odt"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("content.xml", contenido)
    r = consulta.comprobar({"p.odt": leer_texto(str(ruta))})
    assert r.ficheros[0].conocidos == (CR, CO)


def test_comprobar_formato_antiguo(tmp_path, capsys):
    f = tmp_path / "a.md"
    f.write_text("Criterio MAT.1.1.C2 y la competencia CMNSC.CE1.", encoding="utf-8")
    codigo, doc = ejecutar(capsys, str(f))
    assert codigo == 1
    antiguos = {d["codigo"]: d["sugerencias"] for d in doc["ficheros"][0]["desconocidos"]}
    assert antiguos["MAT.1.1.C2"] == [CR]
    assert antiguos["CMNSC.CE1"] == ["MAD.EP.CN.C1.CE.1"]


def test_comprobar_ilegible(tmp_path, capsys):
    f = tmp_path / "roto.docx"
    f.write_bytes(b"\x00\x01esto no es un zip")
    codigo, doc = ejecutar(capsys, str(f))
    assert codigo == 2
    salida.validar(doc)
    assert doc["consulta"] == "comprobar" and doc["ficheros"] == []
    (mal,) = doc["ilegibles"]
    assert mal["fichero"] == str(f) and "roto.docx" in mal["detalle"]


def test_comprobar_inexistente_y_formato_no_admitido(tmp_path, capsys):
    codigo, doc = ejecutar(capsys, str(tmp_path / "no_existe.md"))
    assert (codigo, len(doc["ilegibles"]), doc["ficheros"]) == (2, 1, [])
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    codigo, doc = ejecutar(capsys, str(pdf))
    assert (codigo, len(doc["ilegibles"]), doc["ficheros"]) == (2, 1, [])


def test_comprobar_docx_sin_documento(tmp_path):
    ruta = tmp_path / "vacio.docx"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("otra.txt", "x")
    with pytest.raises(ErrorNormativa) as e:
        leer_texto(str(ruta))
    assert e.value.codigo == "FICHERO_ILEGIBLE"


def test_comprobar_sin_falsos_positivos():
    r = comprobar(
        "Acaba la frase en MAD. Luego EST. y p. ej. EST. 3. Véase "
        "https://www.comunidad.madrid/MAD.EP.MAT.C2.CR.9.9 y www.x.es/EST.ESO.DESC.ZZ9. "
        "También UD.3.1, ESO.1.2, Art. 6.6 y RD 157/2022."
    )
    f = r.ficheros[0]
    assert f.conocidos == () and f.desconocidos == ()


def test_comprobar_puntuacion_final():
    r = comprobar(f"Fin de frase {CR}. Entre paréntesis ({CO}), con coma {DESC}, y «{CR}»;")
    f = r.ficheros[0]
    assert f.conocidos == (CR, CO, DESC)
    assert f.desconocidos == ()


def test_comprobar_prefijo_de_codigo_valido_es_desconocido():
    r = comprobar("El criterio MAD.EP.MAT.C2.CR.1 no existe, pero MAD.EP.MAT.C2.CR.1.1 sí.")
    f = r.ficheros[0]
    assert f.conocidos == (CR,)
    assert [d.codigo for d in f.desconocidos] == ["MAD.EP.MAT.C2.CR.1"]
    assert CR in f.desconocidos[0].sugerencias


def test_comprobar_etapa_inexistente_y_ficha_inexistente():
    r = comprobar("MAD.XYZ.MAT.C2.CR.1.1 y MAD.EP.MAT.C9.CR.1.1")
    assert [d.codigo for d in r.ficheros[0].desconocidos] == [
        "MAD.XYZ.MAT.C2.CR.1.1",
        "MAD.EP.MAT.C9.CR.1.1",
    ]
    assert r.ficheros[0].desconocidos[0].sugerencias == ()


def test_comprobar_varios_ficheros_y_curso(capsys, tmp_path):
    a, b = tmp_path / "a.md", tmp_path / "b.txt"
    a.write_text(CR, encoding="utf-8")
    b.write_text("MAD.EP.MAT.C2.CR.9.9", encoding="utf-8")
    codigo, doc = ejecutar(capsys, str(a), str(b), "--curso-academico", "2026-27")
    assert codigo == 1
    assert [x["desconocidos"] == [] for x in doc["ficheros"]] == [True, False]
    assert doc["curso_academico"] == "2026-27"
    codigo, doc = ejecutar(capsys, str(a), "--curso-academico", "2031-32")
    assert (codigo, doc["error"]) == (2, "CURSO_SIN_DATOS")


def test_comprobar_salida_valida_y_ayuda():
    r = comprobar(f"{CR} MAD.EP.MAT.C2.CR.9.9")
    salida.validar(r.a_dict())
    assert "FICHERO_ILEGIBLE" in salida.CODIGOS_ERROR


def test_equivalencias_apuntan_a_elementos_que_existen():
    ruta = Path(consulta.__file__).parent / "datos" / "equivalencias-primaria-2026.json"
    tabla = json.loads(ruta.read_text(encoding="utf-8"))["equivalencias"]
    elementos = cargar().elementos
    assert tabla and all(n in elementos for nuevos in tabla.values() for n in nuevos)


def test_equivalencias_coinciden_con_el_generador(monkeypatch):
    raiz = Path(__file__).parents[1]
    monkeypatch.syspath_prepend(str(raiz))
    from herramientas.normativa.equivalencias_primaria import equivalencias

    referencia = json.loads(
        (raiz / "tests/referencia/primaria-madrid-bd89f26.json").read_text(encoding="utf-8")
    )
    ruta = raiz / "src/normativa_madrid/datos/equivalencias-primaria-2026.json"
    assert json.loads(ruta.read_text(encoding="utf-8"))["equivalencias"] == equivalencias(referencia)


def test_comprobar_un_ilegible_no_tapa_los_demas(tmp_path, capsys):
    bueno, roto, otro = tmp_path / "a.md", tmp_path / "roto.docx", tmp_path / "c.md"
    bueno.write_text(f"{CR} y MAD.EP.MAT.C2.CR.9.9", encoding="utf-8")
    roto.write_bytes(b"\x00basura")
    otro.write_text(CO, encoding="utf-8")
    codigo, doc = ejecutar(capsys, str(bueno), str(roto), str(otro))
    assert codigo == 2
    salida.validar(doc)
    assert [f["fichero"] for f in doc["ficheros"]] == [str(bueno), str(otro)]
    assert doc["ficheros"][0]["conocidos"] == [CR]
    assert doc["ficheros"][0]["desconocidos"][0]["codigo"] == "MAD.EP.MAT.C2.CR.9.9"
    assert doc["ficheros"][1]["conocidos"] == [CO]
    (mal,) = doc["ilegibles"]
    assert mal["fichero"] == str(roto) and "roto.docx" in mal["detalle"]


def test_comprobar_seis_ilegibles_salen_los_seis(tmp_path, capsys):
    rutas = [tmp_path / f"documento_con_un_nombre_bastante_largo_{n}.docx" for n in range(6)]
    for ruta in rutas:
        ruta.write_bytes(b"\x00")
    codigo, doc = ejecutar(capsys, *map(str, rutas))
    assert codigo == 2 and doc["ficheros"] == []
    salida.validar(doc)
    assert [i["fichero"] for i in doc["ilegibles"]] == [str(r) for r in rutas]
    assert all(r.name in i["detalle"] for r, i in zip(rutas, doc["ilegibles"]))


def test_comprobar_ilegible_sin_desconocidos_sigue_siendo_2(tmp_path, capsys):
    bueno, roto = tmp_path / "a.md", tmp_path / "roto.odt"
    bueno.write_text(CR, encoding="utf-8")
    roto.write_bytes(b"x")
    codigo, doc = ejecutar(capsys, str(bueno), str(roto))
    assert codigo == 2 and len(doc["ilegibles"]) == 1


def test_codigo_del_real_decreto_compartido_sugiere_todos_los_nuevos():
    r = comprobar("La competencia CMNSC.CE5 y la CMNSC.CE6.")
    sugeridas = {d.codigo: d.sugerencias for d in r.ficheros[0].desconocidos}
    assert sugeridas["CMNSC.CE5"] == ("MAD.EP.CN.C1.CE.5", "MAD.EP.CS.C1.CE.1")
    assert sugeridas["CMNSC.CE6"] == ("MAD.EP.CN.C1.CE.6", "MAD.EP.CS.C1.CE.2")


def test_codigo_de_area_sin_ciclo_sugiere_el_de_cada_ciclo():
    r = comprobar(f"{CR.replace('.C2', '')} y MAD.EP.MAT.CR.9.9")
    sugeridas = {d.codigo: d.sugerencias for d in r.ficheros[0].desconocidos}
    assert sugeridas[CR.replace(".C2", "")] == tuple(CR.replace(".C2.", f".C{n}.") for n in (1, 2, 3))
    assert sugeridas["MAD.EP.MAT.CR.9.9"] == ()
