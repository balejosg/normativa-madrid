"""Qué hacer ante cada código de error de las consultas de normativa."""

from __future__ import annotations

__all__ = ["AYUDA", "explicar"]

AYUDA: dict[str, str] = {
    "DATOS_INVALIDOS": (
        "Los datos de normativa no cumplen su formato: el detalle nombra el fichero y el campo. "
        "Es un fallo de la instalación o de una edición a mano: reinstala o actualiza "
        "normativa-madrid."
    ),
    "NORMATIVA_SIN_DATOS": (
        "normativa-madrid no trae esa materia o ese módulo. La lista de «disponibles» dice cuáles "
        "sí trae; para lo demás, consulta la norma en el boletín."
    ),
    "CURSO_SIN_DATOS": (
        "normativa-madrid no trae datos de ese curso académico. La lista de «disponibles» dice de "
        "cuáles sí; no los sustituyas por los de otro curso sin avisar a quien consulta."
    ),
    "CODIGO_DESCONOCIDO": (
        "No hay ningún elemento con ese código. Busca el código exacto con la consulta de la "
        "ficha o con una búsqueda de texto."
    ),
    "NORMA_DESCONOCIDA": (
        "normativa-madrid no tiene esa norma. Prueba con otra forma de citarla (por ejemplo "
        "«Decreto 27/2025» o «RD 405/2023») o consulta el boletín."
    ),
    "ETAPA_DESCONOCIDA": "La etapa debe ser eso, bachillerato o fp.",
    "TEXTO_VACIO": "Falta el texto que buscar: escribe al menos una palabra.",
    "SALIDA_INVALIDA": (
        "La respuesta de la consulta no cumple el formato de salida: no la uses. Es un fallo de "
        "normativa-madrid; avisa a quien la mantiene con este código."
    ),
}


def explicar(codigo: str) -> str | None:
    """El texto de ayuda de un código de error, o ``None`` si no se conoce."""
    return AYUDA.get(codigo)
