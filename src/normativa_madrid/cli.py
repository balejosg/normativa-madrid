"""CLI ``normativa-madrid``: cada consulta imprime un único JSON en stdout.

``ficha`` y ``elemento`` admiten ``--formato md``, una vista en Markdown para personas; los
errores salen siempre en JSON.

Sale con 0 si la consulta se resuelve y con 2 si falla (el JSON es entonces el error);
``comprobar`` sale con 1 si encuentra códigos desconocidos.
No usa red ni escribe ficheros.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata

__all__ = ["main"]


def _anadir_curso(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--curso-academico",
        dest="curso_academico",
        metavar="AAAA-AA",
        help="curso académico, p. ej. 2026-27 (por defecto, el de hoy)",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="normativa-madrid",
        description="Consulta la normativa educativa de Madrid por código; responde en JSON.",
    )
    consultas = parser.add_subparsers(dest="consulta", required=True, metavar="CONSULTA")
    catalogo = consultas.add_parser(
        "catalogo", help="materias y módulos del curso académico, con sus normas"
    )
    catalogo.add_argument(
        "--etapa",
        metavar="ETAPA",
        help="solo las fichas de una etapa: primaria, eso, bachillerato o fp_gs",
    )
    _anadir_curso(catalogo)
    ficha = consultas.add_parser(
        "ficha", help="todos los elementos de una materia o módulo, con su texto y su procedencia"
    )
    ficha.add_argument(
        "codigo",
        help="código de la materia o módulo, p. ej. MAD.ESO.CCOMP.1, o de un área de Primaria, "
        "p. ej. MAD.EP.MAT",
    )
    ficha.add_argument(
        "--curso",
        metavar="N",
        help="curso de Primaria (1 a 6) con el que elegir la ficha de un área; "
        "no es el curso académico",
    )
    ficha.add_argument(
        "--ciclo",
        metavar="CN",
        help="ciclo de Primaria (C1, C2 o C3) con el que elegir la ficha de un área",
    )
    _anadir_curso(ficha)
    _anadir_formato(ficha)
    elemento = consultas.add_parser("elemento", help="un elemento por su código")
    elemento.add_argument("codigo", help="código del elemento")
    _anadir_curso(elemento)
    _anadir_formato(elemento)
    norma = consultas.add_parser("norma", help="una norma por su cita, p. ej. «Decreto 27/2025»")
    norma.add_argument("cita", help="la cita de la norma")
    buscar = consultas.add_parser("buscar", help="busca un texto en los elementos del curso")
    buscar.add_argument("texto", help="palabras que buscar (sin distinguir tildes ni mayúsculas)")
    buscar.add_argument(
        "--en",
        dest="en",
        metavar="CODIGO",
        help="limita la búsqueda a una materia o módulo",
    )
    _anadir_curso(buscar)
    programacion = consultas.add_parser(
        "programacion", help="lo que la normativa exige de la programación de una etapa"
    )
    programacion.add_argument("etapa", help="eso, bachillerato o fp")
    _anadir_curso(programacion)
    comprobar = consultas.add_parser(
        "comprobar",
        help="comprueba que los códigos citados en uno o más documentos existen; "
        "sale con 1 si hay desconocidos",
    )
    comprobar.add_argument(
        "ficheros", nargs="+", metavar="FICHERO", help="documento .md, .txt, .docx o .odt"
    )
    _anadir_curso(comprobar)
    return parser


def _anadir_formato(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--formato",
        choices=("json", "md"),
        default="json",
        help="json (por defecto) o md, una vista en Markdown para personas; "
        "los errores salen siempre en JSON con código de salida 2",
    )


def _consulta_normativa(args, consulta):
    from . import ErrorNormativa

    if args.consulta == "catalogo":
        return consulta.catalogo(args.curso_academico, etapa=args.etapa)
    if args.consulta == "ficha":
        return consulta.ficha(
            args.codigo, args.curso_academico, curso=args.curso, ciclo=args.ciclo
        )
    if args.consulta == "elemento":
        return consulta.elemento(args.codigo, args.curso_academico)
    if args.consulta == "norma":
        return consulta.norma(args.cita)
    if args.consulta == "buscar":
        return consulta.buscar(args.texto, args.en, args.curso_academico)
    if args.consulta == "comprobar":
        from .documentos import leer_texto

        textos: dict[str, str] = {}
        ilegibles: dict[str, str] = {}
        for ruta in args.ficheros:
            try:
                textos[ruta] = leer_texto(ruta)
            except ErrorNormativa as error:
                ilegibles[ruta] = _sin_control(error.detalle)
        if ilegibles and not textos:  # ninguno legible: el error, con todos los nombres
            raise ErrorNormativa("FICHERO_ILEGIBLE", " ".join(ilegibles.values()))
        return consulta.comprobar(textos, args.curso_academico, ilegibles=ilegibles)
    return consulta.programacion(args.etapa, args.curso_academico)


def _sin_control(texto: str) -> str:
    """Quita los caracteres de control y de formato: un detalle no rompe el esquema de salida."""
    return "".join(c for c in texto if not unicodedata.category(c).startswith("C"))


def _escribir_json(documento: dict) -> None:
    _escribir(json.dumps(documento, ensure_ascii=False, indent=1) + "\n")


def _escribir(texto: str) -> None:
    """El texto en stdout como UTF-8, aunque la consola sea cp1252 (Windows)."""
    flujo = sys.stdout
    buffer = getattr(flujo, "buffer", None)
    if buffer is None:
        flujo.write(texto)
        return
    flujo.flush()
    buffer.write(texto.encode("utf-8"))
    buffer.flush()


def _normativa(args) -> int:
    """Una consulta: un único JSON en stdout y 0, o 2 si falla."""
    from . import ErrorNormativa, consulta, salida

    try:
        try:
            respuesta = _consulta_normativa(args, consulta)
            documento = respuesta.a_dict()
            salida.validar(documento)
            codigo = getattr(respuesta, "codigo_salida", 0)
            if getattr(args, "formato", "json") == "md":
                from . import markdown

                vista = markdown.ficha_md if args.consulta == "ficha" else markdown.elemento_md
                _escribir(vista(respuesta))
                return codigo
        except ErrorNormativa as error:
            limpio = ErrorNormativa(
                error.codigo,
                _sin_control(error.detalle),
                tuple(_sin_control(d) for d in error.disponibles),
            )
            documento = salida.error_a_dict(limpio)
            codigo = 2
    except salida.ErrorSalida:
        documento = {"error": "SALIDA_INVALIDA", "detalle": "", "disponibles": []}
        codigo = 2
    _escribir_json(documento)
    return codigo


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return _normativa(args)
