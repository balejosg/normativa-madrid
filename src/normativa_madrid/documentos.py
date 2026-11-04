"""Lectura del texto de un documento: ``.md``, ``.txt``, ``.docx`` y ``.odt``.

Solo con la biblioteca estándar y sin red. De un ``.docx`` se leen el cuerpo, las tablas, las
notas al pie y finales, los encabezados y los pies; de un ``.odt``, su contenido. Un párrafo
se reconstruye uniendo sus trozos (``<w:t>``), porque un código puede venir partido en varios.
Cualquier fichero que no se pueda leer es ``ErrorNormativa("FICHERO_ILEGIBLE", …)``.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .datos import ErrorNormativa

__all__ = ["EXTENSIONES", "leer_texto"]

EXTENSIONES = (".docx", ".md", ".odt", ".txt")
MAX_BYTES = 50 * 1024 * 1024  # de un fichero o de lo que sale de descomprimirlo

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_T = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
# Partes de un .docx con texto, en orden de lectura.
_PARTE_DOCX = re.compile(r"word/(?:header\d*|document|footnotes|endnotes|footer\d*)\.xml")
_ORDEN_DOCX = ("header", "document", "footnotes", "endnotes", "footer")


def _ilegible(ruta: str, motivo: str) -> ErrorNormativa:
    return ErrorNormativa(
        "FICHERO_ILEGIBLE", f"No se puede leer «{Path(ruta).name}»: {motivo}.", ()
    )


def leer_texto(ruta: str) -> str:
    """El texto de un documento; ``FICHERO_ILEGIBLE`` si no existe, está dañado o no se admite."""
    extension = Path(ruta).suffix.lower()
    if extension not in EXTENSIONES:
        raise _ilegible(ruta, "formato no admitido (" + ", ".join(EXTENSIONES) + ")")
    try:
        if Path(ruta).stat().st_size > MAX_BYTES:
            raise _ilegible(ruta, "es demasiado grande")
        if extension in (".md", ".txt"):
            return Path(ruta).read_text(encoding="utf-8", errors="replace")
        with zipfile.ZipFile(ruta) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_BYTES:
                raise _ilegible(ruta, "es demasiado grande")
            return _texto_docx(z) if extension == ".docx" else _texto_odt(z)
    except ErrorNormativa:
        raise
    except (OSError, zipfile.BadZipFile, ET.ParseError, KeyError, ValueError) as exc:
        raise _ilegible(ruta, "está dañado, no existe o no es del formato que indica") from exc


def _texto_docx(z: zipfile.ZipFile) -> str:
    partes = [n for n in z.namelist() if _PARTE_DOCX.fullmatch(n)]
    if "word/document.xml" not in partes:
        raise KeyError("word/document.xml")
    partes.sort(key=lambda n: (_ORDEN_DOCX.index(re.sub(r"\d*\.xml$", "", n[5:])), n))
    lineas: list[str] = []
    for nombre in partes:
        raiz = ET.fromstring(z.read(nombre))
        for parrafo in raiz.iter(_W + "p"):
            lineas.append(_parrafo_docx(parrafo))
    return "\n".join(lineas)


def _parrafo_docx(parrafo: ET.Element) -> str:
    """Los ``<w:t>`` de un párrafo unidos; el texto borrado (``w:delText``) no cuenta."""
    trozos = []
    for el in parrafo.iter():
        if el.tag == _W + "t":
            trozos.append(el.text or "")
        elif el.tag == _W + "tab":
            trozos.append("\t")
        elif el.tag in (_W + "br", _W + "cr"):
            trozos.append("\n")
    return "".join(trozos)


def _texto_odt(z: zipfile.ZipFile) -> str:
    raiz = ET.fromstring(z.read("content.xml"))
    partes: list[str] = []

    def visita(el: ET.Element) -> None:
        if el.text:
            partes.append(el.text)
        for hijo in el:
            if hijo.tag == _T + "s":
                partes.append(" " * int(hijo.get(_T + "c", "1")))
            elif hijo.tag == _T + "tab":
                partes.append("\t")
            elif hijo.tag == _T + "line-break":
                partes.append("\n")
            else:
                visita(hijo)
            if hijo.tail:
                partes.append(hijo.tail)
        if el.tag in (_T + "p", _T + "h"):
            partes.append("\n")

    visita(raiz)
    return "".join(partes)
