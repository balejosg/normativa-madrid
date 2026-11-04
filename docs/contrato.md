# Contrato de `normativa-madrid` para agentes

Qué devuelve cada orden, qué códigos de error y de aviso existen y qué garantiza el paquete (y
qué no). Los ejemplos de JSON son salida real de la CLI, recortada (`…` marca un texto cortado y
las listas largas se reducen a un elemento); `tests/test_contrato.py` comprueba que sus claves de
primer nivel coinciden con las de la salida real y que cada código de error y de aviso del
código está aquí, y al revés.

## Reglas generales

- Cada orden imprime **un único JSON** en stdout. Sale con **0** si se resuelve; con **2** si
  falla (el JSON es entonces un error, ver más abajo). `comprobar` sale con **1** si encuentra
  códigos desconocidos en algún documento.
- Sin red y sin escribir ficheros. Todas las órdenes salvo `norma` admiten
  `--curso-academico AAAA-AA` (por defecto, el curso académico de hoy en Madrid). Los datos
  actuales son del curso `2026-27`.
- Toda respuesta correcta lleva la cabecera `consulta`, `version_datos` (la fecha de la
  revisión más reciente de los datos), `curso_academico`, `curso_en_vigor`, `aviso` y `avisos`
  (lista; vacía si no hay ninguno).
- Todo elemento trae `codigo` (estable, para citar y buscar), `tipo`, `texto` (literal del
  boletín), `codigo_oficial` y `procedencia` (`norma`, `ubicacion`, `pagina` y `via`).
- **`codigo` y `codigo_oficial` no son lo mismo.** `codigo` es el identificador estable de este
  paquete (`MAD.EP.MAT.C2.CR.1.1`). `codigo_oficial` es la numeración **tal como la imprime el
  boletín**, como cadena, y su formato cambia según la etapa: «1» y «1.1» en ESO y Bachillerato
  y en Primaria; «1.» y «a)» en FP. Es `null` si el boletín no numera el elemento, como pasa con
  los contenidos de Primaria y de Madrid en general.
- `pagina` es la **página impresa** del boletín («Pág. N»), no la del PDF.
- Si `via` no está vacío, el texto procede de otra norma y esta lo corrige o lo renombra:
  `via` dice el lugar original.
- Los contenidos se llaman **«contenidos»** en Madrid (no «saberes básicos»).
- Una ficha de Primaria es por **área y ciclo** (C1: 1.º y 2.º; C2: 3.º y 4.º; C3: 5.º y 6.º).
  Educación en Valores Cívicos y Éticos (`MAD.EP.VCE`) es solo de 5.º; Segunda Lengua Extranjera
  (`MAD.EP.SLE`) y Tecnología y Robótica (`MAD.EP.TYR`) son de toda la etapa.

## Órdenes

### `catalogo [--etapa primaria|eso|bachillerato|fp_gs]`

Las fichas (materias, módulos, descriptores, requisitos de la programación) que hay en el curso
académico, con las normas de cada una. Es la fuente de verdad de la cobertura.

<!-- orden: catalogo --etapa primaria -->
```json
{
  "consulta": "catalogo",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [],
  "fichas": [
    {
      "codigo": "MAD.EP.CN.C1",
      "nombre": "Ciencias de la Naturaleza, primer ciclo",
      "etapa": "primaria",
      "curso": null,
      "ciclo": "C1",
      "desde": null,
      "normas": [
        {
          "id": "bocm-20220718-1",
          "rango": "decreto",
          "numero": "61/2022",
          "fecha": "2022-07-13",
          "boletin": "BOCM",
          "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
        }
      ]
    }
  ]
}
```

### `ficha <codigo> [--curso N | --ciclo CN] [--formato json|md]`

Todos los elementos de una ficha, en orden. Para un área de Primaria (`MAD.EP.MAT`) hay que
decir el curso (`--curso 3`, del 1 al 6, que no es el curso académico) o el ciclo (`--ciclo C2`);
sin eso, o con un curso en que el área no se imparte (VCE solo en 5.º), es un error
`CURSO_SIN_DATOS` cuya lista `disponibles` dice las fichas o cursos posibles. `--formato md`
da una vista en Markdown para personas (los errores salen siempre en JSON).

Una competencia lleva en `relaciones.descriptores` los descriptores del perfil de salida que se
le conectan, y un criterio cuelga de su competencia en `padre`.

<!-- orden: ficha MAD.EP.MAT --curso 3 -->
```json
{
  "consulta": "ficha",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [
    {
      "codigo": "NUMERACION_NO_OFICIAL",
      "detalle": "Estos elementos no están numerados en el boletín; su código es estable pero no oficial: no lo presentes como numeración oficial"
    }
  ],
  "codigo": "MAD.EP.MAT.C2",
  "nombre": "Matemáticas, segundo ciclo",
  "etapa": "primaria",
  "curso": null,
  "ciclo": "C2",
  "desde": null,
  "normas": [
    {
      "id": "bocm-20220718-1",
      "rango": "decreto",
      "numero": "61/2022",
      "fecha": "2022-07-13",
      "boletin": "BOCM",
      "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
    }
  ],
  "elementos": [
    {
      "codigo": "MAD.EP.MAT.C2.CE.1",
      "tipo": "competencia_especifica",
      "texto": "Interpretar situaciones de la vida cotidiana proporcionando una representación matemática de las mismas median…",
      "codigo_oficial": "1",
      "procedencia": {
        "norma": {
          "id": "bocm-20220718-1",
          "rango": "decreto",
          "numero": "61/2022",
          "fecha": "2022-07-13",
          "boletin": "BOCM",
          "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
        },
        "ubicacion": "anexo II, Matemáticas, segundo ciclo, competencias específicas",
        "pagina": 100,
        "via": []
      },
      "padre": null,
      "orden": 1,
      "datos": {},
      "relaciones": {
        "descriptores": [
          {
            "codigo": "MAD.EP.DESC.STEM1",
            "ficha": "MAD.EP.DESC",
            "tipo": "descriptor",
            "texto": "Utiliza, de manera guiada, algunos métodos inductivos y deductivos propios del razonamiento matemático en situ…"
          }
        ]
      }
    },
    {
      "codigo": "MAD.EP.MAT.C2.CR.1.1",
      "tipo": "criterio",
      "texto": "Interpretar, de forma verbal o gráfica, problemas de la vida cotidiana, comprendiendo las preguntas planteadas…",
      "codigo_oficial": "1.1",
      "procedencia": {
        "norma": {
          "id": "bocm-20220718-1",
          "rango": "decreto",
          "numero": "61/2022",
          "fecha": "2022-07-13",
          "boletin": "BOCM",
          "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
        },
        "ubicacion": "anexo II, Matemáticas, segundo ciclo, criterios",
        "pagina": 100,
        "via": []
      },
      "padre": "MAD.EP.MAT.C2.CE.1",
      "orden": 2,
      "datos": {},
      "relaciones": {}
    },
    {
      "codigo": "MAD.EP.MAT.C2.CO.A.1.1",
      "tipo": "contenido",
      "texto": "Estrategias variadas de conteo (series ascendentes y descendentes de cadencia 2, 10,100, 1000, 10000, a partir…",
      "codigo_oficial": null,
      "procedencia": {
        "norma": {
          "id": "bocm-20220718-1",
          "rango": "decreto",
          "numero": "61/2022",
          "fecha": "2022-07-13",
          "boletin": "BOCM",
          "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
        },
        "ubicacion": "anexo II, Matemáticas, segundo ciclo, contenidos",
        "pagina": 102,
        "via": []
      },
      "padre": "MAD.EP.MAT.C2.CO.A.1",
      "orden": 28,
      "datos": {},
      "relaciones": {}
    }
  ]
}
```

### `elemento <codigo> [--formato json|md]`

Un elemento por su código, con la misma forma que los de `ficha` y la ficha a la que
pertenece.

<!-- orden: elemento MAD.EP.MAT.C2.CO.A.1.1 -->
```json
{
  "consulta": "elemento",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [
    {
      "codigo": "NUMERACION_NO_OFICIAL",
      "detalle": "Estos elementos no están numerados en el boletín; su código es estable pero no oficial: no lo presentes como n…"
    }
  ],
  "ficha": "MAD.EP.MAT.C2",
  "desde": null,
  "elemento": {
    "codigo": "MAD.EP.MAT.C2.CO.A.1.1",
    "tipo": "contenido",
    "texto": "Estrategias variadas de conteo (series ascendentes y descendentes de cadencia 2, 10,100, 1000, 10000, a partir…",
    "codigo_oficial": null,
    "procedencia": {
      "norma": {
        "id": "bocm-20220718-1",
        "rango": "decreto",
        "numero": "61/2022",
        "fecha": "2022-07-13",
        "boletin": "BOCM",
        "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
      },
      "ubicacion": "anexo II, Matemáticas, segundo ciclo, contenidos",
      "pagina": 102,
      "via": []
    },
    "padre": "MAD.EP.MAT.C2.CO.A.1",
    "orden": 28,
    "datos": {},
    "relaciones": {}
  }
}
```

### `norma "<cita>"`

Una norma por su cita («Decreto 61/2022», «RD 405/2023»): título, boletín, URL, estado y las
normas que la modifican o corrigen. No admite `--curso-academico`.

<!-- orden: norma "Decreto 61/2022" -->
```json
{
  "consulta": "norma",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [],
  "id": "bocm-20220718-1",
  "rango": "decreto",
  "numero": "61/2022",
  "fecha": "2022-07-13",
  "titulo": "Decreto 61/2022, de 13 de julio, del Consejo de Gobierno, por el que se establece para la Comunidad de Madrid…",
  "boletin": "BOCM",
  "url_pdf": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF",
  "url_api": null,
  "estado": "vigente",
  "derogada_por": null,
  "desde": null,
  "correcciones": [],
  "modifica": [],
  "modificada_por": [
    {
      "id": "bocm-20240613-2",
      "rango": "decreto",
      "numero": "59/2024",
      "fecha": "2024-06-12",
      "boletin": "BOCM",
      "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2024/06/13/BOCM-20240613-2.PDF"
    }
  ],
  "derogaciones_parciales": [],
  "cita_pedida": null,
  "cita_correcta": null
}
```

### `buscar "<texto>" [--en <codigo>]`

Busca un texto, sin distinguir tildes ni mayúsculas, en los elementos del curso académico, o
solo en una ficha con `--en`. `total` es el número de resultados.

<!-- orden: buscar división --en MAD.EP.MAT.C2 -->
```json
{
  "consulta": "buscar",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [
    {
      "codigo": "NUMERACION_NO_OFICIAL",
      "detalle": "Estos elementos no están numerados en el boletín; su código es estable pero no oficial: no lo presentes como numeración oficial"
    }
  ],
  "total": 6,
  "resultados": [
    {
      "codigo": "MAD.EP.MAT.C2.CO.A.3.3",
      "ficha": "MAD.EP.MAT.C2",
      "tipo": "contenido",
      "texto": "Estrategias de cálculo mental de multiplicación y división de números naturales.",
      "codigo_oficial": null,
      "procedencia": {
        "norma": {
          "id": "bocm-20220718-1",
          "rango": "decreto",
          "numero": "61/2022",
          "fecha": "2022-07-13",
          "boletin": "BOCM",
          "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/07/18/BOCM-20220718-1.PDF"
        },
        "ubicacion": "anexo II, Matemáticas, segundo ciclo, contenidos",
        "pagina": 102,
        "via": []
      }
    }
  ]
}
```

### `programacion <eso|bachillerato|fp>`

Lo que la normativa exige de la programación didáctica de una etapa: cada requisito con su texto
literal y su procedencia, y el `indice`, que dice quién fija el índice de la programación.

<!-- orden: programacion eso -->
```json
{
  "consulta": "programacion",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [
    {
      "codigo": "NUMERACION_NO_OFICIAL",
      "detalle": "Estos elementos no están numerados en el boletín; su código es estable pero no oficial: no lo presentes como numeración oficial"
    }
  ],
  "etapa": "eso",
  "ficha": "MAD.ESO.PROG",
  "requisitos": [
    {
      "codigo": "MAD.ESO.PROG.1",
      "tipo": "requisito_programacion",
      "texto": "La evaluación continua del alumnado requiere su asistencia regular a las clases y a las actividades programada…",
      "codigo_oficial": null,
      "procedencia": {
        "norma": {
          "id": "bocm-20230531-17",
          "rango": "orden",
          "numero": "1712/2023",
          "fecha": "2023-05-19",
          "boletin": "BOCM",
          "url": "https://www.bocm.es/boletin/CM_Orden_BOCM/2023/05/31/BOCM-20230531-17.PDF"
        },
        "ubicacion": "art. 19.3",
        "pagina": 68,
        "via": []
      },
      "padre": null,
      "orden": 1,
      "datos": {},
      "relaciones": {}
    }
  ],
  "indice": "Cuando ninguna norma fija el índice de la programación, lo fija la plantilla del centro."
}
```

### `comprobar <fichero>…`

Comprueba que **todos** los códigos citados en uno o más documentos (`.md`, `.txt`, `.docx`,
`.odt`; lee también tablas, notas al pie y encabezados) existen. Por fichero devuelve los
`conocidos` y los `desconocidos`, con sugerencias. Sale con 1 si hay algún desconocido. Un fichero
que no se puede leer va a `ilegibles` y no tapa el resultado de los demás; si no se puede leer
ninguno, la respuesta es un error `FICHERO_ILEGIBLE` (salida 2). También marca los códigos del
formato antiguo de Primaria (`MAT.3.1.C2`) como desconocidos y sugiere el nuevo.
Si el documento no cita ningún código, `conocidos` y `desconocidos` salen vacíos: no lo des por
bueno si debería citar alguno.

<!-- orden: comprobar programacion.md -->
```json
{
  "consulta": "comprobar",
  "version_datos": "2026-10-18",
  "curso_academico": "2026-27",
  "curso_en_vigor": true,
  "aviso": "Texto literal del boletín. Cita siempre el código y la procedencia.",
  "avisos": [],
  "ficheros": [
    {
      "fichero": "programacion.md",
      "conocidos": [
        "MAD.EP.MAT.C2.CR.1.1"
      ],
      "desconocidos": [
        {
          "codigo": "MAD.EP.MAT.C2.CR.9.9",
          "sugerencias": [
            "MAD.EP.MAT.C2.CR.8.2",
            "MAD.EP.MAT.C2.CR.8.1"
          ]
        }
      ]
    }
  ],
  "ilegibles": []
}
```

## Errores

Un error es un único JSON con salida 2; `disponibles` lista las opciones válidas cuando las hay
(o `[]`).

<!-- orden: ficha MAD.EP.XX -->
```json
{
  "error": "NORMATIVA_SIN_DATOS",
  "detalle": "La fuente de normativa no trae la ficha «MAD.EP.XX».",
  "disponibles": [
    "EST.BACH.DESC"
  ]
}
```

## Códigos de error

| Código | Cuándo sale y qué hacer |
|---|---|
| `CODIGO_DESCONOCIDO` | El código pedido a `elemento` no existe. No hay ningún elemento con ese código. Busca el código exacto con la consulta de la ficha o con una búsqueda de texto. |
| `CURSO_SIN_DATOS` | El curso académico, el curso o el ciclo pedidos no tienen datos (o falta decir el curso o el ciclo de un área de Primaria). normativa-madrid no trae datos de ese curso académico. La lista de «disponibles» dice de cuáles sí; no los sustituyas por los de otro curso sin avisar a quien consulta. |
| `DATOS_INVALIDOS` | Los datos instalados no cumplen su formato. Los datos de normativa no cumplen su formato: el detalle nombra el fichero y el campo. Es un fallo de la instalación o de una edición a mano: reinstala o actualiza normativa-madrid. |
| `ETAPA_DESCONOCIDA` | La etapa de `programacion` o de `catalogo --etapa` no es válida. La etapa debe ser eso, bachillerato o fp. |
| `FICHERO_ILEGIBLE` | Ningún fichero de `comprobar` se pudo leer. No se pudo leer el documento: no existe, está dañado o no es .md, .txt, .docx ni .odt. Convierte el documento a uno de esos formatos y repite la comprobación. |
| `NORMATIVA_SIN_DATOS` | La ficha, materia o módulo pedido no está en el paquete. normativa-madrid no trae esa materia o ese módulo. La lista de «disponibles» dice cuáles sí trae; para lo demás, consulta la norma en el boletín. |
| `NORMA_DESCONOCIDA` | La cita de `norma` no corresponde a ninguna norma. normativa-madrid no tiene esa norma. Prueba con otra forma de citarla (por ejemplo «Decreto 27/2025» o «RD 405/2023») o consulta el boletín. |
| `SALIDA_INVALIDA` | La respuesta no cumplió el esquema de salida. La respuesta de la consulta no cumple el formato de salida: no la uses. Es un fallo de normativa-madrid; avisa a quien la mantiene con este código. |
| `TEXTO_VACIO` | `buscar` sin texto. Falta el texto que buscar: escribe al menos una palabra. |

## Códigos de aviso

Un aviso no es un error: la respuesta es válida, pero hay que leerlo y tenerlo en cuenta. Va en
`avisos`, con `codigo` y `detalle`.

| Código | Cuándo sale y qué hacer |
|---|---|
| `NUMERACION_NO_OFICIAL` | Una respuesta incluye elementos con `codigo_oficial: null`. Estos elementos no están numerados en el boletín; su código es estable pero no oficial: no lo presentes como numeración oficial. Cita esos elementos por su texto y su bloque, sin código, o di que el código no es oficial. |

## Qué garantiza el paquete

- **Texto literal.** Cada texto es el del boletín, con espacios y saltos de línea normalizados.
  No hay palabras cortadas ni unidas, letras perdidas ni restos de cabecera. Una herramienta de
  mantenimiento comprueba que cada texto aparece literal en la página que cita.
- **Procedencia de cada elemento.** Norma, ubicación y página impresa del boletín, de modo que se
  puede cotejar con la fuente. Las correcciones de errores oficiales se aplican y quedan
  anotadas en `via`.
- **Códigos estables.** Un `codigo` identifica siempre al mismo elemento; `comprobar` detecta
  los que no existen.
- **`codigo_oficial` fiel al boletín.** Se guarda como se imprime (o `null` si no hay
  numeración). Un elemento con `codigo_oficial: null` hace que la respuesta lleve el aviso
  `NUMERACION_NO_OFICIAL`: su `codigo` es de este paquete, **no** oficial.
- **Sin red.** Consultar no abre conexiones ni escribe ficheros.

## Qué no garantiza

- **Vigencia posterior a `revisada`.** Los datos están revisados contra el boletín en la fecha
  `revisada` de cada norma (`version_datos` es la más reciente). Si la norma se ha modificado o
  derogado después, el paquete no lo sabe: comprueba el boletín o actualiza el paquete.
- **Recursos judiciales.** Hay un recurso contencioso-administrativo contra el Decreto 61/2022
  (currículo de Educación Primaria de Madrid) cuyo resultado no consta en los datos. Una sentencia
  podría anular parte del decreto; el paquete no lo refleja.
- **Cobertura.** Solo trae lo que lista `catalogo`. Lo que no está no se puede citar con este
  paquete; no inventes un código.
- **Interpretación.** Devuelve el texto de la norma, no su aplicación (calendarios, instrucciones
  de inicio de curso, normas de centro).
- **Que un documento sea correcto.** `comprobar` dice que los códigos existen, no que se hayan
  elegido bien ni que el texto citado sea fiel: cita el texto que devuelve la consulta.
