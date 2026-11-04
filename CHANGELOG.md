# Cambios

## 0.1.0

Origen: trasplantado de la carpeta `normativa` de tiza en el commit `210d608`.
Origen: el extractor de Primaria (`extraer_primaria`) viene de Mint Docente, commit `bd89f26`.

- CLI `normativa-madrid` con `catalogo`, `ficha`, `elemento`, `norma`, `buscar` y `programacion`.
- Biblioteca `normativa_madrid` (`cargar`, `consulta`, `salida`).
- Datos de Primaria, ESO, Bachillerato y FP del curso académico 2026-27. Primaria (Decreto
  61/2022): una ficha por área y ciclo (VCE, solo de 5.º; SLE y TYR, de toda la etapa) y los
  descriptores del anexo I (`MAD.EP.DESC`).
- `codigo_oficial` (la numeración tal como la imprime el boletín, o `null`) y el aviso `NUMERACION_NO_OFICIAL`.
- `comprobar`: códigos citados en documentos .md, .txt, .docx y .odt, con aviso de los del formato antiguo de Primaria.
- `ficha` y `elemento` con `--formato md`.
- Documentación: `docs/contrato.md` (contrato para agentes), `docs/mantener-los-datos.md` (mantenimiento y revisión externa) y la skill `skill/normativa-madrid`.
