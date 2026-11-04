"""Vista en Markdown de una ficha o de un elemento, para leerla una persona.

Lo visible es el texto literal con su numeración oficial en negrita («**1.1** texto»). El
código estable de cada elemento va en un comentario HTML al final de su línea
(``<!-- MAD.… -->``): no se ve al leer, pero quien lea el Markdown en bruto puede citarlo.
Si el boletín no numera un elemento, su código solo aparece en ese comentario.
"""

from __future__ import annotations

import re

from .modelo import NOMBRE_DEL_RANGO
from .salida import AvisoSalida, ElementoSalida, FichaSalida, Fragmento, NormaRef, ProcedenciaSalida

__all__ = ["elemento_md", "ficha_md"]

# Cómo se titula cada tipo de elemento (los que no estén aquí salen con su nombre de tipo).
TITULOS = {
    "titulo": "Título",
    "competencia_general": "Competencia general",
    "competencia_profesional": "Competencias profesionales, personales y sociales",
    "objetivo_general": "Objetivos generales",
    "modulo": "Módulos",
    "competencia_especifica": "Competencias específicas",
    "criterio": "Criterios de evaluación",
    "bloque_contenidos": "Contenidos",
    "contenido": "Contenidos",
    "contenido_basico": "Contenidos básicos",
    "resultado_aprendizaje": "Resultados de aprendizaje",
    "criterio_fp": "Criterios de evaluación",
    "orientaciones": "Orientaciones",
    "requisito_programacion": "Requisitos de la programación",
    "descriptor": "Descriptores del perfil de salida",
}
_ESPACIOS = re.compile(r"\s+")


def _titulo_de(tipo: str) -> str:
    return TITULOS.get(tipo) or tipo.replace("_", " ").capitalize()


def _una_linea(texto: str) -> str:
    return _ESPACIOS.sub(" ", texto).strip()


def _nombre_norma(norma: NormaRef) -> str:
    return f"{NOMBRE_DEL_RANGO[norma.rango].capitalize()} {norma.numero}"


def _enlace(norma: NormaRef) -> str:
    return f"[{_nombre_norma(norma)}]({norma.url}) ({norma.boletin})"


def _aviso(avisos: tuple[AvisoSalida, ...]) -> list[str]:
    return [f"> **Aviso.** {_una_linea(a.detalle)}" for a in avisos]


def _lugar(p: ProcedenciaSalida) -> str:
    pagina = f", p. {p.pagina}" if p.pagina is not None else ""
    return f"{_enlace(p.norma)}, {p.ubicacion}{pagina}"


def _procedencia(p: ProcedenciaSalida) -> str:
    linea = f"Procedencia: {_lugar(p)}."
    for original in p.via:
        linea += f" Lugar original: {_lugar(original)}."
    return linea


def _extras(e: Fragmento) -> str:
    """Los datos propios del elemento (horas, curso, equivalencia con el real decreto…)."""
    partes = []
    for clave, valor in e.datos.items():
        if clave == "equivalencia_rd":
            partes.append(f"equivale a {valor} del real decreto")
        else:
            partes.append(f"{clave.replace('_', ' ')}: {valor}")
    return f" *({'; '.join(partes)})*" if partes else ""


def _linea(e: Fragmento, sangria: str) -> str:
    numero = f"**{_una_linea(e.codigo_oficial)}** " if e.codigo_oficial else ""
    return f"{sangria}- {numero}{_una_linea(e.texto)}{_extras(e)} <!-- {e.codigo} -->"


def _agrupar(elementos: list[Fragmento]) -> list[tuple[str, list[Fragmento]]]:
    """Por tipo, en el orden en que cada tipo aparece por primera vez."""
    grupos: dict[str, list[Fragmento]] = {}
    for e in elementos:
        grupos.setdefault(e.tipo, []).append(e)
    return list(grupos.items())


def _nodo(
    e: Fragmento, hijos: dict[str, list[Fragmento]], nivel: int, lineas: list[str]
) -> None:
    sangria = "  " * nivel
    lineas.append(_linea(e, sangria))
    interior = sangria + "  "
    for clave, relacionados in e.relaciones.items():
        if not relacionados:
            continue
        lineas.append(f"{interior}- *{clave.capitalize()}*")
        for r in relacionados:
            nombre = r.codigo.rsplit(".", 1)[-1]
            lineas.append(f"{interior}  - **{nombre}** {_una_linea(r.texto)} <!-- {r.codigo} -->")
    grupos = _agrupar(hijos.get(e.codigo, []))
    for tipo, grupo in grupos:
        base = nivel + 1
        if len(grupos) > 1:  # varios tipos bajo el mismo padre: se rotulan
            lineas.append(f"{interior}- *{_titulo_de(tipo)}*")
            base += 1
        for h in grupo:
            _nodo(h, hijos, base, lineas)


def _arbol(elementos: tuple[Fragmento, ...]) -> list[str]:
    codigos = {e.codigo for e in elementos}
    hijos: dict[str, list[Fragmento]] = {}
    raices: list[Fragmento] = []
    for e in elementos:
        if e.padre in codigos:
            hijos.setdefault(e.padre, []).append(e)
        else:
            raices.append(e)
    lineas: list[str] = []
    for tipo, grupo in _agrupar(raices):
        lineas += ["", f"## {_titulo_de(tipo)}", ""]
        for e in grupo:
            _nodo(e, hijos, 0, lineas)
    return lineas


def ficha_md(ficha: FichaSalida) -> str:
    """La ficha completa: título, avisos, normas y sus elementos por tipo, anidados por padre."""
    detalle = [ficha.etapa]
    if ficha.curso:
        detalle.append(f"curso {ficha.curso}")
    if ficha.ciclo:
        detalle.append(f"ciclo {ficha.ciclo}")
    lineas = [f"# {_una_linea(ficha.nombre)} <!-- {ficha.codigo} -->", ""]
    lineas.append(f"{', '.join(detalle)}; curso académico {ficha.curso_academico}")
    if ficha.avisos:
        lineas += [""] + _aviso(ficha.avisos)
    if ficha.normas:
        lineas += ["", "## Normas", ""]
        lineas += [f"- {_enlace(n)}" for n in ficha.normas]
    lineas += _arbol(ficha.elementos)
    lineas += ["", f"*{ficha.aviso}*", ""]
    return "\n".join(lineas)


def elemento_md(respuesta: ElementoSalida) -> str:
    """Un elemento con su texto, sus relaciones y su procedencia."""
    e = respuesta.elemento
    lineas = [f"# {_titulo_de(e.tipo)}", ""]
    if respuesta.avisos:
        lineas += _aviso(respuesta.avisos) + [""]
    _nodo(e, {}, 0, lineas)
    lineas += ["", _procedencia(e.procedencia), f"Ficha: {respuesta.ficha}", ""]
    lineas += [f"*{respuesta.aviso}*", ""]
    return "\n".join(lineas)
