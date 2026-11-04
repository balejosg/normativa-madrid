"""Vista en Markdown de una ficha o un elemento, para personas."""

from __future__ import annotations

import json
import re

import pytest

from normativa_madrid import cargar, cli, consulta, markdown

COMENTARIO = re.compile(r"<!--.*?-->")
INDICE = cargar()


def visible(texto: str) -> list[str]:
    return [COMENTARIO.sub("", linea) for linea in texto.splitlines()]


def test_md_criterio_con_numero_oficial():
    ficha = consulta.ficha("MAD.ESO.TECDIG.2", indice=INDICE)
    criterio = next(e for e in ficha.elementos if e.codigo_oficial == "1.1")
    md = markdown.ficha_md(ficha)
    assert f"**1.1** {criterio.texto}" in md


def test_md_contenidos_sin_codigo_visible():
    md = markdown.ficha_md(consulta.ficha("MAD.ESO.TECDIG.2", indice=INDICE))
    assert any(".CO." in linea for linea in md.splitlines())
    assert any("<!--" in linea and ".CO." in linea for linea in md.splitlines())
    assert not any(".CO." in linea for linea in visible(md))


def test_md_normas_con_enlace_al_pdf():
    ficha = consulta.ficha("MAD.ESO.TECDIG.2", indice=INDICE)
    md = markdown.ficha_md(ficha)
    for norma in ficha.normas:
        assert norma.url in md
    assert "Decreto 65/2022" in md


def test_md_aviso_visible_arriba():
    md = markdown.ficha_md(consulta.ficha("MAD.ESO.TECDIG.2", indice=INDICE))
    primeras = "\n".join(md.splitlines()[:6])
    assert "no están numerados" in primeras


def test_md_competencia_con_descriptores_y_criterios_debajo():
    ficha = consulta.ficha("MAD.ESO.TECDIG.2", indice=INDICE)
    lineas = markdown.ficha_md(ficha).splitlines()
    ce = next(e for e in ficha.elementos if e.codigo.endswith(".CE.1"))
    i = next(n for n, linea in enumerate(lineas) if ce.codigo in linea)
    descriptor = ce.relaciones["descriptores"][0]
    j = next(n for n, linea in enumerate(lineas) if descriptor.texto in linea and n > i)
    k = next(n for n, linea in enumerate(lineas) if ".CR.1.1" in linea)
    assert i < j < k


def test_md_primaria_anida_bloques_y_subbloques():
    ficha = consulta.ficha("MAD.EP.MAT", curso="3", indice=INDICE)
    md = markdown.ficha_md(ficha)
    por_codigo = {e.codigo: e for e in ficha.elementos}
    sub = next(
        e for e in ficha.elementos
        if e.tipo == "bloque_contenidos" and e.padre and por_codigo[e.padre].tipo == "bloque_contenidos"
    )
    lineas = md.splitlines()
    sangria = lambda c: len(next(l for l in lineas if c in l)) - len(
        next(l for l in lineas if c in l).lstrip()
    )
    assert sangria(sub.codigo) > sangria(sub.padre)


def test_md_elemento_con_procedencia():
    md = markdown.elemento_md(consulta.elemento("MAD.ESO.TECDIG.2.CR.1.1", indice=INDICE))
    assert "**1.1** " in md
    assert "Procedencia" in md and "https://" in md


@pytest.mark.parametrize("codigo", sorted(INDICE.fichas))
def test_md_renderiza_toda_ficha(codigo):
    md = markdown.ficha_md(consulta.ficha(codigo, indice=INDICE))
    assert md.startswith("# ")
    assert not any(".CO." in linea for linea in visible(md))


def test_md_ningun_elemento_se_pierde():
    for codigo in INDICE.fichas:
        ficha = consulta.ficha(codigo, indice=INDICE)
        md = markdown.ficha_md(ficha)
        for e in ficha.elementos:
            assert f"<!-- {e.codigo} -->" in md, e.codigo


def test_cli_formato_md(capsys):
    assert cli.main(["ficha", "MAD.ESO.TECDIG.2", "--formato", "md"]) == 0
    salida = capsys.readouterr().out
    assert salida.startswith("# ") and "**1.1** " in salida


def test_cli_elemento_md(capsys):
    assert cli.main(["elemento", "MAD.ESO.TECDIG.2.CR.1.1", "--formato", "md"]) == 0
    assert "Procedencia" in capsys.readouterr().out


def test_cli_formato_json_es_el_de_siempre(capsys):
    assert cli.main(["ficha", "MAD.ESO.TECDIG.2"]) == 0
    assert json.loads(capsys.readouterr().out)["consulta"] == "ficha"


def test_cli_error_sigue_en_json_con_md(capsys):
    assert cli.main(["elemento", "MAD.NO.EXISTE", "--formato", "md"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "CODIGO_DESCONOCIDO"


def test_cli_formato_invalido(capsys):
    with pytest.raises(SystemExit) as salida:
        cli.main(["ficha", "MAD.ESO.TECDIG.2", "--formato", "html"])
    assert salida.value.code == 2
