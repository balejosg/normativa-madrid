# Instrucciones para desarrollar en normativa-madrid

- Todo en español: código, mensajes, documentación y commits.
- Entorno con `uv`; pruebas con `uv run pytest -q`.
- En ejecución solo se usa la biblioteca estándar y no hay red. Las dependencias de mantenimiento (`pdfplumber`) van en el grupo `mantenimiento`.
- El texto normativo es literal del boletín: no se corrige a mano. Los errores oficiales se anotan en `via`.
- Todo elemento lleva `procedencia` (`norma`, `ubicacion`, `pagina`).
- El paquete es independiente de cualquier producto: `tests/test_independencia.py` lo comprueba.
- Las herramientas de `herramientas/normativa/` regeneran los datos (ver su README); las pruebas que necesitan la caché de PDFs o la red se omiten si no están disponibles.
- Commits terminan con la línea `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. No se hace push sin permiso.
