"""CLI ``normativa-madrid``: cada consulta imprime un único JSON en stdout.

Sale con 0 si la consulta se resuelve y con 2 si falla (el JSON es entonces el error).
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
    _anadir_curso(catalogo)
    ficha = consultas.add_parser(
        "ficha", help="todos los elementos de una materia o módulo, con su texto y su procedencia"
    )
    ficha.add_argument("codigo", help="código de la materia o módulo, p. ej. MAD.ESO.CCOMP.1")
    _anadir_curso(ficha)
    elemento = consultas.add_parser("elemento", help="un elemento por su código")
    elemento.add_argument("codigo", help="código del elemento")
    _anadir_curso(elemento)
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
    return parser


def _consulta_normativa(args, consulta):
    if args.consulta == "catalogo":
        return consulta.catalogo(args.curso_academico)
    if args.consulta == "ficha":
        return consulta.ficha(args.codigo, args.curso_academico)
    if args.consulta == "elemento":
        return consulta.elemento(args.codigo, args.curso_academico)
    if args.consulta == "norma":
        return consulta.norma(args.cita)
    if args.consulta == "buscar":
        return consulta.buscar(args.texto, args.en, args.curso_academico)
    return consulta.programacion(args.etapa, args.curso_academico)


def _sin_control(texto: str) -> str:
    """Quita los caracteres de control y de formato: un detalle no rompe el esquema de salida."""
    return "".join(c for c in texto if not unicodedata.category(c).startswith("C"))


def _escribir_json(documento: dict) -> None:
    """El documento en stdout como UTF-8, aunque la consola sea cp1252 (Windows)."""
    texto = json.dumps(documento, ensure_ascii=False, indent=1) + "\n"
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
            documento = _consulta_normativa(args, consulta).a_dict()
            salida.validar(documento)
            codigo = 0
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
