# Herramientas del mantenedor

Convierten el texto oficial de los boletines en los datos de `src/normativa_madrid/datos/` y
comprueban que cada texto aparece literal en la página que cita. Son solo para quien mantiene
los datos; nadie las usa al consultar.

Cómo se usan (descargar, extraer, comprobar, regenerar el lote, Primaria, la revisión externa
por materia y qué garantiza y qué no `comprobar`): [`docs/mantener-los-datos.md`](../../docs/mantener-los-datos.md).

El manifiesto del lote es `lote.toml`; las normas, `fuentes.toml`; los requisitos de la
programación, `requisitos.toml`; los fragmentos de boletín para las pruebas, `fuentes/`.
