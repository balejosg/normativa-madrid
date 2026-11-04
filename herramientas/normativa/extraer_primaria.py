"""Extrae la Primaria de Madrid (Decreto 61/2022): una ficha por área y ciclo, y los descriptores.

El anexo II del decreto es una sucesión de tablas (``COMPETENCIAS ESPECÍFICAS | CRITERIOS DE
EVALUACIÓN`` y ``CONTENIDOS``: bloque, sub-bloque y viñetas) que ``pdftotext`` mezcla al leer
por columnas, así que se leen con ``pdfplumber`` (dependencia del grupo ``mantenimiento``, que
solo se importa al leer un PDF):

- anexo I: los descriptores operativos de Madrid (``MAD.EP.DESC.CCL1``…);
- anexo II: por área y ciclo, las competencias (en la redacción de ese ciclo, que a veces
  cambia), los criterios y los contenidos;
- RD 157/2022: qué descriptores conecta cada competencia (SLE y TYR lo traen en el propio
  decreto). Ciencias de la Naturaleza y Ciencias Sociales son en el RD un área única,
  Conocimiento del Medio: sus competencias 1-6 son las del RD 1-6 y las de Sociales 1-5, las
  del RD 5-9 (``datos.equivalencia_rd``).

Fichas: ``MAD.EP.<ÁREA>.<C1|C2|C3>``; Valores Cívicos y Éticos, solo de 5.º, es
``MAD.EP.VCE`` con curso 5; Segunda Lengua Extranjera y Tecnología y Robótica, de toda la
etapa, ``MAD.EP.SLE`` y ``MAD.EP.TYR``. Las páginas son las que imprime el boletín («Pág. N»).

Cualquier tabla que no encaja (una fila con varias celdas por columna, un criterio fuera de
orden, un contenido sin viñeta ni anterior…) es un error con el área y la página: no se omite.

Uso::

    python -m herramientas.normativa.extraer_primaria --norma bocm-20220718-1 \\
        --rd boe-a-2022-3296 --cursos-academicos 2026-27 --cache <dir> [--salida <datos>]

Las funciones que interpretan las tablas trabajan sobre eventos ya leídos (filas y celdas con
su posición); las que abren el PDF son las de lectura, y solo :func:`main` escribe ficheros.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator, Sequence
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import comun

# Áreas del anexo II, en el orden del decreto. «rd» es el título del área en el RD 157/2022 y
# «desfase_rd», lo que se suma al número de la competencia para dar la del RD (CS.CE1 =
# CMNSC.CE5). «curso»: el área de un solo curso (VCE, solo en 5.º).
AREAS: tuple[dict[str, Any], ...] = (
    {"codigo": "CN", "nombre": "Ciencias de la Naturaleza", "ciclos": ("C1", "C2", "C3"),
     "rd": "Conocimiento del Medio Natural, Social y Cultural", "prefijo_rd": "CMNSC",
     "desfase_rd": 0},
    {"codigo": "CS", "nombre": "Ciencias Sociales", "ciclos": ("C1", "C2", "C3"),
     "rd": "Conocimiento del Medio Natural, Social y Cultural", "prefijo_rd": "CMNSC",
     "desfase_rd": 4},
    {"codigo": "EA", "nombre": "Educación Artística", "ciclos": ("C1", "C2", "C3"),
     "rd": "Educación Artística"},
    {"codigo": "EF", "nombre": "Educación Física", "ciclos": ("C1", "C2", "C3"),
     "rd": "Educación Física"},
    {"codigo": "LCL", "nombre": "Lengua Castellana y Literatura", "ciclos": ("C1", "C2", "C3"),
     "rd": "Lengua Castellana y Literatura"},
    {"codigo": "ING", "nombre": "Lengua Extranjera: Inglés", "ciclos": ("C1", "C2", "C3"),
     "rd": "Lengua Extranjera"},
    {"codigo": "MAT", "nombre": "Matemáticas", "ciclos": ("C1", "C2", "C3"),
     "rd": "Matemáticas"},
    {"codigo": "VCE", "nombre": "Educación en Valores Cívicos y Éticos", "ciclos": ("C3",),
     "rd": "Educación en Valores Cívicos y Éticos", "curso": "5"},
    {"codigo": "SLE", "nombre": "Segunda Lengua Extranjera", "ciclos": ("E",), "rd": None},
    {"codigo": "TYR", "nombre": "Tecnología y Robótica", "ciclos": ("E",), "rd": None},
)  # fmt: skip
_AREAS = {a["codigo"]: a for a in AREAS}

CICLOS = {"PRIMER CICLO": "C1", "SEGUNDO CICLO": "C2", "TERCER CICLO": "C3"}
ORDINAL_DEL_CICLO = {"C1": "primer", "C2": "segundo", "C3": "tercer"}
ORDINAL_DEL_CURSO = {"5": "quinto"}
FICHA_DESCRIPTORES = "MAD.EP.DESC"

_DESCRIPTOR = re.compile(r"^(CCL|CP|STEM|CD|CPSAA|CC|CE|CCEC)([0-9])\.\s+(.*)$")
_COMPETENCIA = re.compile(r"^(\d+)\.\s+(.*)$", re.DOTALL)
_CRITERIO = re.compile(r"^(\d+)\.(\d{1,2})\.?\s+(.*)$")
# Las viñetas como las da pdfplumber: «-», y los glifos sin Unicode de «•» y «–».
VINETAS = (("- ", 1), ("(cid:2) ", 2), ("(cid:3) ", 3))
_GLIFOS_DE_VINETA = {"(cid:2)": "•", "(cid:3)": "–"}
_LISTA_DESCRIPTORES = r"siguientes descriptores del [Pp]erfil de\s+salida:\s*([A-Z0-9,\s]+?)\."
_BLOQUE = re.compile(r"^([A-Z])\.\s+(\S.*)$")
_GRAN_BLOQUE = re.compile(r"^BLOQUE ([IVX]+)\s+(\S.*)$")
_SUBBLOQUE_NUMERADO = re.compile(r"^(\d+)\.\s+(\S.*)$")
_PAGINA = re.compile(r"Pág\.\s*(\d+)")

# Recortes que dejan fuera cabeceras, pies y el texto vertical del margen.
RECORTE_BOCM = (0, 95, 560, None)
RECORTE_BOE = (0, 100, 560, None)

_ANTIGUO_CE = re.compile(r"^([A-Z]+)\.CE(\d+)$")
_ANTIGUO_CR = re.compile(r"^([A-Z]+)\.(\d+)\.(\d+)\.(C[1-3]|E)$")
_ANTIGUO_DESCRIPTOR = re.compile(r"^(?:CCL|CP|STEM|CD|CPSAA|CC|CE|CCEC)[0-9]$")


class ErrorPrimaria(ValueError):
    """Una tabla del decreto que no encaja con lo esperado (con el área y la página)."""


def _fallo(mensaje: str) -> None:
    raise ErrorPrimaria(mensaje)


# --- códigos -------------------------------------------------------------------------------


def codigo_ficha(area: str, ciclo: str) -> str:
    """La ficha de un área en un ciclo (``E``: toda la etapa); VCE, de un solo curso, sin ciclo."""
    definicion = _AREAS.get(area)
    if definicion is None:
        raise ValueError(f"área desconocida «{area}»")
    if ciclo not in definicion["ciclos"]:
        raise ValueError(f"el área {area} no tiene el ciclo {ciclo}")
    if ciclo == "E" or "curso" in definicion:
        return f"MAD.EP.{area}"
    return f"MAD.EP.{area}.{ciclo}"


def codigo_nuevo(antiguo: str) -> str:
    """El código del formato común de un código antiguo de Primaria.

    ``MAT.1.1.C2`` (criterio) es ``MAD.EP.MAT.C2.CR.1.1``; ``MAT.CE1`` (competencia, común a
    los ciclos) es la competencia del primer ciclo en que aparece, ``MAD.EP.MAT.C1.CE.1``; un
    descriptor (``CCL1``) es ``MAD.EP.DESC.CCL1``. Un código que no es de Primaria es
    ``ValueError``.
    """
    if (m := _ANTIGUO_CR.match(antiguo)) is not None:
        return f"{codigo_ficha(m[1], m[4])}.CR.{int(m[2])}.{int(m[3])}"
    if (m := _ANTIGUO_CE.match(antiguo)) is not None:
        if m[1] not in _AREAS:
            raise ValueError(f"área desconocida en «{antiguo}»")
        return f"{codigo_ficha(m[1], _AREAS[m[1]]['ciclos'][0])}.CE.{int(m[2])}"
    if _ANTIGUO_DESCRIPTOR.match(antiguo):
        return f"{FICHA_DESCRIPTORES}.{antiguo}"
    raise ValueError(f"«{antiguo}» no es un código antiguo de Primaria")


# --- utilidades de texto ---------------------------------------------------------------------


def unir(a: str, b: str) -> str:
    """Une dos líneas de un mismo párrafo. Un guion al final de línea pegado a una letra es
    parte de un compuesto («sintáctico-discursivos»): se conserva y no se pone espacio."""
    a, b = a.rstrip(), b.strip()
    if not a:
        return b
    if not b:
        return a
    if a[-1] in "-–" and len(a) > 1 and a[-2].isalpha() and b[0].isalpha():
        return a + b
    return a + " " + b


def unir_lineas(texto: str) -> str:
    resultado = ""
    for linea in texto.split("\n"):
        resultado = unir(resultado, linea)
    return re.sub(r" {2,}", " ", resultado).strip()


def contenida(a: Sequence[float], b: Sequence[float]) -> bool:
    return (
        a != b and a[0] >= b[0] - 1 and a[1] >= b[1] - 1 and a[2] <= b[2] + 1 and a[3] <= b[3] + 1
    )


# --- interpretación del anexo II (pura: eventos ya leídos) ---------------------------------


class Area:
    """Lo leído de un área: competencias por ciclo, criterios y contenidos, con su página."""

    def __init__(self, definicion: dict[str, Any]) -> None:
        self.d = definicion
        self.codigo: str = definicion["codigo"]
        self.ciclo: str | None = definicion["ciclos"][0] if len(definicion["ciclos"]) == 1 else None
        self.seccion: str | None = None  # None (introducción), "competencias" o "contenidos"
        self.corte_criterios: float | None = None  # x desde la que una celda es de criterios
        self.corte_contenidos: float | None = None
        self.competencias: dict[str, dict[int, str]] = {}  # ciclo -> {número: texto}
        self.paginas_competencias: dict[str, dict[int, int]] = {}
        self.criterios: list[dict[str, Any]] = []
        self.contenidos: list[dict[str, Any]] = []
        self.paginas_bloques: dict[tuple[str, str, str | None], int] = {}
        self.comp_actual: int | None = None  # número de la competencia de la fila en curso
        self.ultimo: dict[str, Any] | None = None  # criterio o contenido en curso
        self.bloque: str | None = None
        self.subbloque: str | None = None
        self.gran_bloque: str | None = None  # «BLOQUE I Música y danza» (Educación Artística)
        self.gran_bloque_nuevo: str | None = None
        self.pagina_gran_bloque: int | None = None

    def nuevo_ciclo(self, ciclo: str) -> None:
        if len(self.d["ciclos"]) == 1:
            _fallo(f"{self.codigo}: cabecera de ciclo {ciclo} en un área de ciclo único")
        self.ciclo, self.seccion = ciclo, None
        self.bloque = self.subbloque = self.gran_bloque = self.ultimo = None

    def fila(self, pagina: int, x_tabla: float, celdas: Sequence[tuple[float, float, str]]) -> None:
        textos = [t for _, _, t in celdas if t]
        if not textos:
            return
        if len(textos) == 1 and textos[0] in CICLOS:
            self.nuevo_ciclo(CICLOS[textos[0]])
            return
        if "CRITERIOS DE EVALUACIÓN" in textos:
            x = next(x0 for x0, _, t in celdas if t == "CRITERIOS DE EVALUACIÓN")
            self.corte_criterios = x - 12
            if self.ciclo is None:
                _fallo(f"{self.codigo}: competencias sin cabecera de ciclo (pág. {pagina})")
            if self.seccion != "competencias":
                self.ultimo = None
            self.seccion = "competencias"
            return
        if textos == ["CONTENIDOS"]:
            self.seccion, self.ultimo = "contenidos", None
            self.bloque = self.subbloque = self.gran_bloque = None
            return
        if self.seccion is None:
            return  # introducción del área maquetada como tabla
        if "CONOCIMIENTOS, DESTREZAS Y ACTITUDES" in textos:
            x = next(x0 for x0, _, t in celdas if t == "CONOCIMIENTOS, DESTREZAS Y ACTITUDES")
            self.corte_contenidos = x - 12
            resto = [
                t for t in textos if t not in ("CONOCIMIENTOS, DESTREZAS Y ACTITUDES", "BLOQUES")
            ]
            if resto and re.match(r"^BLOQUE [IVX]+\b", resto[0]):
                self.gran_bloque_nuevo = unir_lineas(resto[0])
                self.pagina_gran_bloque = pagina
            elif resto:
                _fallo(
                    f"{self.codigo}: cabecera de contenidos con texto inesperado {resto} "
                    f"(pág. {pagina})"
                )
            return
        if self.seccion == "competencias":
            self.fila_competencias(pagina, celdas)
        else:
            self.fila_contenidos(pagina, x_tabla, celdas)

    def fila_competencias(self, pagina: int, celdas: Sequence[tuple[float, float, str]]) -> None:
        assert self.corte_criterios is not None and self.ciclo is not None
        izquierda = [t for x0, _, t in celdas if x0 < self.corte_criterios and t]
        derecha = [t for x0, _, t in celdas if x0 >= self.corte_criterios and t]
        if len(izquierda) > 1 or len(derecha) > 1:
            _fallo(
                f"{self.codigo}: fila de competencias con varias celdas por columna (pág. {pagina})"
            )
        comps = self.competencias.setdefault(self.ciclo, {})
        paginas = self.paginas_competencias.setdefault(self.ciclo, {})
        if izquierda:
            texto = "\n".join(izquierda)
            m = _COMPETENCIA.match(texto)
            if m:
                self.comp_actual = int(m[1])
                if self.comp_actual in comps:
                    _fallo(
                        f"{self.codigo}: competencia {m[1]} repetida en {self.ciclo} (pág. {pagina})"
                    )
                comps[self.comp_actual] = unir_lineas(m[2])
                paginas[self.comp_actual] = pagina
            elif self.comp_actual is not None:
                comps[self.comp_actual] = unir(comps[self.comp_actual], unir_lineas(texto))
            else:
                _fallo(
                    f"{self.codigo}: texto de competencia sin número (pág. {pagina}): {texto[:60]!r}"
                )
        for linea in "\n".join(derecha).split("\n") if derecha else []:
            m = _CRITERIO.match(linea.strip())
            if m:
                n, num = int(m[1]), int(m[2])
                if n != self.comp_actual:
                    _fallo(
                        f"{self.codigo}: criterio {n}.{num} bajo la competencia {self.comp_actual} "
                        f"en {self.ciclo} (pág. {pagina})"
                    )
                self.ultimo = {"n": n, "m": num, "ciclo": self.ciclo, "texto": m[3].strip(),
                               "pagina": pagina}  # fmt: skip
                self.criterios.append(self.ultimo)
            elif self.ultimo is not None and "m" in self.ultimo:
                self.ultimo["texto"] = unir(self.ultimo["texto"], linea)
            else:
                _fallo(
                    f"{self.codigo}: texto de criterio sin numeración (pág. {pagina}): {linea[:60]!r}"
                )

    def fila_contenidos(
        self, pagina: int, x_tabla: float, celdas: Sequence[tuple[float, float, str]]
    ) -> None:
        if self.corte_contenidos is None:
            _fallo(f"{self.codigo}: contenidos sin cabecera de columnas (pág. {pagina})")
        assert self.corte_contenidos is not None and self.ciclo is not None
        columna = [t for x0, _, t in celdas if x0 >= self.corte_contenidos]
        izquierda = [(x0, t) for x0, _, t in celdas if x0 < self.corte_contenidos]
        col_bloque = [t for x0, t in izquierda if x0 <= x_tabla + 10]
        col_sub = [t for x0, t in izquierda if x0 > x_tabla + 10]
        if len(columna) > 1 or len(col_bloque) > 1 or len(col_sub) > 1:
            _fallo(
                f"{self.codigo}: fila de contenidos con varias celdas por columna (pág. {pagina})"
            )
        texto = "\n".join(columna)
        bloque = unir_lineas("\n".join(col_bloque)) or None
        sub = unir_lineas("\n".join(col_sub)) or None
        lineas = [l.strip() for l in texto.split("\n") if l.strip()]
        continua = bool(lineas) and not any(lineas[0].startswith(v) for v, _ in VINETAS)

        # Fila sin contenidos: continuación del título de un «BLOQUE I/II» de Artística.
        if not lineas:
            if self.gran_bloque_nuevo is not None and (bloque or sub):
                self.gran_bloque_nuevo = unir(self.gran_bloque_nuevo, bloque or sub or "")
            elif bloque or sub:
                _fallo(
                    f"{self.codigo}: celda de bloque sin contenidos (pág. {pagina}): {bloque or sub!r}"
                )
            return
        if self.gran_bloque_nuevo is not None:
            if self.gran_bloque_nuevo != self.gran_bloque:
                self.gran_bloque, self.subbloque = self.gran_bloque_nuevo, None
                self.paginas_bloques.setdefault(
                    (self.ciclo, self.gran_bloque, None), self.pagina_gran_bloque or pagina
                )
            self.gran_bloque_nuevo = None

        # En Artística, la columna izquierda es el sub-bloque del «BLOQUE I/II».
        if self.gran_bloque is not None:
            bloque, sub = None, bloque if bloque else sub
        if bloque:
            if continua and bloque[0].islower():
                assert self.bloque is not None
                self.renombrar("bloque", unir(self.bloque, bloque))
            else:
                self.bloque, self.subbloque = bloque, None
                self.paginas_bloques.setdefault((self.ciclo, bloque, None), pagina)
        if sub:
            if continua and sub[0].islower():
                assert self.subbloque is not None
                self.renombrar("subbloque", unir(self.subbloque, sub))
            else:
                self.subbloque = sub
                if self.gran_bloque is not None:
                    self.bloque = self.gran_bloque
                if self.bloque is not None:
                    self.paginas_bloques.setdefault((self.ciclo, self.bloque, sub), pagina)
        if self.gran_bloque is not None:
            self.bloque = self.gran_bloque
        if self.bloque is None:
            _fallo(f"{self.codigo}: contenidos sin bloque (pág. {pagina})")
        if (bloque or (sub and not sub[0].islower())) and continua:
            _fallo(
                f"{self.codigo}: bloque o sub-bloque nuevo que empieza sin viñeta (pág. {pagina}): "
                f"{lineas[0][:60]!r}"
            )

        for linea in lineas:
            nivel = next((nv for v, nv in VINETAS if linea.startswith(v)), None)
            if nivel is not None:
                marca = next(v for v, nv in VINETAS if nv == nivel)
                self.ultimo = {"ciclo": self.ciclo, "bloque": self.bloque, "subbloque": self.subbloque,
                               "nivel": nivel, "texto": linea[len(marca):].strip(), "pagina": pagina}  # fmt: skip
                self.contenidos.append(self.ultimo)
            elif self.ultimo is not None and "nivel" in self.ultimo:
                self.ultimo["texto"] = unir(self.ultimo["texto"], linea)
            else:
                _fallo(
                    f"{self.codigo}: contenido sin viñeta y sin anterior (pág. {pagina}): {linea[:60]!r}"
                )

    def renombrar(self, campo: str, nuevo: str) -> None:
        """Un nombre de bloque o sub-bloque partido entre dos páginas."""
        viejo = getattr(self, campo)
        for c in self.contenidos:
            if (
                c["ciclo"] == self.ciclo
                and c[campo] == viejo
                and (campo == "bloque" or c["bloque"] == self.bloque)
            ):
                c[campo] = nuevo
        renombradas: dict[tuple[str, str, str | None], int] = {}
        for (ciclo, bloque, sub), pagina in self.paginas_bloques.items():
            if ciclo == self.ciclo and campo == "bloque" and bloque == viejo:
                renombradas[(ciclo, nuevo, sub)] = pagina
            elif (
                ciclo == self.ciclo
                and campo == "subbloque"
                and bloque == self.bloque
                and sub == viejo
            ):
                renombradas[(ciclo, bloque, nuevo)] = pagina
            else:
                renombradas[(ciclo, bloque, sub)] = pagina
        self.paginas_bloques = renombradas
        setattr(self, campo, nuevo)

    def resultado(
        self, descriptores_rd: dict[str, list[list[str]]], descriptores_decreto: list[list[str]]
    ) -> dict[str, Any]:
        """El área con sus competencias (texto del primer ciclo y variantes), criterios y
        contenidos; cada uno con su página."""
        codigo = self.codigo
        textos: dict[int, dict[str, list[str]]] = {}
        for ciclo in self.d["ciclos"]:
            comps = self.competencias.get(ciclo, {})
            if not comps:
                _fallo(f"{codigo}: no hay competencias en {ciclo}")
            for n, t in comps.items():
                textos.setdefault(n, {}).setdefault(t, []).append(ciclo)
        competencias = []
        for n in sorted(textos):
            # El decreto repite las competencias en cada ciclo y a veces cambia la redacción
            # (comas, alguna palabra, erratas). «texto» es la del primer ciclo en que aparece y
            # «variantes» guarda, por ciclo, las que difieren.
            por_ciclo = {c: t for t, ciclos in textos[n].items() for c in ciclos}
            presentes = [c for c in self.d["ciclos"] if c in por_ciclo]
            if presentes != list(self.d["ciclos"]):
                _fallo(f"{codigo}.CE{n}: solo aparece en {presentes}")
            texto = por_ciclo[presentes[0]]
            variantes = {c: t for c, t in por_ciclo.items() if t != texto}
            if self.d.get("rd"):
                n_rd = n + self.d.get("desfase_rd", 0)
                listas = descriptores_rd[self.d["rd"]]
                desc = listas[n_rd - 1] if n_rd <= len(listas) else []
                if not desc:
                    _fallo(f"{codigo}.CE{n}: sin descriptores en el RD")
            else:
                desc = descriptores_decreto[n - 1] if n <= len(descriptores_decreto) else []
            competencias.append({
                "codigo": f"{codigo}.CE{n}", "numero": n, "texto": texto,
                "variantes": dict(sorted(variantes.items())), "descriptores": desc,
                "equivalencia_rd": (f"{self.d['prefijo_rd']}.CE{n + self.d['desfase_rd']}"
                                    if "prefijo_rd" in self.d else None),
                "paginas": {c: self.paginas_competencias[c][n] for c in presentes},
            })  # fmt: skip
        if self.d.get("rd") is None and len(descriptores_decreto) != len(competencias):
            _fallo(
                f"{codigo}: {len(descriptores_decreto)} listas de descriptores en el decreto para "
                f"{len(competencias)} competencias"
            )

        criterios, vistos = [], set()
        anterior: dict[str, tuple[int, int]] = {}
        for c in self.criterios:
            cod = f"{codigo}.{c['n']}.{c['m']}.{c['ciclo']}"
            if cod in vistos:
                _fallo(f"{cod}: código repetido (pág. {c['pagina']})")
            vistos.add(cod)
            prev = anterior.get(c["ciclo"])
            esperado = [(prev[0], prev[1] + 1), (prev[0] + 1, 1)] if prev else [(1, 1)]
            if (c["n"], c["m"]) not in esperado:
                _fallo(f"{cod}: numeración no consecutiva tras {prev} (pág. {c['pagina']})")
            anterior[c["ciclo"]] = (c["n"], c["m"])
            criterios.append({"codigo": cod, "ciclo": c["ciclo"], "competencia": f"{codigo}.CE{c['n']}",
                              "texto": c["texto"], "pagina": c["pagina"]})  # fmt: skip
        bloques = [
            {"ciclo": ciclo, "bloque": bloque, "subbloque": sub, "pagina": pagina}
            for (ciclo, bloque, sub), pagina in self.paginas_bloques.items()
        ]
        return {
            "codigo": codigo, "nombre": self.d["nombre"], "ciclos": list(self.d["ciclos"]),
            "competencias": competencias, "criterios": criterios, "contenidos": self.contenidos,
            "bloques": bloques,
        }  # fmt: skip


Evento = tuple[int, tuple[Any, ...]]


def leer_anexo_ii(eventos: Iterable[Evento]) -> list[Area]:
    """Las áreas del anexo II a partir de sus eventos (títulos de área, ciclos y filas)."""
    areas: list[Area] = []
    actual: Area | None = None
    for pagina, ev in eventos:
        if ev[0] == "area":
            actual = Area(_AREAS[ev[1]])
            areas.append(actual)
        elif actual is None:
            continue
        elif ev[0] == "ciclo":
            actual.nuevo_ciclo(ev[1])
        else:
            actual.fila(pagina, ev[1], ev[2])
    if [a.codigo for a in areas] != [a["codigo"] for a in AREAS]:
        _fallo(f"áreas encontradas: {[a.codigo for a in areas]}")
    return areas


# --- de lo leído a las fichas (puro) -------------------------------------------------------


def _bloque_oficial(nombre: str, gran: bool) -> tuple[str, str]:
    """(letra o número romano impreso, título) de «A. Cultura científica» o «BLOQUE I Música…»."""
    m = (_GRAN_BLOQUE if gran else _BLOQUE).match(nombre)
    if m is None:
        raise ErrorPrimaria(f"bloque de contenidos sin letra: «{nombre}»")
    return m[1], m[2]


def _subbloque_oficial(nombre: str) -> tuple[str | None, str]:
    """El sub-bloque: su letra o número si el boletín lo imprime («A. Recepción…»), y su título."""
    for patron in (_BLOQUE, _SUBBLOQUE_NUMERADO):
        if (m := patron.match(nombre)) is not None:
            return m[1], m[2]
    return None, nombre


def _ubicacion(area: dict[str, Any], ciclo: str, apartado: str) -> str:
    if ciclo == "E" or "curso" in area:
        return f"anexo II, {area['nombre']}, {apartado}"
    return f"anexo II, {area['nombre']}, {ORDINAL_DEL_CICLO[ciclo]} ciclo, {apartado}"


def _nombre_de_ficha(area: dict[str, Any], ciclo: str) -> str:
    if "curso" in area:
        return f"{area['nombre']}, {ORDINAL_DEL_CURSO[area['curso']]} curso"
    if ciclo == "E":
        return str(area["nombre"])
    return f"{area['nombre']}, {ORDINAL_DEL_CICLO[ciclo]} ciclo"


def ficha_de_area(
    leida: dict[str, Any],
    ciclo: str,
    *,
    norma: str,
    norma_rd: str,
    cursos_academicos: Sequence[str],
) -> dict[str, Any]:
    """La ficha de un área (``resultado`` de :class:`Area`) en un ciclo."""
    area = _AREAS[leida["codigo"]]
    codigo = codigo_ficha(leida["codigo"], ciclo)
    elementos: list[dict[str, Any]] = []

    def anadir(
        sufijo: str,
        tipo: str,
        texto: str,
        pagina: int,
        apartado: str,
        *,
        oficial: str | None,
        padre: str | None = None,
        relaciones: dict[str, list[str]] | None = None,
        datos: dict[str, str] | None = None,
    ) -> str:
        elemento: dict[str, Any] = {
            "codigo": f"{codigo}.{sufijo}",
            "tipo": tipo,
            "texto": comun.normalizar(texto),
            "codigo_oficial": oficial,
            "procedencia": {
                "norma": norma,
                "ubicacion": _ubicacion(area, ciclo, apartado),
                "pagina": pagina,
            },
            "orden": len(elementos) + 1,
        }
        if padre is not None:
            elemento["padre"] = padre
        if relaciones:
            elemento["relaciones"] = relaciones
        if datos:
            elemento["datos"] = datos
        elementos.append(elemento)
        return str(elemento["codigo"])

    criterios = [c for c in leida["criterios"] if c["ciclo"] == ciclo]
    for comp in leida["competencias"]:
        n = comp["numero"]
        ce = anadir(
            f"CE.{n}",
            "competencia_especifica",
            comp["variantes"].get(ciclo, comp["texto"]),
            comp["paginas"][ciclo],
            "competencias específicas",
            oficial=str(n),
            relaciones={"descriptores": [f"{FICHA_DESCRIPTORES}.{d}" for d in comp["descriptores"]]}
            if comp["descriptores"]
            else None,
            datos={"equivalencia_rd": comp["equivalencia_rd"]} if comp["equivalencia_rd"] else None,
        )
        for c in criterios:
            n_c, m_c = c["codigo"].split(".")[1:3]
            if int(n_c) == n:
                anadir(f"CR.{n_c}.{m_c}", "criterio", c["texto"], c["pagina"], "criterios",
                       oficial=f"{n_c}.{m_c}", padre=ce)  # fmt: skip
    numeros = {comp["numero"] for comp in leida["competencias"]}
    sueltos = sorted({int(c["codigo"].split(".")[1]) for c in criterios} - numeros)
    if sueltos:
        raise ErrorPrimaria(f"{codigo}: criterios de competencias que no existen: {sueltos}")

    paginas = {
        (b["bloque"], b["subbloque"]): b["pagina"] for b in leida["bloques"] if b["ciclo"] == ciclo
    }
    gran = leida["codigo"] == "EA"
    bloques: dict[str, str] = {}  # nombre del bloque -> código
    subbloques: dict[tuple[str, str], str] = {}
    hijos: dict[str, int] = {}  # código -> hijos que lleva
    por_nivel: dict[int, str] = {}  # el último contenido de cada nivel en el contenedor actual
    contenedor = ""

    def hijo(padre: str) -> str:
        hijos[padre] = hijos.get(padre, 0) + 1
        return f"{padre}.{hijos[padre]}"

    for c in (c for c in leida["contenidos"] if c["ciclo"] == ciclo):
        nombre, sub = c["bloque"], c["subbloque"]
        if nombre not in bloques:
            letra, titulo = _bloque_oficial(nombre, gran)
            bloques[nombre] = anadir(f"CO.{letra}", "bloque_contenidos", titulo,
                                     paginas[(nombre, None)], "contenidos", oficial=letra)  # fmt: skip
        actual = bloques[nombre]
        if sub is not None:
            if (nombre, sub) not in subbloques:
                oficial, titulo = _subbloque_oficial(sub)
                n_sub = hijo(bloques[nombre]).rsplit(".", 1)[1]
                subbloques[(nombre, sub)] = anadir(
                    f"{bloques[nombre].removeprefix(codigo + '.')}.{n_sub}",
                    "bloque_contenidos",
                    titulo,
                    paginas[(nombre, sub)],
                    "contenidos",
                    oficial=oficial,
                    padre=bloques[nombre],
                )
            actual = subbloques[(nombre, sub)]
        if actual != contenedor:
            contenedor, por_nivel = actual, {}
        nivel = c["nivel"]
        padre = actual if nivel == 1 else por_nivel.get(nivel - 1)
        if padre is None:
            raise ErrorPrimaria(
                f"{codigo}: contenido de nivel {nivel} sin uno de nivel {nivel - 1} antes "
                f"(pág. {c['pagina']}): {c['texto'][:60]!r}"
            )
        nuevo = hijo(padre)
        anadir(nuevo.removeprefix(codigo + "."), "contenido", c["texto"], c["pagina"], "contenidos",
               oficial=None, padre=padre)  # fmt: skip
        por_nivel = {k: v for k, v in por_nivel.items() if k < nivel}
        por_nivel[nivel] = nuevo

    normas = [norma] if area["rd"] is None else [norma, norma_rd]
    return {
        "codigo": codigo,
        "nombre": _nombre_de_ficha(area, ciclo),
        "etapa": "primaria",
        **({"ciclo": ciclo} if ciclo != "E" and "curso" not in area else {}),
        "curso": area.get("curso"),
        "cursos_academicos": list(cursos_academicos),
        "normas": normas,
        "elementos": elementos,
    }


def ficha_de_descriptores(
    descriptores: Sequence[dict[str, Any]], *, norma: str, cursos_academicos: Sequence[str]
) -> dict[str, Any]:
    """``MAD.EP.DESC``: los descriptores operativos del anexo I del decreto."""
    return {
        "codigo": FICHA_DESCRIPTORES,
        "nombre": "Descriptores operativos de las competencias clave, Primaria",
        "etapa": "primaria",
        "curso": None,
        "cursos_academicos": list(cursos_academicos),
        "normas": [norma],
        "elementos": [
            {
                "codigo": f"{FICHA_DESCRIPTORES}.{d['codigo']}",
                "tipo": "descriptor",
                "texto": comun.normalizar(d["texto"]),
                "codigo_oficial": d["codigo"],
                "procedencia": {
                    "norma": norma,
                    "ubicacion": "anexo I, descriptores",
                    "pagina": d["pagina"],
                },
                "orden": i,
            }
            for i, d in enumerate(descriptores, start=1)
        ],
    }


def fichas_primaria(
    curriculo: dict[str, Any], *, norma: str, norma_rd: str, cursos_academicos: Sequence[str]
) -> list[dict[str, Any]]:
    """Todas las fichas: los descriptores y cada área en cada uno de sus ciclos."""
    fichas = [
        ficha_de_descriptores(
            curriculo["descriptores"], norma=norma, cursos_academicos=cursos_academicos
        )
    ]
    for leida in curriculo["areas"]:
        for ciclo in leida["ciclos"]:
            fichas.append(
                ficha_de_area(
                    leida,
                    ciclo,
                    norma=norma,
                    norma_rd=norma_rd,
                    cursos_academicos=cursos_academicos,
                )
            )
    return fichas


# --- lectura del PDF (pdfplumber) ----------------------------------------------------------


def recortar(pagina: Any, recorte: tuple[float, float, float, float | None]) -> Any:
    x0, top, x1, bottom = recorte
    return pagina.crop((x0, top, x1, bottom or pagina.height))


def pagina_impresa(pagina: Any) -> int:
    """El número que imprime la cabecera del boletín («Pág. 33»), no el orden en el PDF."""
    cabecera = pagina.crop((0, 0, pagina.width, RECORTE_BOCM[1])).extract_text() or ""
    if (m := _PAGINA.search(cabecera)) is None:
        raise ErrorPrimaria(f"la página {pagina.page_number} del PDF no trae «Pág. N»")
    return int(m[1])


def _tablas(pagina: Any) -> list[Any]:
    tablas = pagina.find_tables()
    return [t for t in tablas if not any(contenida(t.bbox, o.bbox) for o in tablas)]


def _filas(tabla: Any) -> Iterator[tuple[float, list[tuple[float, float, str]]]]:
    """Las filas de una tabla: (arriba, celdas (x0, x1, texto) de izquierda a derecha).

    pdfplumber a veces da una celda grande y, además, una fila por cada línea que contiene:
    se descartan las celdas dentro de otra ya leída (y las estrechas, de borde).
    """
    leidas: list[Sequence[float]] = []
    for fila, datos in zip(tabla.rows, tabla.extract(), strict=True):
        celdas = []
        for c, d in zip(fila.cells, datos, strict=True):
            if c is None or c[2] - c[0] < 12:
                continue
            if any(contenida(c, l) for l in leidas):
                continue
            leidas.append(c)
            celdas.append((c[0], c[2], (d or "").strip()))
        if celdas:
            yield fila.bbox[1], sorted(celdas)


def _fuera_de_tablas(pagina: Any, tablas: list[Any]) -> Any:
    def en_tabla(o: dict[str, Any]) -> bool:
        return any(
            t.bbox[0] - 1 <= o["x0"]
            and o["x1"] <= t.bbox[2] + 1
            and t.bbox[1] - 1 <= o["top"]
            and o["bottom"] <= t.bbox[3] + 1
            for t in tablas
        )

    return pagina.filter(lambda o: not (o.get("object_type") == "char" and en_tabla(o)))


def eventos_anexo_ii(pdf: Any) -> Iterator[Evento]:
    """Recorre el anexo II y da eventos ordenados: títulos de área, cabeceras de ciclo y filas
    de tabla con la posición de cada celda, con la página impresa."""
    titulos = {a["nombre"]: a["codigo"] for a in AREAS}
    dentro = False
    for pagina_entera in pdf.pages:
        pagina = recortar(pagina_entera, RECORTE_BOCM)
        texto = pagina.extract_text() or ""
        if not dentro:
            if "ANEXO II" in texto.split("\n"):
                dentro = True
            else:
                continue
        if "ANEXO III" in texto.split("\n"):
            break
        n = pagina_impresa(pagina_entera)
        tablas = _tablas(pagina)
        fuera = _fuera_de_tablas(pagina, tablas)
        eventos: list[tuple[float, int, tuple[Any, ...]]] = []
        centro = pagina_entera.width / 2
        for l in fuera.extract_text_lines():
            t = l["text"].strip()
            if t in titulos and abs((l["x0"] + l["x1"]) / 2 - centro) < 30:
                eventos.append((l["top"], 0, ("area", titulos[t])))
            elif t in CICLOS:
                eventos.append((l["top"], 0, ("ciclo", CICLOS[t])))
        for tabla in tablas:
            for arriba, celdas in _filas(tabla):
                eventos.append((arriba, 1, ("fila", tabla.bbox[0], celdas)))
        for _, _, ev in sorted(eventos, key=lambda e: (e[0], e[1])):
            yield n, ev


def extraer_descriptores(pdf: Any) -> list[dict[str, Any]]:
    """Los descriptores operativos del anexo I, con la página en que empieza cada uno."""
    lineas: list[tuple[str, int]] = []
    dentro = False
    for pagina in pdf.pages:
        texto = recortar(pagina, RECORTE_BOCM).extract_text() or ""
        for linea in texto.split("\n"):
            linea = linea.strip()
            if linea == "ANEXO I":
                dentro = True
                continue
            if linea == "ANEXO II":
                dentro = False
                break
            if dentro:
                lineas.append((linea, pagina_impresa(pagina)))
        if lineas and not dentro:
            break
    descriptores: list[dict[str, Any]] = []
    for linea, n in lineas:
        m = _DESCRIPTOR.match(linea)
        if m:
            descriptores.append({"codigo": m[1] + m[2], "competencia_clave": m[1],
                                 "texto": m[3], "pagina": n})  # fmt: skip
        elif linea == "Descriptores operativos" or re.match(r"^[a-h]\) Competencia", linea):
            continue
        elif descriptores:
            descriptores[-1]["texto"] = unir(descriptores[-1]["texto"], linea)
    if not descriptores:
        raise ErrorPrimaria("no hay descriptores en el anexo I")
    return descriptores


def extraer_descriptores_rd(pdf: Any) -> dict[str, list[list[str]]]:
    """{título del área en el RD: [[descriptores de CE1], [de CE2], …]}"""
    lineas: list[str] = []
    for pagina in pdf.pages:
        lineas += (recortar(pagina, RECORTE_BOE).extract_text() or "").split("\n")
    lineas = [l.strip() for l in lineas]
    inicio = lineas.index("ANEXO II")
    titulos = sorted({a["rd"] for a in AREAS if a["rd"]})
    posiciones = sorted((lineas.index(t, inicio), t) for t in titulos)
    resultado = {}
    for i, (pos, titulo) in enumerate(posiciones):
        fin = posiciones[i + 1][0] if i + 1 < len(posiciones) else len(lineas)
        texto = " ".join(lineas[pos:fin])
        listas = re.findall(
            r"se conecta con los siguientes descriptores del Perfil de\s+salida:"
            r"\s*([A-Z0-9,\s]+?)\.",
            texto,
        )
        resultado[titulo] = [[d.strip() for d in l.split(",") if d.strip()] for l in listas]
    for a in AREAS:
        if a["rd"] and not resultado.get(a["rd"]):
            raise ErrorPrimaria(f"RD: no hay descriptores para «{a['rd']}»")
    return resultado


def descriptores_en_decreto(pdf: Any, codigo: str) -> list[list[str]]:
    """SLE y TYR enumeran sus descriptores en el propio decreto, en la «Descripción de las
    competencias específicas del área»."""
    i = [a["codigo"] for a in AREAS].index(codigo)
    nombre = AREAS[i]["nombre"]
    siguiente = AREAS[i + 1]["nombre"] if i + 1 < len(AREAS) else "ANEXO III"
    texto = []
    dentro = False
    for pagina in pdf.pages:
        for linea in (recortar(pagina, RECORTE_BOCM).extract_text() or "").split("\n"):
            linea = linea.strip()
            if linea == nombre:
                dentro = True
            elif linea == siguiente and dentro:
                dentro = False
            elif dentro:
                texto.append(linea)
    listas = re.findall(_LISTA_DESCRIPTORES, " ".join(texto))
    return [[d.strip() for d in l.split(",") if d.strip()] for l in listas]


def extraer_curriculo(pdf_decreto: Any, pdf_rd: Any) -> dict[str, Any]:
    """Lo leído del decreto (descriptores y áreas) con los descriptores que cita el RD."""
    descriptores_rd = extraer_descriptores_rd(pdf_rd)
    descriptores = extraer_descriptores(pdf_decreto)
    areas = []
    for a in leer_anexo_ii(eventos_anexo_ii(pdf_decreto)):
        decreto = descriptores_en_decreto(pdf_decreto, a.codigo) if a.d["rd"] is None else []
        areas.append(a.resultado(descriptores_rd, decreto))
    return {"descriptores": descriptores, "areas": areas}


def _sin_glifos(texto: str) -> str:
    for glifo, vineta in _GLIFOS_DE_VINETA.items():
        texto = texto.replace(glifo, vineta)
    return texto


def columnas_de_pdf(pdf: Any) -> dict[int, list[str]]:
    """El texto de cada página impresa por columnas, para que ``comprobar`` lo compare.

    Cada columna es lo que hay a una misma x en las tablas de la página (las celdas, de arriba
    abajo, leídas como las lee el extractor) y la última, el texto fuera de las tablas. Así un
    texto que sigue en la página siguiente sigue en una columna, no tras la otra columna.
    Los glifos de viñeta sin Unicode salen como «•» y «–».
    """
    resultado: dict[int, list[str]] = {}
    for pagina_entera in pdf.pages:
        try:
            n = pagina_impresa(pagina_entera)
        except ErrorPrimaria:
            continue
        pagina = recortar(pagina_entera, RECORTE_BOCM)
        tablas = _tablas(pagina)
        celdas = sorted(
            (x0, arriba, texto)
            for tabla in tablas
            for arriba, fila in _filas(tabla)
            for x0, _, texto in fila
            if texto
        )
        grupos: list[list[tuple[float, float, str]]] = []
        for celda in celdas:  # columnas: celdas a menos de 10 puntos de x de la anterior
            if grupos and celda[0] - grupos[-1][-1][0] <= 10:
                grupos[-1].append(celda)
            else:
                grupos.append([celda])
        columnas = ["\n".join(t for _, _, t in sorted(g, key=lambda c: c[1])) for g in grupos]
        columnas.append(_fuera_de_tablas(pagina, tablas).extract_text() or "")
        resultado[n] = [_sin_glifos(c) for c in columnas]
    return resultado


def _pdfplumber() -> Any:
    try:
        import pdfplumber
    except ImportError as error:
        raise ErrorPrimaria(
            "falta pdfplumber: ejecuta con `uv run --group mantenimiento`"
        ) from error
    return pdfplumber


def columnas_de_norma(cache: Path, id_: str) -> dict[int, list[str]]:
    """:func:`columnas_de_pdf` del PDF de la caché, guardado en ``<id>.columnas.json``."""
    guardado = cache / f"{id_}.columnas.json"
    if guardado.is_file():
        bruto = json.loads(guardado.read_text(encoding="utf-8"))
        return {int(n): list(c) for n, c in bruto.items()}
    pdf = cache / f"{id_}.pdf"
    if not pdf.is_file():
        raise FileNotFoundError(f"no hay {pdf.name} en {cache}; ¿descargar.py?")
    pdfplumber = _pdfplumber()

    with pdfplumber.open(pdf) as documento:
        columnas = columnas_de_pdf(documento)
    guardado.write_text(json.dumps(columnas, ensure_ascii=False), encoding="utf-8")
    return columnas


def escribir_fichas(fichas: Iterable[dict[str, Any]], raiz: Path) -> list[Path]:
    """Escribe ``fichas/<código>.json`` bajo ``raiz``."""
    destinos = []
    for ficha in fichas:
        destino = raiz / "fichas" / f"{ficha['codigo']}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(ficha, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        destinos.append(destino)
    return destinos


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extrae la Primaria de Madrid a fichas JSON.")
    ap.add_argument("--norma", required=True, help="el decreto del currículo: bocm-20220718-1")
    ap.add_argument("--rd", required=True, help="el real decreto de mínimos: boe-a-2022-3296")
    ap.add_argument("--cursos-academicos", required=True, help="separados por comas: 2026-27")
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--salida", type=Path, help="carpeta de datos (por defecto, la del paquete)")
    args = ap.parse_args(argv)
    rutas = {id_: args.cache / f"{id_}.pdf" for id_ in (args.norma, args.rd)}
    for ruta in rutas.values():
        if not ruta.is_file():
            print(f"ERROR no hay {ruta.name} en {args.cache}; ¿descargar.py?", file=sys.stderr)
            return 1
    try:
        pdfplumber = _pdfplumber()
        with pdfplumber.open(rutas[args.norma]) as decreto, pdfplumber.open(rutas[args.rd]) as rd:
            curriculo = extraer_curriculo(decreto, rd)
        fichas = fichas_primaria(
            curriculo,
            norma=args.norma,
            norma_rd=args.rd,
            cursos_academicos=args.cursos_academicos.split(","),
        )
    except ErrorPrimaria as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    raiz = args.salida or Path(str(files("normativa_madrid").joinpath("datos")))
    for destino in escribir_fichas(fichas, raiz):
        print(destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
