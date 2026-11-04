# Mantener los datos de normativa-madrid

Las herramientas de `herramientas/normativa/` convierten el texto oficial de los boletines (PDF del BOCM con `pdftotext -layout`, XML
consolidado del BOE) en los JSON que carga `normativa_madrid` y comprueba que cada texto
guardado aparece literal en la página que cita. **Es solo para quien mantiene los datos:
ni los docentes ni sus agentes la usan.** Necesita `pdftotext` (poppler) para los PDF.

Su `README.md` solo remite a este documento. Se ejecutan desde la raíz del repositorio, con `uv run python -m herramientas.normativa.<módulo>`.
La lista de normas (`fuentes.toml`: id, URL, `sha256`, correcciones, `recuentos`,
`sustituciones` y `cifrado`) vive en `herramientas/normativa/`; sus comentarios explican cada decisión (qué toca
cada corrección o modificación, de dónde sale el texto cuando el PDF no sirve).

## Orden de trabajo: descargar, extraer, comprobar

**Regenerar todo el lote**: `lote.toml` es el manifiesto de las 70 fichas del paquete (extractor y
parámetros exactos de cada una, más la fecha de revisión y los cursos académicos). Orden:

1. `descargar --cache <dir>` (caché fuera del repositorio).
2. `uv run --group mantenimiento python -m herramientas.normativa.regenerar --cache <dir>
   [--salida <datos>]`: escribe las normas, los descriptores, el resto de fichas, la Primaria y los
   requisitos, en ese orden, y para en el primer error. Para preparar un curso nuevo se cambian en
   `lote.toml` (y `fuentes.toml`) las normas, los cursos y la fecha. El grupo `mantenimiento`
   trae pdfplumber, que necesitan la Primaria y su comprobación.
3. **`comprobar --cache <dir>`** (también con `--group mantenimiento`), siempre después de
   regenerar, y a 0 antes de commitear datos.

Los pasos de abajo son lo que `regenerar` hace por dentro, para extraer una sola ficha.

1. **Descargar**: `descargar --cache <dir>` baja cada `url_pdf` y comprueba su `sha256`; si
   no coincide, para y no sobrescribe nada. Las normas con `url_api` bajan también su XML
   consolidado. La caché (`<id>.pdf`, `<id>.txt`, `<id>.xml`) **va fuera del repositorio**
   y **nunca se commitean los PDF**
   (salvo el PDF mínimo de `fuentes/bocm-20250827-6_cifrado.pdf`, para los tests).
2. **Normas**: `normas --revisada AAAA-MM-DD [--salida <datos>]` escribe `normas/<id>.json`
   de cada norma de `fuentes.toml` (sin `recuentos` ni `sustituciones`, con la fecha de la
   revisión). Se repite cuando cambia `fuentes.toml`.
3. **Extraer**, según la fuente (escriben `fichas/<código>.json` en `src/normativa_madrid/datos`,
   o donde diga `--salida`):
   - `extraer_descriptores --norma <id> --etapa <eso|bachillerato> --cursos-academicos …
     --cache <dir>` (toma de las tablas del anexo I la columna de la etapa):
     **primero**, antes de cualquier materia. Las relaciones entre fichas (los descriptores
     que cita cada competencia) se validan entre fichas al cargar, y una materia sin la
     ficha de descriptores de su etapa no carga.
   - `extraer_lomloe --norma <id> --materia <sigla> --curso <n> --nombre <nombre de la ficha>
     [--titulo <título en el boletín>] --etapa <eso|bachillerato> --cursos-academicos
     2023-24,2024-25 --cache <dir>`. El título que se busca en el boletín es el de la materia
     tal cual (en el decreto de la ESO, en mayúsculas: `--titulo "DIGITALIZACIÓN"`); si la ficha
     la nombra distinto (Bachillerato: «Ciencias de la Computación I»), `--nombre` es el de la
     ficha (si termina en un ordinal romano, «… II», no lleva el sufijo «, N curso»). La
     búsqueda acaba en el título de la materia siguiente: una línea solo en mayúsculas con al
     menos cinco letras (limitación: una línea así *dentro* de una materia la cortaría antes;
     `comprobar` y los recuentos lo delatarían). Una materia que no marca el curso
     (Digitalización, solo 4.º ESO) solo se extrae con `--curso-unico`: sus criterios y
     contenidos van tras las competencias y debe haber un único bloque de criterios; sin esa
     opción es un error.
   - `extraer_fp modulo --ficha <código> --modulo <código> --ciclo <nombre> --boe <id>
     --ubicacion-boe <lugar> [--via <id>] --madrid <id> --horas <id> --cursos-academicos …
     --cache <dir>` (la ficha es el módulo, p. ej. `MAD.DAM.0485`). Los resultados, criterios,
     contenidos básicos (estatales, `EST.…CB.n`) y orientaciones salen del **PDF** de la norma
     `--boe`, limitado a su `--articulo` (por defecto el «segundo»): el RD 450/2010 no tiene
     texto consolidado, su anexo I vigente es el que reescribe el artículo segundo del RD
     405/2023 («queda redactado como sigue»; el artículo tercero repite módulos para otro
     título y no se toca). La procedencia es esa norma y su página; `--via` pone el real
     decreto original y `--ubicacion-via` el lugar de su anexo. Los contenidos de Madrid salen
     de `--madrid`; `--sin-contenidos-madrid` es para el módulo que el decreto no desarrolla
     (el proyecto). Las horas y el curso, de la tabla de `--horas`; si la tabla no pone el
     curso (el proyecto intermodular se desarrolla en los dos), hay que decidirlo con
     `--curso` y explicar la decisión en `fuentes.toml`. Un módulo sin ficha en alguna de las
     fuentes, una letra de criterio fuera de orden o una línea sin lugar son errores, no se
     omiten.
   - `extraer_fp titulo --ficha <código> --nombre <nombre del título> --boe <id> --original
     <id> [--adicion <id>] --cursos-academicos … --cache <dir>` (la ficha es el título, p. ej.
     `MAD.DAM`): los datos de identificación (`TIT.n`, uno por dato), las competencias
     profesionales (`CP.a`…) y los objetivos generales (`OG.a`…) en la redacción de `--boe`,
     con `via` al real decreto original, y la competencia general (`CG`) del PDF de
     `--original`. `--adicion` es la norma que añade un párrafo final al artículo 2.
   - `extraer_fp transversal --ficha <código> --modulo <código> --ciclo <nombre> --madrid <id>
     --ubicacion-madrid <anexo> --horas <id> [--estatal <id>] --cursos-academicos … --cache
     <dir>` (Itinerario I y II, Inglés, Digitalización y Sostenibilidad: `MAD.DAM.1709`…).
     Resultados, criterios y contenidos salen de la orden de Madrid `--madrid` (Orden
     3537/2025, el currículo que se aplica allí): resultados «1. …», criterios «a) …» (a veces
     pegada al texto) y, tras «Contenidos:», apartados y letras, por orden y sin interpretar la
     sangría; cada uno con la página en que empieza y la orden como procedencia (sin `via`: es
     currículo propio, no una modificación). El mínimo estatal (RD 659/2023, que la orden
     reformula y en 1709 y 1710 amplía) no se guarda: `--estatal` solo lo cita en las normas de
     la ficha. Las horas y el curso, de la tabla de `--horas`, como en `modulo`.
   - `extraer_fp optativo --ficha <código> --modulo <código del catálogo> --madrid <id>
     --catalogo <id> --cursos-academicos … --cache <dir>` (Orden 3536/2025 en la redacción de
     la Orden 3822/2026; la ficha es `MAD.CMO.316`, `MAD.CMO.001I`…). El currículo (resultados
     «1.Reconoce», criterios y contenidos) es el anexo II de `--madrid`; el nombre y las horas
     salen del encabezado del módulo («CMO-316 Programación en Python (90 horas).», o sin horas
     en los transversales), y las horas se cruzan con la fila del catálogo (`--catalogo`), de
     donde sale también el curso de los transversales (`2º curso.`; «en cualquiera de los dos
     cursos» es sin curso). CMO-001, 002 y 003 son un único currículo para tres lenguas
     (`F`, `I`, `A`): una ficha por variante, con el mismo texto. Se aplican las
     `sustituciones` de `--madrid` (Phyton→Python); una diferencia entre las horas del catálogo
     y las del anexo, o un criterio fuera de orden, es un error.
   - `extraer_requisitos --cache <dir>` (las tres fichas `MAD.ESO.PROG`, `MAD.BACH.PROG` y
     `MAD.FP.PROG`, tipo `requisito_programacion`): declarativo. `requisitos.toml` lista por ficha
     cada requisito (código, norma, ubicación, página y dos anclas literales, de inicio y de fin,
     ambas incluidas en el texto) y el módulo saca el texto de la página del PDF (y la siguiente)
     o, si no lleva `pagina`, del XML consolidado, con la normalización de `comprobar`. Un ancla
     que no aparece, que se repite en la región o con el fin antes del inicio es un error; en
     el XML el apartado no puede cruzar de párrafo. Un apartado con letras es un elemento (la
     frase que las introduce) y un hijo por letra (`padre`, código `….PROG.5.a`), sin la marca
     «a)». Para elegir los apartados: «programación didáctica», «programaciones» y
     «programación del» en cada norma; solo entra el que dice qué debe incluir, recoger,
     concretar, tener en cuenta o integrar la programación (no el que la nombra de pasada:
     quién la elabora, cuándo se revisa, qué hace la inspección con ella). Los `recuentos`
     son los apartados de cada norma que entran en cada ficha. Un texto sin cabeceras de
     boletín (las instrucciones de la web de la Comunidad) numera sus páginas por los saltos de
     página y no cuenta el número del pie.
   - `extraer_primaria --norma bocm-20220718-1 --rd boe-a-2022-3296 --cursos-academicos … --cache
     <dir>` (las 25 fichas de Primaria en una sola ejecución, como los requisitos; necesita el
     grupo `mantenimiento`: `uv run --group mantenimiento python -m …`). El anexo II del Decreto
     61/2022 son tablas (competencias | criterios; bloque | sub-bloque | contenidos) que
     `pdftotext` mezcla, así que se leen con pdfplumber: una ficha por área y ciclo,
     `MAD.EP.<ÁREA>.<C1|C2|C3>`; VCE (solo 5.º) es `MAD.EP.VCE` con curso 5, y SLE y TYR, de toda
     la etapa, no llevan ciclo. Cada ficha de ciclo trae todas las competencias del área en la
     redacción de ese ciclo (el decreto las repite y a veces cambia una coma o una palabra), con
     los descriptores que les conecta el RD 157/2022 (`--rd`; SLE y TYR los dicen en el propio
     decreto) y, en Ciencias de la Naturaleza y Sociales, `datos.equivalencia_rd` (la
     competencia de Conocimiento del Medio del RD). Los contenidos son
     `CO.<bloque>[.<n sub-bloque>].<n>`: el bloque con su letra (en Educación Artística, el
     «BLOQUE I/II» con su número romano y sus sub-bloques «A.», «B.»…), las viñetas «•» bajo la
     «-» anterior y las «–» bajo la «•»; sin numeración oficial. `MAD.EP.DESC` son los
     descriptores del anexo I. Una fila que no encaja (dos celdas en una columna, un criterio
     fuera de orden, un contenido sin viñeta ni anterior, un nivel saltado) es un error con el
     área y la página. Las páginas son las impresas («Pág. N»). `codigo_nuevo` traduce los
     códigos del JSON anterior de Primaria (`MAT.1.1.C2`, `MAT.CE1`) a los de las fichas.

## La Orden 3537/2025 sale cifrada: `cifrado.py`

La fuente del cuerpo de su PDF (un subconjunto de Arial sin mapa `ToUnicode`) nombra cada
glifo por su número en la fuente original (`/g3`, `/g38`…), y `pdftotext` los saca como el
carácter U+00NN: «competencias» sale «FRPSHWHQFLDV» y los paréntesis desaparecen (los
glifos 11 y 12 son para Unicode un espacio). `fuentes.toml` lo declara con
`cifrado = "glifos-arial"` (clave solo del mantenedor) y `comun.convertir_pdf` /
`comun.texto_de_norma` hacen lo siguiente, sin tocar el PDF original:

1. `cifrado.parchear_pdf` añade al final una actualización incremental que redeclara la
   codificación de esa fuente con `/uniXXXX` (el carácter ya descifrado) y un xref nuevo;
2. `pdftotext -layout` lee la copia temporal como cualquier otro PDF;
3. `cifrado.comprobar_descifrado` rechaza el resultado si queda un carácter de control o un
   glifo sin tabla (se pone en el área privada de Unicode, U+E000 + glifo). Se aplica
   también a un `.txt` ya en la caché: uno sacado sin descifrar se rechaza (bórralo).

La tabla (`GLIFOS_ARIAL`) es una biyección: el ASCII imprimible es el glifo 3 (el espacio) a
97 (`carácter = glifo + 29`) y los demás son los de Arial en el orden «Macintosh» (con una
plaza menos desde las comillas, porque esta Arial no trae el espacio duro): á é í ñ ó ú ü
(105, 112, 116, 120, 121, 126, 129), ª « » (157, 169, 170), “ ” (179, 180) y Á (200). Solo
entran los glifos que se compararon con la imagen de la página (`pdftoppm -r 100`); un glifo
nuevo se añade tras mirar dónde se usa. Otro PDF del BOCM con el mismo problema solo
necesita la misma línea en `fuentes.toml`, y si su fuente usa más glifos, ampliar la tabla.

## Qué garantiza `comprobar` y qué no

`comprobar` comprueba que el texto de cada elemento aparece **literal** en la página que cita
(y que recuentos, vigencias y relaciones cuadran). Sirve para cazar una extracción rota, no para
certificar el boletín. Sus límites:

- **Normaliza antes de comparar**, igual que el extractor: espacios y saltos de línea, NFC (y
  la marca combinante que repite el acento de su letra), espacios duros, viñetas (guiones,
  `•`, el glifo de apartado), un `»` de cierre al final de la unidad y los guiones de
  partición de palabra. El guion
  a final de línea tiene dos lecturas posibles y `comprobar` acepta las dos (con y sin guion).
  Consecuencia: un guion real de palabra compuesta que `unir` perdiera al juntar líneas **no
  lo detectaría**, porque la lectura sin guion también vale.
- **Una norma con `lector = "pdfplumber"`** (el Decreto 61/2022 de Primaria) no se compara
  con `pdftotext`, que mezcla sus columnas, sino con el texto de pdfplumber de la página por
  columnas (`<id>.columnas.json` en la caché; bórralo si cambia `columnas_de_pdf`): el texto tiene que estar en una columna y solo
  puede seguir en una columna de la página siguiente. El extractor y `comprobar` leen ese PDF con
  la misma biblioteca, así que un carácter mal leído saldría igual en los dos.
- **La raya corta (–) a final de línea entre dos letras** une un compuesto sin espacio
  («Mecánica–» «Ingeniería»), en las dos lecturas: no es una partición de palabra.
- **Las `sustituciones` de `fuentes.toml`** son correcciones de errores oficiales declaradas
  («Phyton» por «Python»): el texto guardado difiere a propósito de la página y `comprobar`
  aplica el par a la página antes de comparar. Lo que no está declarado ahí no se perdona.
- **Un elemento cuyo texto no es el de la página original** porque una norma posterior lo
  corrige o lo renombra lleva esa norma en `procedencia.norma` (con su ubicación y página,
  declaradas en `correccion_en`) y el lugar original en `procedencia.via`; el extractor lo pone
  solo, a partir de `fuentes.toml` (`sustituciones`, `correccion_en`, `consolidado`) y del
  catálogo vigente, nunca a mano. `comprobar` exige: el texto, tras aplicar las `sustituciones`
  de la norma original (o su forma del XML consolidado, `consolidado`), está en la página de
  `via`; la página de la corrección trae lo corregido; y las dos normas figuran relacionadas
  (`correcciones`, `modifica`, `modificada_por`). Un nombre renombrado en el catálogo se lee
  del catálogo por columnas y se compara con el mismo lector. Sin eso, discrepancia.
- **El descifrado de la Orden 3537/2025** (`cifrado.py`) lo comparten el extractor y
  `comprobar`: leen el mismo PDF por el mismo descifrado, así que un glifo mal traducido sale
  igual en los dos y la comparación no lo ve. Su única salvaguarda independiente es la
  comparación visual del mantenedor con la imagen de la página (`pdftoppm`).
- **La revisión independiente** es el doble chequeo con otro modelo, ficha por ficha
  (ver «Revisión externa por materia» más abajo): `comprobar` no lo sustituye ni lo reduce.

## Los fragmentos de `fuentes/`

`fuentes/*.txt` son trozos de texto de boletín ya extraído, con sus cabeceras de página,
`fuentes/*.xml` trozos del XML consolidado del BOE (tablas y anexos) y
`bocm-20250827-6_cifrado.pdf` un PDF mínimo con los objetos reales de la fuente cifrada, para
los tests (`tests/test_herramienta.py`). Junto con los datos de
`src/normativa_madrid/datos/`, es el único sitio del repositorio donde puede aparecer texto de
boletín literal.

## Primaria: un PDF de tablas, leído con pdfplumber

El Decreto 61/2022 (`bocm-20220718-1`) maqueta el anexo II en tablas de columnas (competencias |
criterios; bloque | sub-bloque | contenidos) que `pdftotext` mezcla. Por eso:

- `fuentes.toml` declara `lector = "pdfplumber"` para esa norma, y `extraer_primaria` y
  `comprobar` la leen con la misma biblioteca, por columnas. Ese grupo se instala con
  `uv run --group mantenimiento …`; `pdfplumber` nunca es dependencia de ejecución.
- La lectura por columnas es lenta y se guarda en la caché como `<id>.columnas.json`. Si cambia
  `columnas_de_pdf`, **bórrala**: `comprobar` seguiría comparando con la lectura vieja.
- `extraer_primaria` genera las 25 fichas `MAD.EP.*` en una sola ejecución (24 por área y
  ciclo —VCE solo de 5.º; SLE y TYR de toda la etapa— más `MAD.EP.DESC`). Una fila que no encaja
  es un error con el área y la página: no se arregla a mano, se arregla el extractor o se
  declara en `fuentes.toml`. `regenerar` la ejecuta junto con el resto del lote.
- Los contenidos de Primaria no llevan numeración oficial (`codigo_oficial: null`); su código sale
  de la posición (`CO.<bloque>[.<sub-bloque>].<n>`) y por eso es estable mientras el decreto no
  cambie de orden, pero no oficial.
- `equivalencias_primaria.py` genera `datos/equivalencias-primaria-2026.json` (los códigos
  del formato antiguo de Primaria y su código nuevo); el paquete solo lo lee al comprobar
  documentos. Se regenera con `uv run python -m herramientas.normativa.equivalencias_primaria` y se commitea; `test_migracion_primaria_sin_perdidas` vigila
  que no se pierda ningún criterio ni competencia.

## Revisión externa por materia

`comprobar` caza una extracción rota, pero lee el PDF con la misma biblioteca que el extractor:
un fallo de lectura saldría igual en los dos. Por eso cada ficha nueva (o cada ficha que cambie
de extractor) pasa además por una **revisión independiente**: otro modelo, en una sesión nueva
por ficha, que lee el PDF por su cuenta.

Hay que repetir el proceso por cada ficha (una materia y curso, un módulo, el conjunto de
descriptores de una etapa o un grupo de requisitos):

1. Abre una **sesión nueva por ficha** en un modelo que lea PDF.
2. **Mensaje 1:** adjunta solo el PDF de la norma y pega el prompt de la fase 1. **No adjuntes
   todavía el JSON.** El revisor cuenta lo que hay, sin saber qué extrajo el programa.
3. **Mensaje 2:** cuando haya respondido, pega el prompt de la fase 2 y adjunta el JSON de la
   ficha, que sale de `normativa-madrid ficha <codigo> [--curso N | --ciclo CN] > <codigo>.json`.
   Si la ficha se apoya en otra norma (descriptores del perfil de salida, módulo estatal de FP),
   adjunta también su PDF.
4. Guarda la respuesta final junto con el resto de revisiones del repositorio. Copia los
   recuentos de la fase 1 a `recuentos` de la norma en `fuentes.toml` (o a `requisitos.toml`)
   para que `comprobar` los vigile.
5. Solo se aprueba con **cero discrepancias**. Los patrones que repita el revisor se corrigen en
   el extractor, se regenera y se vuelve a revisar la ficha completa.

### Prompt, fase 1 (solo el PDF)

Sustituye `{NORMA}` (nombre y número de la norma, p. ej. «Decreto 65/2022, de 20 de julio»),
`{BOLETÍN}`, `{APARTADO}` (anexo y materia o módulo, p. ej. «Anexo II, materia de Ciencias de la
Computación, primer curso») y `{SIGUIENTE}` (el título de lo que viene a continuación).

````text
Eres revisor de normativa educativa. Te adjunto la norma {NORMA} ({BOLETÍN}).

Trabaja solo con {APARTADO}, desde su título hasta {SIGUIENTE}. Lee las tablas tal como están
maquetadas (en una tabla de dos columnas, competencias a la izquierda y criterios a la derecha;
en las de contenidos, bloque, sub-bloque si lo hay y texto). Las tablas continúan de una página
a otra.

Sin ningún otro material, cuenta y responde exactamente con este formato:

FICHA: {APARTADO}
Páginas del PDF que abarca: <primera>–<última>   (y páginas impresas «Pág. N»)
Organización: <por ciclos | por cursos | un único bloque>
Competencias específicas (o resultados de aprendizaje) distintas: <n>
Por curso o ciclo (o «único» si no hay):
  <curso o ciclo>: criterios=<n>  bloques de contenidos=<n>  contenidos o viñetas=<n>
Lista de criterios (solo la numeración, en orden, tal como se imprime):
  <curso o ciclo>: 1.1, 1.2, 2.1, … (en FP: a), b), …)
Dudas de lectura: <celdas ilegibles, numeración salteada o repetida en el original, erratas del
propio boletín, o «ninguna»>

Un «contenido» o «viñeta» es cada línea que empieza por un marcador («-», «x», «•» u otro) o por
una numeración propia, incluidas las anidadas. Cuenta cada una una vez, aunque ocupe varias
líneas. No resumas ni interpretes: es un recuento. Si el propio boletín tiene una errata, por
ejemplo un criterio numerado dos veces, anótala en «Dudas de lectura» tal como aparece.
````

### Prompt, fase 2 (con el JSON de la ficha)

````text
Ahora te adjunto {CODIGO}.json: lo que un programa ha extraído automáticamente de ese mismo
apartado del PDF. Es la respuesta de `normativa-madrid ficha {CODIGO}`: una lista `elementos[]`
con, en cada uno, `codigo`, `tipo`, `texto`, `codigo_oficial` (la numeración tal como la imprime
el boletín, o null si no la hay), `padre`, `orden`, `procedencia` (`norma`, `ubicacion`,
`pagina` impresa y `via`) y `relaciones` (p. ej. los descriptores que cita una competencia).

Compáralo con el PDF elemento a elemento, sin muestrear. Comprueba:

1. Que no falte nada ni sobre nada: cada competencia, criterio, contenido o resultado de
   aprendizaje del PDF está en el JSON exactamente una vez, y no hay nada en el JSON que no esté
   en el PDF. Usa tus recuentos de la fase 1.
2. Textos literales: el texto coincide con el del boletín palabra por palabra. Se admiten
   diferencias de salto de línea y de espacios; no se admiten palabras cortadas o unidas
   («investi gación», «delmedio»), tildes o letras perdidas, frases de otra celda mezcladas, ni
   restos de cabecera o pie de página («BOCM», «Pág.», la fecha).
3. Asignación correcta: cada criterio cuelga (`padre`) de su competencia o resultado y del curso o
   ciclo correcto; cada contenido, de su bloque y sub-bloque; el orden es el del boletín.
4. `codigo_oficial`: es exactamente la numeración impresa («1», «1.1», «a)», «1.»…) y es null solo
   si el boletín no numera ese elemento (lo normal en los contenidos de Madrid).
5. `procedencia`: la norma y la página impresa son las del texto; si hay `via`, el texto procede
   de otra norma que lo corrige y el lugar original es el que dice `via`.
6. Relaciones: los descriptores de cada competencia coinciden con los que da la norma que los
   conecta (adjunta su PDF si es otra). Si ninguna norma los enumera, no debe haber ninguno.

Responde exactamente con este formato:

FICHA: {CODIGO}
VEREDICTO: APROBADA | NO APROBADA
Recuentos PDF vs JSON:
  competencias o resultados: <pdf> vs <json>
  <curso o ciclo>: criterios <pdf> vs <json>; contenidos <pdf> vs <json>
Discrepancias (una fila por problema; «ninguna» si no hay):
| # | Tipo (falta/sobra/texto/asignación/codigo_oficial/procedencia/relación) | Código o ubicación | Página | Dice el PDF | Dice el JSON |
Patrones (si un mismo error se repite, descríbelo una vez para corregir el extractor):
Dudas que necesitan a una persona:

Solo se aprueba con cero discrepancias. Una errata del propio boletín que el JSON reproduce
fielmente no cuenta como discrepancia; anótala en «Dudas». No propongas correcciones al texto
oficial ni lo mejores: la referencia es el boletín, incluidos sus errores.
````

### Variante: descriptores (sesión aparte)

Adjunta el PDF de la norma y `normativa-madrid ficha MAD.EP.DESC` (o `EST.ESO.DESC`,
`EST.BACH.DESC`) en lugar de las dos fases anteriores, y pega:

````text
Te adjunto la norma {NORMA} y un JSON con los descriptores operativos que un programa ha extraído
de su anexo I. Primero cuenta, en el PDF, cuántos descriptores hay por competencia clave (CCL, CP,
STEM, CD, CPSAA, CC, CE y CCEC) y lista sus códigos tal como se imprimen. Después compara el JSON
elemento a elemento: códigos, competencia clave y texto literal, con los mismos criterios de
literalidad (sin palabras cortadas, sin letras perdidas, sin restos de cabecera). Responde con el
formato de la fase 2 y pon «DESCRIPTORES» como ficha.
````
