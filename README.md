# normativa-madrid

La normativa educativa de la Comunidad de Madrid como fuente de datos fiable para agentes: texto literal del boletín, códigos estables y procedencia (norma, ubicación y página) de cada elemento. Solo biblioteca estándar y sin red al consultar.

Origen: el código sale del proyecto tiza (MIT, mismo autor), commit `210d608`; el extractor de Primaria, de Mint Docente (MIT, mismo autor), commit `bd89f26`.

## Qué garantiza y qué no

Garantiza (detalle en [`docs/contrato.md`](docs/contrato.md)):

- **Texto literal** del boletín (espacios y saltos de línea normalizados), comprobado contra la página que cita.
- **Procedencia** de cada elemento: norma, ubicación y página impresa del boletín (`null` si el texto viene del XML consolidado del BOE; entonces `ubicacion` da el lugar).
- **Códigos estables** (`MAD.EP.MAT.C2.CR.1.1`) y una orden, `comprobar`, que dice si los de un documento existen.
- **`codigo_oficial`** tal como lo imprime el boletín (`"1.1"`, `"a)"`), o `null` si no numera; en ese caso la respuesta lleva el aviso `NUMERACION_NO_OFICIAL` y el código no se debe presentar como oficial. No es lo mismo que `codigo`, el identificador estable de este paquete.

No garantiza:

- **Vigencia posterior a `revisada`**: los datos están revisados en esa fecha (`version_datos` en cada respuesta); lo que cambie después no está.
- **Recursos judiciales**: hay un contencioso contra el Decreto 61/2022 (Primaria) cuyo resultado no consta.
- **Cobertura**: solo lo que lista `catalogo`.

## Cobertura (curso académico 2026-27)

| Etapa | Qué trae |
|---|---|
| Primaria | Completa: Decreto 61/2022, 25 fichas `MAD.EP.*`: 24 por área y ciclo (Ciencias de la Naturaleza, Ciencias Sociales, Educación Artística, Educación Física, Inglés, Lengua Castellana y Literatura y Matemáticas, cada una en C1–C3; Educación en Valores Cívicos y Éticos en 5.º; Segunda Lengua Extranjera y Tecnología y Robótica de toda la etapa) y los descriptores del anexo I (`MAD.EP.DESC`) |
| ESO | Ciencias de la Computación 1.º y 2.º (`MAD.ESO.CCOMP`), Tecnología y Digitalización 2.º y 3.º (`MAD.ESO.TECDIG`), Digitalización 4.º (`MAD.ESO.DIG.4`), descriptores del perfil de salida (`EST.ESO.DESC`) y requisitos de la programación (`MAD.ESO.PROG`). **El resto de materias de ESO no está cargado.** |
| Bachillerato | Ciencias de la Computación I y II (`MAD.BACH.CCOMP`), descriptores (`EST.BACH.DESC`) y requisitos de la programación (`MAD.BACH.PROG`). **El resto de materias no está cargado.** |
| FP | Título de Técnico Superior en Desarrollo de Aplicaciones Multiplataforma (`MAD.DAM`) y sus módulos, con los transversales (Itinerarios, Inglés, Digitalización, Sostenibilidad) y los optativos (`MAD.CMO.*`), y los requisitos de la programación (`MAD.FP.PROG`) |

La lista exacta es `normativa-madrid catalogo`; la respuesta es la única fuente de verdad.

## Instalación

```
uv build
pip install dist/normativa_madrid-0.1.0-py3-none-any.whl
normativa-madrid catalogo --etapa primaria
```

La rueda lleva los datos dentro: no necesita red ni dependencias.

## Para agentes

```
normativa-madrid catalogo --etapa primaria
normativa-madrid ficha MAD.EP.MAT --curso 3          # Matemáticas, ciclo de 3.º
normativa-madrid ficha MAD.ESO.TECDIG.2
normativa-madrid elemento MAD.EP.MAT.C2.CR.1.1
normativa-madrid norma "Decreto 61/2022"
normativa-madrid buscar "división" --en MAD.EP.MAT.C2
normativa-madrid programacion eso
normativa-madrid comprobar programacion.docx         # sale 1 si cita un código que no existe
```

Todas admiten `--curso-academico AAAA-AA` (salvo `norma`). Cada consulta imprime un único JSON en stdout y sale con 0 (`comprobar` sale con 1 si encuentra códigos desconocidos y con 2 si no pudo leer un documento); si falla, imprime `{"error": "<CODIGO>", "detalle": ..., "disponibles": [...]}` y sale con 2. Una respuesta puede llevar `avisos`. El contrato está en [`docs/contrato.md`](docs/contrato.md) y una skill genérica para agentes, en [`skill/normativa-madrid/SKILL.md`](skill/normativa-madrid/SKILL.md).

Como biblioteca: `normativa_madrid.cargar()`, `normativa_madrid.consulta` y `normativa_madrid.salida`.

## Desarrollo

```
uv run pytest -q
```

Cómo se regeneran y revisan los datos: [`docs/mantener-los-datos.md`](docs/mantener-los-datos.md).

## Licencia

Código bajo licencia MIT. Los textos normativos no tienen derechos de autor (art. 13 del Real Decreto Legislativo 1/1996, Ley de Propiedad Intelectual).
