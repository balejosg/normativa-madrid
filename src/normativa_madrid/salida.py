"""Salida de las consultas de normativa: esquema cerrado.

Lo que la CLI imprime para el agente se construye solo con los dataclasses de este
módulo y ``a_dict()``, y pasa por :func:`validar`: cualquier clave que no esté en el
esquema, a cualquier nivel, o un valor de otro tipo se rechaza. Los textos que salen
son los de los datos de normativa o los fijos de este paquete (:data:`AVISO`,
:data:`INDICE_PROGRAMACION`); lo único que viene de fuera es, en ``comprobar``, el nombre del
documento y los códigos que cita (que casan con un patrón estricto).

Cada respuesta lleva la misma cabecera: ``consulta`` (cuál se hizo),
``version_datos`` (la revisión más reciente de los datos), ``curso_academico``,
``curso_en_vigor`` y ``aviso``. Un error se imprime con :func:`error_a_dict`.
"""

from __future__ import annotations

import re
import types
import typing
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, ClassVar, Union, get_args, get_origin

from .datos import ErrorNormativa, primer_invisible

__all__ = [
    "AVISO",
    "CODIGOS_ERROR",
    "INDICE_PROGRAMACION",
    "AVISOS",
    "NUMERACION_NO_OFICIAL",
    "AvisoSalida",
    "Catalogo",
    "Comprobacion",
    "CorreccionSalida",
    "Desconocido",
    "ElementoSalida",
    "ErrorSalida",
    "FicheroComprobado",
    "Ilegible",
    "FichaResumen",
    "FichaSalida",
    "Fragmento",
    "NormaRef",
    "NormaSalida",
    "ProcedenciaSalida",
    "RelacionSalida",
    "Requisitos",
    "Resultado",
    "Resultados",
    "Respuesta",
    "a_dict",
    "error_a_dict",
    "validar",
]

AVISO = "Texto literal del boletín. Cita siempre el código y la procedencia."
INDICE_PROGRAMACION = (
    "Cuando ninguna norma fija el índice de la programación, lo fija la plantilla del centro."
)

# Los avisos que puede llevar una respuesta: código -> detalle fijo.
NUMERACION_NO_OFICIAL = "NUMERACION_NO_OFICIAL"
AVISOS = {
    NUMERACION_NO_OFICIAL: (
        "Estos elementos no están numerados en el boletín; su código es estable pero no "
        "oficial: no lo presentes como numeración oficial"
    ),
}

# Los códigos de error de una consulta: solo estos salen en un error impreso.
CODIGOS_ERROR = frozenset(
    {
        "CODIGO_DESCONOCIDO",
        "CURSO_SIN_DATOS",
        "DATOS_INVALIDOS",
        "ETAPA_DESCONOCIDA",
        "FICHERO_ILEGIBLE",
        "NORMA_DESCONOCIDA",
        "NORMATIVA_SIN_DATOS",
        "SALIDA_INVALIDA",
        "TEXTO_VACIO",
    }
)
MAX_DETALLE = 300

_CODIGO = re.compile(r"[A-Z][A-Z0-9_]{1,39}")
_FECHA = re.compile(r"\d{4}-\d{2}-\d{2}")
_CURSO_ACADEMICO = re.compile(r"\d{4}-\d{2}")


class ErrorSalida(Exception):
    """Un documento de salida que no cumple el esquema cerrado."""

    def __init__(self, codigo: str, detalle: str) -> None:
        super().__init__(f"{codigo}: {detalle}")
        self.codigo = codigo
        self.detalle = detalle


# --- piezas ------------------------------------------------------------------


@dataclass(frozen=True)
class NormaRef:
    """Una norma citada: lo justo para citarla y encontrarla en el boletín."""

    id: str
    rango: str
    numero: str
    fecha: str
    boletin: str
    url: str


@dataclass(frozen=True)
class ProcedenciaSalida:
    """De qué norma y de qué lugar sale un texto; ``via`` es el lugar original si lo modifica otra."""

    norma: NormaRef
    ubicacion: str
    pagina: int | None
    via: tuple[ProcedenciaSalida, ...]


@dataclass(frozen=True)
class RelacionSalida:
    """Un elemento al que apunta otro (un descriptor, por ejemplo), con su texto."""

    codigo: str
    ficha: str
    tipo: str
    texto: str


@dataclass(frozen=True)
class AvisoSalida:
    """Un aviso de la respuesta: ``codigo`` es uno de :data:`AVISOS` y ``detalle`` su texto fijo."""

    codigo: str
    detalle: str


@dataclass(frozen=True)
class Fragmento:
    """Un elemento de una ficha: su texto, su procedencia y sus relaciones resueltas."""

    codigo: str
    tipo: str
    texto: str
    codigo_oficial: str | None
    procedencia: ProcedenciaSalida
    padre: str | None
    orden: int
    datos: dict[str, int | str]
    relaciones: dict[str, tuple[RelacionSalida, ...]]


@dataclass(frozen=True)
class FichaResumen:
    """Una materia o un módulo en el catálogo."""

    codigo: str
    nombre: str
    etapa: str
    curso: str | None
    ciclo: str | None
    desde: str | None
    normas: tuple[NormaRef, ...]


@dataclass(frozen=True)
class CorreccionSalida:
    """Una corrección de errores; ``fragmento`` si lo es de una disposición concreta."""

    norma: NormaRef
    fragmento: str | None


@dataclass(frozen=True)
class Resultado:
    """Un elemento encontrado por :func:`consulta.buscar`."""

    codigo: str
    ficha: str
    tipo: str
    texto: str
    codigo_oficial: str | None
    procedencia: ProcedenciaSalida


@dataclass(frozen=True)
class Desconocido:
    """Un código citado que no existe, con los existentes que pueden ser el que se quiso citar."""

    codigo: str
    sugerencias: tuple[str, ...]


@dataclass(frozen=True)
class FicheroComprobado:
    """Los códigos de un documento: los que existen y los que no (``fichero`` es el pedido)."""

    fichero: str
    conocidos: tuple[str, ...]
    desconocidos: tuple[Desconocido, ...]


@dataclass(frozen=True)
class Ilegible:
    """Un documento que no se pudo leer y por qué (``detalle`` es un texto fijo de este paquete)."""

    fichero: str
    detalle: str


# --- respuestas --------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Respuesta:
    """La cabecera común de toda respuesta."""

    CONSULTA: ClassVar[str]
    FIJOS: ClassVar[dict[str, str]] = {}

    version_datos: str
    curso_academico: str
    curso_en_vigor: bool
    aviso: str = AVISO
    avisos: tuple[AvisoSalida, ...] = ()

    def a_dict(self) -> dict[str, Any]:
        """El documento que se imprime: ``consulta`` y los campos, sin nada más."""
        return {"consulta": self.CONSULTA, **a_dict(self)}


@dataclass(frozen=True, kw_only=True)
class Catalogo(Respuesta):
    CONSULTA = "catalogo"

    fichas: tuple[FichaResumen, ...]


@dataclass(frozen=True, kw_only=True)
class FichaSalida(Respuesta):
    CONSULTA = "ficha"

    codigo: str
    nombre: str
    etapa: str
    curso: str | None
    ciclo: str | None
    desde: str | None
    normas: tuple[NormaRef, ...]
    elementos: tuple[Fragmento, ...]


@dataclass(frozen=True, kw_only=True)
class ElementoSalida(Respuesta):
    CONSULTA = "elemento"

    ficha: str
    desde: str | None
    elemento: Fragmento


@dataclass(frozen=True, kw_only=True)
class NormaSalida(Respuesta):
    CONSULTA = "norma"

    id: str
    rango: str
    numero: str
    fecha: str
    titulo: str
    boletin: str
    url_pdf: str
    url_api: str | None
    estado: str
    derogada_por: NormaRef | None
    desde: str | None
    correcciones: tuple[CorreccionSalida, ...]
    modifica: tuple[NormaRef, ...]
    modificada_por: tuple[NormaRef, ...]
    derogaciones_parciales: tuple[str, ...]
    cita_pedida: str | None
    cita_correcta: str | None


@dataclass(frozen=True, kw_only=True)
class Resultados(Respuesta):
    CONSULTA = "buscar"

    total: int
    resultados: tuple[Resultado, ...]


@dataclass(frozen=True, kw_only=True)
class Requisitos(Respuesta):
    CONSULTA = "programacion"
    FIJOS = {"indice": INDICE_PROGRAMACION}

    etapa: str
    ficha: str
    requisitos: tuple[Fragmento, ...]
    indice: str = INDICE_PROGRAMACION


@dataclass(frozen=True, kw_only=True)
class Comprobacion(Respuesta):
    CONSULTA = "comprobar"

    ficheros: tuple[FicheroComprobado, ...]
    ilegibles: tuple[Ilegible, ...] = ()

    @property
    def codigo_salida(self) -> int:
        """2 si algún documento no se pudo leer, si no 1 si algún código es desconocido, si no 0.

        ``ficheros`` trae los documentos leídos y ``ilegibles`` los que no. Si no se pudo leer
        ninguno, la CLI imprime en su lugar el error ``FICHERO_ILEGIBLE`` con todos sus nombres.
        """
        if self.ilegibles:
            return 2
        return 1 if any(f.desconocidos for f in self.ficheros) else 0


_RESPUESTAS: dict[str, type[Respuesta]] = {
    clase.CONSULTA: clase
    for clase in (
        Catalogo,
        FichaSalida,
        ElementoSalida,
        NormaSalida,
        Resultados,
        Requisitos,
        Comprobacion,
    )
}


# --- del dataclass al documento -----------------------------------------------


def a_dict(valor: Any) -> Any:
    """Convierte dataclasses, tuplas y diccionarios en objetos JSON (sin la ``consulta``)."""
    if is_dataclass(valor) and not isinstance(valor, type):
        return {f.name: a_dict(getattr(valor, f.name)) for f in fields(valor)}
    if isinstance(valor, (tuple, list)):
        return [a_dict(v) for v in valor]
    if isinstance(valor, dict):
        return {k: a_dict(v) for k, v in valor.items()}
    return valor


def error_a_dict(error: ErrorNormativa) -> dict[str, Any]:
    """El documento de un error: ``error``, ``detalle`` y ``disponibles``, ya validado."""
    documento = {
        "error": error.codigo,
        "detalle": error.detalle[:MAX_DETALLE],
        "disponibles": list(error.disponibles),
    }
    validar(documento)
    return documento


# --- validación --------------------------------------------------------------


def validar(documento: Any) -> None:
    """Comprueba que un documento de salida (respuesta o error) cumple el esquema cerrado."""
    if not isinstance(documento, dict):
        raise ErrorSalida("TIPO_INCORRECTO", "la salida debe ser un objeto")
    if "error" in documento:
        _validar_error(documento)
        return
    consulta = documento.get("consulta")
    clase = _RESPUESTAS.get(consulta) if isinstance(consulta, str) else None
    if clase is None:
        raise ErrorSalida("VALOR_NO_PERMITIDO", "la consulta no es una de las conocidas")
    resto = {k: v for k, v in documento.items() if k != "consulta"}
    _comprobar(resto, clase, clase.CONSULTA)
    if resto["aviso"] != AVISO:
        raise ErrorSalida("VALOR_NO_PERMITIDO", "el aviso no es el fijo")
    for clave, fijo in clase.FIJOS.items():
        if resto[clave] != fijo:
            raise ErrorSalida("VALOR_NO_PERMITIDO", f"{clave} no es el texto fijo")
    for i, a in enumerate(resto["avisos"]):
        if AVISOS.get(a["codigo"]) != a["detalle"]:
            raise ErrorSalida("VALOR_NO_PERMITIDO", f"avisos[{i}]: no es uno de los avisos fijos")
    if not _FECHA.fullmatch(resto["version_datos"]):
        raise ErrorSalida("VALOR_NO_PERMITIDO", "version_datos debe ser una fecha ISO")
    if not _CURSO_ACADEMICO.fullmatch(resto["curso_academico"]):
        raise ErrorSalida("VALOR_NO_PERMITIDO", "curso_academico debe ser como «2026-27»")


def _validar_error(documento: dict[str, Any]) -> None:
    claves = {"error", "detalle", "disponibles"}
    if set(documento) != claves:
        extra = sorted(set(documento) ^ claves)
        raise ErrorSalida(
            "CLAVE_NO_PERMITIDA", f"error: claves distintas de las del esquema {extra}"
        )
    codigo = documento["error"]
    if not isinstance(codigo, str) or not _CODIGO.fullmatch(codigo) or codigo not in CODIGOS_ERROR:
        raise ErrorSalida("VALOR_NO_PERMITIDO", "el código de error no está registrado")
    detalle = documento["detalle"]
    if (
        not isinstance(detalle, str)
        or len(detalle) > MAX_DETALLE
        or primer_invisible(detalle) is not None
    ):
        raise ErrorSalida("VALOR_NO_PERMITIDO", "el detalle debe ser un texto corto de una línea")
    disponibles = documento["disponibles"]
    if not isinstance(disponibles, list) or not all(
        type(d) is str and primer_invisible(d) is None for d in disponibles
    ):
        raise ErrorSalida("TIPO_INCORRECTO", "disponibles debe ser una lista de textos")


def _comprobar(valor: Any, tipo: Any, ruta: str) -> None:
    """Comprueba ``valor`` contra la anotación ``tipo``: claves y tipos exactos, a todo nivel."""
    origen = get_origin(tipo)
    if tipo is type(None):
        if valor is not None:
            raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: debe ser nulo")
    elif tipo is bool or tipo is int:
        if type(valor) is not tipo:
            raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: debe ser {tipo.__name__}")
    elif tipo is str:
        if type(valor) is not str:
            raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: debe ser texto")
        if primer_invisible(valor) is not None:
            raise ErrorSalida("VALOR_NO_PERMITIDO", f"{ruta}: el texto lleva caracteres de control")
    elif origen is Union or origen is types.UnionType:
        errores: list[ErrorSalida] = []
        for opcion in get_args(tipo):
            try:
                _comprobar(valor, opcion, ruta)
                return
            except ErrorSalida as exc:
                errores.append(exc)
        raise (
            errores[0]
            if len(errores) == 1
            else ErrorSalida("TIPO_INCORRECTO", f"{ruta}: no es de ninguno de los tipos permitidos")
        )
    elif origen is tuple:
        if not isinstance(valor, list):
            raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: debe ser una lista")
        for i, v in enumerate(valor):
            _comprobar(v, get_args(tipo)[0], f"{ruta}[{i}]")
    elif origen is dict:
        if not isinstance(valor, dict):
            raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: debe ser un objeto")
        for clave, v in valor.items():
            _comprobar(clave, str, f"{ruta}.{clave}")
            _comprobar(v, get_args(tipo)[1], f"{ruta}.{clave}")
    elif isinstance(tipo, type) and is_dataclass(tipo):
        if not isinstance(valor, dict):
            raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: debe ser un objeto")
        anotaciones = typing.get_type_hints(tipo)
        permitidas = [f.name for f in fields(tipo)]
        for clave in valor:
            if clave not in permitidas:
                raise ErrorSalida("CLAVE_NO_PERMITIDA", f"{ruta}: clave «{clave}» no permitida")
        for nombre in permitidas:
            if nombre not in valor:
                raise ErrorSalida("FALTA_CLAVE", f"{ruta}: falta «{nombre}»")
            _comprobar(valor[nombre], anotaciones[nombre], f"{ruta}.{nombre}")
    else:  # un tipo que el esquema no sabe comprobar es un fallo del esquema, no de la salida
        raise ErrorSalida("TIPO_INCORRECTO", f"{ruta}: el esquema no admite {tipo}")
