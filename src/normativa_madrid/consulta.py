"""Consultas exactas a la fuente de normativa: por código, sin interpretar nada.

Cada consulta devuelve un dataclass de :mod:`.salida` o lanza
:class:`~normativa_madrid.datos.ErrorNormativa`. Las que dependen del curso académico
(de septiembre a agosto) toman ``curso_academico`` (``None`` es el curso en vigor
según ``hoy``, que por defecto es la fecha de hoy en Europe/Madrid) y nunca caen
en silencio a otro curso: si no hay datos del pedido, es ``CURSO_SIN_DATOS`` con los
cursos que sí hay. Todas aceptan ``indice`` para consultar otros datos (los tests).
"""

from __future__ import annotations

import difflib
import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, time, timedelta, timezone
from functools import cache
from importlib.resources import files
from typing import TypedDict
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import salida
from .datos import ErrorNormativa, Indice, cargar, normalizar_cita
from .modelo import ETAPAS, NOMBRE_DEL_RANGO, Elemento, Ficha, Norma, Procedencia

__all__ = [
    "MAX_RESULTADOS",
    "buscar",
    "catalogo",
    "ciclo_de_curso",
    "comprobar",
    "curso_de",
    "elemento",
    "ficha",
    "hoy_en_madrid",
    "norma",
    "programacion",
]

MAX_RESULTADOS = 20
# Etapa de la programación -> ficha que reúne lo que la normativa exige de ella.
_FICHA_DE_PROGRAMACION = {
    "eso": "MAD.ESO.PROG",
    "bachillerato": "MAD.BACH.PROG",
    "fp": "MAD.FP.PROG",
}
_CURSO_ACADEMICO = re.compile(r"(\d{4})-(\d{2})")
_CURSOS_DE_PRIMARIA = ("1", "2", "3", "4", "5", "6")
_CICLOS_DE_PRIMARIA = ("C1", "C2", "C3")
_SUFIJO_DE_CICLO = re.compile(r"\.C[1-3]$")
MAX_SUGERENCIAS = 3
# Un código citado: «MAD.EP.MAT.C2.CR.1.1», «EST.ESO.DESC.CCL1». El punto final de una frase no
# es del código; delante no puede haber letra, cifra, punto, barra ni guion (URL, siglas).
_CITA = re.compile(r"(?<![\w./@:-])(?:MAD|EST)\.[A-Z0-9]+(?:\.[A-Za-z0-9ñ]+)+\b")
# El formato antiguo de Primaria: «MAT.1.1.C2», «CMNSC.CE1».
_CITA_ANTIGUA = re.compile(
    r"(?<![\w./@:-])(?:CN|CS|EA|EF|LCL|ING|MAT|VCE|SLE|TYR|CMNSC)"
    r"\.(?:CE\d+|\d+\.\d+\.(?:C[1-3]|E))\b"
)
_ECO = re.compile(r"[\w .,/#()«»-]{1,80}")  # lo pedido que se puede repetir en un detalle


class _Cabecera(TypedDict):
    version_datos: str
    curso_academico: str
    curso_en_vigor: bool


def ciclo_de_curso(curso: int | str) -> str:
    """El ciclo de Primaria de un curso: 1.º y 2.º son ``C1``, 3.º y 4.º ``C2``, 5.º y 6.º ``C3``."""
    texto = str(curso).strip()
    if texto not in _CURSOS_DE_PRIMARIA:
        raise ErrorNormativa(
            "CURSO_SIN_DATOS",
            f"El curso de Primaria {_eco(texto)} no existe: debe ser de 1 a 6.",
            _CURSOS_DE_PRIMARIA,
        )
    return _CICLOS_DE_PRIMARIA[(int(texto) - 1) // 2]


def _ultimo_domingo(anio: int, mes: int) -> date:
    ultimo = date(anio, mes, 31)  # marzo y octubre tienen 31 días
    return ultimo - timedelta(days=(ultimo.weekday() + 1) % 7)


def _fecha_de_madrid_sin_tzdata(ahora_utc: datetime) -> date:
    """La fecha de Madrid solo con la biblioteca estándar: UTC+1, y UTC+2 desde el último
    domingo de marzo a la 01:00 UTC hasta el último domingo de octubre a la 01:00 UTC."""
    anio = ahora_utc.year
    inicio = datetime.combine(_ultimo_domingo(anio, 3), time(1), tzinfo=timezone.utc)
    fin = datetime.combine(_ultimo_domingo(anio, 10), time(1), tzinfo=timezone.utc)
    horas = 2 if inicio <= ahora_utc < fin else 1
    return (ahora_utc + timedelta(hours=horas)).date()


def hoy_en_madrid() -> date:
    """La fecha de hoy en Europe/Madrid (sin base de zonas horarias, con la regla fija CET/CEST)."""
    try:
        return datetime.now(ZoneInfo("Europe/Madrid")).date()
    except ZoneInfoNotFoundError:
        return _fecha_de_madrid_sin_tzdata(datetime.now(timezone.utc))


def curso_de(fecha: date) -> str:
    """El curso académico de una fecha: de septiembre a agosto («2026-27»)."""
    inicio = fecha.year if fecha.month >= 9 else fecha.year - 1
    return f"{inicio}-{(inicio + 1) % 100:02d}"


# --- consultas ---------------------------------------------------------------


def catalogo(
    curso_academico: str | None = None,
    *,
    etapa: str | None = None,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.Catalogo:
    """Las materias y los módulos de un curso académico, con sus normas.

    ``etapa`` (uno de ``ETAPAS``) limita el catálogo a las fichas de esa etapa.
    """
    datos = indice or cargar()
    if etapa is not None and etapa not in ETAPAS:
        raise ErrorNormativa(
            "ETAPA_DESCONOCIDA", f"La etapa {_eco(etapa)} no es una de las admitidas.", ETAPAS
        )
    curso, vigente = _curso(curso_academico, hoy, _cursos_de_los_datos(datos))
    fichas = sorted(
        (
            f
            for f in datos.fichas.values()
            if curso in f.cursos_academicos and etapa in (None, f.etapa)
        ),
        key=lambda f: f.codigo,
    )
    return salida.Catalogo(
        **_cabecera(datos, curso, vigente),
        fichas=tuple(
            salida.FichaResumen(
                codigo=f.codigo,
                nombre=f.nombre,
                etapa=f.etapa,
                curso=f.curso,
                ciclo=f.ciclo,
                desde=_iso(f.desde),
                normas=tuple(_ref(datos, n) for n in f.normas),
            )
            for f in fichas
        ),
    )


def ficha(
    codigo: str,
    curso_academico: str | None = None,
    *,
    curso: int | str | None = None,
    ciclo: str | None = None,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.FichaSalida:
    """Todos los elementos de una materia o módulo, con su texto y su procedencia.

    ``codigo`` es el de una ficha o el de un área de Primaria (``MAD.EP.MAT``); con un
    área, ``curso`` (1 a 6 de Primaria) o ``ciclo`` (``C1`` a ``C3``) eligen la ficha.
    Ambos son distintos de ``curso_academico`` (el año escolar, «2026-27»).
    """
    datos = indice or cargar()
    f = _ficha_por_curso(datos, codigo, curso, ciclo)
    curso, vigente = _curso(curso_academico, hoy, f.cursos_academicos)
    return salida.FichaSalida(
        **_cabecera(datos, curso, vigente),
        codigo=f.codigo,
        nombre=f.nombre,
        etapa=f.etapa,
        curso=f.curso,
        ciclo=f.ciclo,
        desde=_iso(f.desde),
        normas=tuple(_ref(datos, n) for n in f.normas),
        elementos=tuple(_fragmento(datos, e) for e in f.elementos),
        avisos=_avisos(f.elementos),
    )


def elemento(
    codigo: str,
    curso_academico: str | None = None,
    *,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.ElementoSalida:
    """Un elemento por su código, con su texto, su procedencia y sus relaciones."""
    datos = indice or cargar()
    if codigo not in datos.elementos:
        raise ErrorNormativa(
            "CODIGO_DESCONOCIDO", f"No hay ningún elemento con el código {_eco(codigo)}."
        )
    f, e = datos.elementos[codigo]
    curso, vigente = _curso(curso_academico, hoy, f.cursos_academicos)
    return salida.ElementoSalida(
        **_cabecera(datos, curso, vigente),
        ficha=f.codigo,
        desde=_iso(f.desde),
        elemento=_fragmento(datos, e),
        avisos=_avisos([e]),
    )


def comprobar(
    textos: dict[str, str],
    curso_academico: str | None = None,
    *,
    ilegibles: dict[str, str] | None = None,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.Comprobacion:
    """Si los códigos que cita cada texto existen en el curso académico.

    ``textos`` va de nombre de documento a su texto (véase :mod:`.documentos`). Un código
    existente es el de un elemento o el de una ficha de ese curso; uno desconocido lleva como
    mucho :data:`MAX_SUGERENCIAS` sugerencias de la misma ficha. Un código del formato antiguo
    de Primaria es desconocido y su sugerencia es el código nuevo. ``ilegibles`` (nombre ->
    motivo) son los documentos que no se pudieron leer: salen aparte, junto a los demás.
    """
    datos = indice or cargar()
    curso, vigente = _curso(curso_academico, hoy, _cursos_de_los_datos(datos))
    existentes = _existentes(datos, curso)
    equivalencias = _equivalencias()
    ficheros = []
    usados: list[Elemento] = []
    for nombre, texto in textos.items():
        conocidos: list[str] = []
        desconocidos: list[salida.Desconocido] = []
        for codigo in _codigos_citados(texto):
            if codigo in existentes:
                conocidos.append(codigo)
                if codigo in datos.elementos:
                    usados.append(datos.elementos[codigo][1])
            elif _CITA_ANTIGUA.fullmatch(codigo):
                sugeridos = tuple(n for n in equivalencias.get(codigo, ()) if n in existentes)
                desconocidos.append(salida.Desconocido(codigo, sugeridos))
            else:
                desconocidos.append(
                    salida.Desconocido(codigo, _sugerencias(codigo, datos, existentes))
                )
        ficheros.append(salida.FicheroComprobado(nombre, tuple(conocidos), tuple(desconocidos)))
    return salida.Comprobacion(
        **_cabecera(datos, curso, vigente), ficheros=tuple(ficheros),
        ilegibles=tuple(salida.Ilegible(n, m) for n, m in (ilegibles or {}).items()),
        avisos=_avisos(usados),
    )


def _nombre_oficial(rango: str) -> str:
    """«Real Decreto», «Decreto»… en título; «Corrección de errores», solo con la inicial."""
    nombre = NOMBRE_DEL_RANGO[rango]
    return nombre[:1].upper() + nombre[1:] if rango == "correccion" else nombre.title()


def norma(
    cita: str,
    *,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.NormaSalida:
    """Una norma por su cita libre («Decreto 27/2025», «RD 405/2023»…).

    No depende del curso: la cabecera lleva el curso académico de ``hoy``. Si la cita
    es una errata publicada de la norma, ``cita_pedida`` y ``cita_correcta`` lo dicen.
    """
    datos = indice or cargar()
    if not datos.normas:
        raise ErrorNormativa("NORMATIVA_SIN_DATOS", "La fuente de normativa no trae normas.")
    clave = normalizar_cita(cita)
    id_ = datos.alias.get(clave)
    if id_ is None:
        raise ErrorNormativa("NORMA_DESCONOCIDA", f"No hay ninguna norma con la cita {_eco(cita)}.")
    n = datos.normas[id_]
    nombre = f"{NOMBRE_DEL_RANGO[n.rango]} {n.numero}"
    canonicas = {normalizar_cita(nombre)}
    if n.rango == "real_decreto":
        canonicas.add(normalizar_cita(f"rd {n.numero}"))
    pedida = None
    correcta = None
    if clave not in canonicas:
        pedida = next(c for c in n.citas if normalizar_cita(c) == clave)
        # el estilo oficial: «Decreto 27/2025», «Orden 5/2025», «Real Decreto 1/2024»
        correcta = f"{_nombre_oficial(n.rango)} {n.numero}"
    vigente = curso_de(hoy or hoy_en_madrid())
    return salida.NormaSalida(
        **_cabecera(datos, vigente, True),
        id=n.id,
        rango=n.rango,
        numero=n.numero,
        fecha=n.fecha.isoformat(),
        titulo=n.titulo,
        boletin=n.boletin,
        url_pdf=n.url_pdf,
        url_api=n.url_api,
        estado=n.estado,
        derogada_por=None if n.derogada_por is None else _ref(datos, n.derogada_por),
        desde=_iso(n.desde),
        correcciones=tuple(_correccion(datos, c) for c in n.correcciones),
        modifica=tuple(_ref(datos, m) for m in n.modifica),
        modificada_por=tuple(_ref(datos, m) for m in n.modificada_por),
        derogaciones_parciales=n.derogaciones_parciales,
        cita_pedida=pedida,
        cita_correcta=correcta,
    )


def buscar(
    texto: str,
    codigo_ficha: str | None = None,
    curso_academico: str | None = None,
    *,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.Resultados:
    """Búsqueda de texto simple: todas las palabras, sin tildes ni mayúsculas.

    Mira el texto de los elementos de una ficha o de todas las del curso; devuelve
    como mucho :data:`MAX_RESULTADOS` y ``total`` dice cuántos había.
    """
    datos = indice or cargar()
    palabras = _plano(texto).split()
    if not palabras:
        raise ErrorNormativa("TEXTO_VACIO", "Falta el texto que buscar.")
    if codigo_ficha is None:
        curso, vigente = _curso(curso_academico, hoy, _cursos_de_los_datos(datos))
        fichas = sorted(
            (f for f in datos.fichas.values() if curso in f.cursos_academicos),
            key=lambda f: f.codigo,
        )
    else:
        una = _ficha_de(datos, codigo_ficha)
        curso, vigente = _curso(curso_academico, hoy, una.cursos_academicos)
        fichas = [una]
    hallados = [
        (f, e) for f in fichas for e in f.elementos if all(p in _plano(e.texto) for p in palabras)
    ]
    return salida.Resultados(
        **_cabecera(datos, curso, vigente),
        total=len(hallados),
        avisos=_avisos([e for _, e in hallados[:MAX_RESULTADOS]]),
        resultados=tuple(
            salida.Resultado(
                codigo=e.codigo,
                ficha=f.codigo,
                tipo=e.tipo,
                texto=e.texto,
                codigo_oficial=e.codigo_oficial,
                procedencia=_procedencia(datos, e.procedencia),
            )
            for f, e in hallados[:MAX_RESULTADOS]
        ),
    )


def programacion(
    etapa: str,
    curso_academico: str | None = None,
    *,
    hoy: date | None = None,
    indice: Indice | None = None,
) -> salida.Requisitos:
    """Lo que la normativa exige de la programación de una etapa (``eso``, ``bachillerato``, ``fp``)."""
    datos = indice or cargar()
    clave = etapa.strip().lower()
    if clave not in _FICHA_DE_PROGRAMACION:
        raise ErrorNormativa(
            "ETAPA_DESCONOCIDA",
            f"La etapa {_eco(etapa)} no es una de las admitidas.",
            tuple(_FICHA_DE_PROGRAMACION),
        )
    f = _ficha_de(datos, _FICHA_DE_PROGRAMACION[clave])
    curso, vigente = _curso(curso_academico, hoy, f.cursos_academicos)
    requisitos = tuple(
        _fragmento(datos, e) for e in f.elementos if e.tipo == "requisito_programacion"
    )
    if not requisitos:
        raise ErrorNormativa(
            "NORMATIVA_SIN_DATOS",
            f"La ficha {_eco(f.codigo)} no trae ningún requisito de la programación.",
        )
    return salida.Requisitos(
        **_cabecera(datos, curso, vigente),
        etapa=clave,
        ficha=f.codigo,
        requisitos=requisitos,
        avisos=_avisos([e for e in f.elementos if e.tipo == "requisito_programacion"]),
    )


# --- piezas comunes ------------------------------------------------------------


def _eco(valor: str) -> str:
    """Lo pedido, para repetirlo en un detalle: solo si es corto y sin caracteres raros."""
    return f"«{valor}»" if _ECO.fullmatch(valor) else "pedido (no se puede mostrar)"


def _iso(fecha: date | None) -> str | None:
    return None if fecha is None else fecha.isoformat()


def _plano(texto: str) -> str:
    """Minúsculas y sin tildes, para comparar."""
    base = unicodedata.normalize("NFD", texto)
    return "".join(c for c in base if not unicodedata.combining(c)).casefold()


def _ficha_de(datos: Indice, codigo: str) -> Ficha:
    if codigo not in datos.fichas:
        raise ErrorNormativa(
            "NORMATIVA_SIN_DATOS",
            f"La fuente de normativa no trae la ficha {_eco(codigo)}.",
            tuple(sorted(datos.fichas)),
        )
    return datos.fichas[codigo]


def _area_de(f: Ficha) -> str:
    """El código del área: el de la ficha sin el sufijo de ciclo."""
    return _SUFIJO_DE_CICLO.sub("", f.codigo) if f.ciclo else f.codigo


def _rige_en(f: Ficha, curso: str | None, ciclo: str | None) -> bool:
    """Si la ficha sirve al curso o ciclo pedido: por ciclo, por curso o de toda la etapa."""
    if f.ciclo is not None:
        return ciclo in (None, f.ciclo)
    if f.curso is not None and f.etapa == "primaria":
        return (curso is None and ciclo in (None, ciclo_de_curso(f.curso))) or curso == f.curso
    return True


def _ficha_por_curso(
    datos: Indice, codigo: str, curso: int | str | None, ciclo: str | None
) -> Ficha:
    """La ficha de un código de ficha o, con un área, la que rige en el curso o ciclo pedido."""
    if curso is not None:
        curso = str(curso).strip()
        ciclo_del_curso = ciclo_de_curso(curso)
        if ciclo is not None and ciclo != ciclo_del_curso:
            raise ErrorNormativa(
                "CURSO_SIN_DATOS",
                f"El curso {_eco(curso)} no es del ciclo {_eco(ciclo)}.",
                (ciclo_del_curso,),
            )
        ciclo = ciclo_del_curso
    elif ciclo is not None and ciclo not in _CICLOS_DE_PRIMARIA:
        raise ErrorNormativa(
            "CURSO_SIN_DATOS",
            f"El ciclo {_eco(ciclo)} no existe: debe ser C1, C2 o C3.",
            _CICLOS_DE_PRIMARIA,
        )
    pedido = curso or ciclo
    if codigo in datos.fichas:
        f = datos.fichas[codigo]
        if pedido is not None and not _rige_en(f, curso, ciclo):
            raise ErrorNormativa(
                "CURSO_SIN_DATOS",
                f"La ficha {_eco(codigo)} no rige en {_eco(pedido)}.",
                tuple(x for x in (f.ciclo or f.curso,) if x),
            )
        return f
    candidatas = sorted(
        (f for f in datos.fichas.values() if _area_de(f) == codigo), key=lambda f: f.codigo
    )
    if not candidatas:
        areas = {_area_de(f) for f in datos.fichas.values()}
        raise ErrorNormativa(
            "NORMATIVA_SIN_DATOS",
            f"La fuente de normativa no trae la ficha {_eco(codigo)}.",
            tuple(sorted(areas | set(datos.fichas))),
        )
    if pedido is None:
        raise ErrorNormativa(
            "CURSO_SIN_DATOS",
            f"El área {_eco(codigo)} tiene una ficha por ciclo: indica el curso o el ciclo.",
            tuple(f.codigo for f in candidatas),
        )
    rigen = [f for f in candidatas if _rige_en(f, curso, ciclo)]
    if not rigen:
        raise ErrorNormativa(
            "CURSO_SIN_DATOS",
            f"El área {_eco(codigo)} no trae datos de {_eco(pedido)}.",
            tuple(sorted({f.ciclo or f.curso or "" for f in candidatas} - {""})),
        )
    return rigen[0]


def _cursos_de_los_datos(datos: Indice) -> tuple[str, ...]:
    if not datos.fichas:
        raise ErrorNormativa("NORMATIVA_SIN_DATOS", "La fuente de normativa no trae fichas.")
    return tuple(sorted({c for f in datos.fichas.values() for c in f.cursos_academicos}))


def _curso(pedido: str | None, hoy: date | None, disponibles: tuple[str, ...]) -> tuple[str, bool]:
    """El curso a responder y si es el que está en vigor; sin datos de él, ``CURSO_SIN_DATOS``."""
    vigente = curso_de(hoy or hoy_en_madrid())
    curso = vigente if pedido is None else pedido
    if curso not in disponibles:
        motivo = "" if _CURSO_ACADEMICO.fullmatch(curso) else " (debe ser como «2026-27»)"
        raise ErrorNormativa(
            "CURSO_SIN_DATOS",
            f"No hay datos del curso académico {_eco(curso)}{motivo}.",
            tuple(sorted(disponibles)),
        )
    return curso, curso == vigente


def _cabecera(datos: Indice, curso: str, en_vigor: bool) -> _Cabecera:
    if not datos.normas:
        raise ErrorNormativa("NORMATIVA_SIN_DATOS", "La fuente de normativa no trae normas.")
    revision = max(n.revisada for n in datos.normas.values())
    return _Cabecera(
        version_datos=revision.isoformat(), curso_academico=curso, curso_en_vigor=en_vigor
    )


def _ref(datos: Indice, id_: str) -> salida.NormaRef:
    n: Norma = datos.normas[id_]
    return salida.NormaRef(
        id=n.id,
        rango=n.rango,
        numero=n.numero,
        fecha=n.fecha.isoformat(),
        boletin=n.boletin,
        url=n.url_pdf,
    )


def _correccion(datos: Indice, referencia: str) -> salida.CorreccionSalida:
    id_, _, fragmento = referencia.partition("#")
    return salida.CorreccionSalida(norma=_ref(datos, id_), fragmento=fragmento or None)


def _procedencia(datos: Indice, p: Procedencia) -> salida.ProcedenciaSalida:
    return salida.ProcedenciaSalida(
        norma=_ref(datos, p.norma),
        ubicacion=p.ubicacion,
        pagina=p.pagina,
        via=tuple(_procedencia(datos, v) for v in p.via),
    )


def _avisos(elementos: Iterable[Elemento]) -> tuple[salida.AvisoSalida, ...]:
    """El aviso de numeración no oficial si algún elemento no lleva ``codigo_oficial``."""
    if all(e.codigo_oficial is not None for e in elementos):
        return ()
    codigo = salida.NUMERACION_NO_OFICIAL
    return (salida.AvisoSalida(codigo=codigo, detalle=salida.AVISOS[codigo]),)


def _fragmento(datos: Indice, e: Elemento) -> salida.Fragmento:
    relaciones: dict[str, tuple[salida.RelacionSalida, ...]] = {}
    for nombre, codigos in e.relaciones.items():
        relaciones[nombre] = tuple(
            salida.RelacionSalida(
                codigo=otro.codigo,
                ficha=de.codigo,
                tipo=otro.tipo,
                texto=otro.texto,
            )
            for de, otro in (datos.elementos[c] for c in codigos)
        )
    return salida.Fragmento(
        codigo=e.codigo,
        tipo=e.tipo,
        texto=e.texto,
        codigo_oficial=e.codigo_oficial,
        procedencia=_procedencia(datos, e.procedencia),
        padre=e.padre,
        orden=e.orden,
        datos=dict(e.datos),
        relaciones=relaciones,
    )


# --- comprobar -------------------------------------------------------------------


def _codigos_citados(texto: str) -> list[str]:
    """Los códigos de un texto, sin repetir y en orden de aparición."""
    primero: dict[str, int] = {}
    for m in sorted(
        [*_CITA.finditer(texto), *_CITA_ANTIGUA.finditer(texto)], key=lambda m: m.start()
    ):
        primero.setdefault(m.group(0), m.start())
    return list(primero)


def _existentes(datos: Indice, curso: str) -> frozenset[str]:
    """Los códigos citables del curso: los de sus fichas, sus elementos y las áreas de Primaria."""
    fichas = [f for f in datos.fichas.values() if curso in f.cursos_academicos]
    codigos = {f.codigo for f in fichas} | {_area_de(f) for f in fichas}
    return frozenset(codigos | {e.codigo for f in fichas for e in f.elementos})


def _sugerencias(codigo: str, datos: Indice, existentes: frozenset[str]) -> tuple[str, ...]:
    """Los códigos de la misma ficha que el desconocido: primero los que lo continúan
    (si cita solo el principio de un código), luego los más parecidos. Sin ficha, ninguno."""
    ficha = max(
        (f.codigo for f in datos.fichas.values() if codigo.startswith(f.codigo + ".")),
        key=len,
        default=None,
    )
    if ficha is None:
        return ()
    candidatos = sorted(e.codigo for e in datos.fichas[ficha].elementos if e.codigo in existentes)
    siguientes = [c for c in candidatos if c.startswith(codigo + ".")]
    parecidos = difflib.get_close_matches(codigo, candidatos, MAX_SUGERENCIAS)
    return tuple(dict.fromkeys(siguientes + parecidos))[:MAX_SUGERENCIAS]


@cache
def _equivalencias() -> dict[str, tuple[str, ...]]:
    """Código antiguo de Primaria -> códigos nuevos (``datos/equivalencias-primaria-2026.json``)."""
    nombre = "datos/equivalencias-primaria-2026.json"
    try:
        bruto = json.loads(files("normativa_madrid").joinpath(nombre).read_text(encoding="utf-8"))
        tabla = bruto["equivalencias"]
        valido = isinstance(tabla, dict) and all(
            type(k) is str and isinstance(v, list) and all(type(n) is str for n in v)
            for k, v in tabla.items()
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ErrorNormativa("DATOS_INVALIDOS", f"{nombre}: no es un JSON legible") from exc
    if not valido:
        raise ErrorNormativa("DATOS_INVALIDOS", f"{nombre}: debe ser un objeto de listas de textos")
    return {k: tuple(v) for k, v in tabla.items()}
