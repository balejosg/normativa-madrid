---
name: normativa-madrid
description: Consultar la normativa educativa oficial de la Comunidad de Madrid (competencias, criterios de evaluación, contenidos, descriptores, resultados de aprendizaje y requisitos de la programación de Primaria, ESO, Bachillerato y FP) con texto literal y procedencia, y comprobar que un documento solo cita códigos que existen. Úsala antes de citar el currículo en programaciones, unidades, rúbricas o exámenes.
---

# Normativa educativa de Madrid

Fuente de datos: el paquete `normativa-madrid` (orden `normativa-madrid`). Trae el texto literal
del boletín, un código estable por elemento y su procedencia (norma, ubicación y, si la hay, página impresa; es `null` en el texto que viene del XML consolidado del BOE y entonces `ubicacion` da el lugar).
Funciona sin Internet. El contrato completo está en `docs/contrato.md` del repositorio (no va en el paquete instalado); cada orden admite `--help` y todo error trae su código y un detalle.

## Cuándo usarla
Siempre que el encargo necesite citar competencias específicas, criterios de evaluación,
contenidos, descriptores del perfil de salida, resultados de aprendizaje o los requisitos de la
programación didáctica **en Madrid**. Si la comunidad no es Madrid, no la uses.

## Reglas
1. **Consulta antes de citar.** No cites de memoria ningún código ni texto del currículo.
2. **Cita solo lo que la consulta devuelve**: el `codigo` y el `texto` literal, sin cambiar
   palabras. Si resumes o adaptas, dilo («resumen de …») y conserva el código.
3. **Antes de entregar un documento, pásalo por `comprobar`** (ver abajo).
4. **Código con `NUMERACION_NO_OFICIAL`: no lo presentes como oficial.** Esos elementos no están
   numerados en el boletín (`codigo_oficial` es `null`); su código es estable pero lo ha puesto
   este paquete. Cítalos por su texto y su bloque (p. ej. «A. Números y operaciones › Operaciones»)
   y, si pones el código, di que no es numeración oficial.
5. **`codigo_oficial` es lo que imprime el boletín**, y su formato cambia por etapa (ESO y
   Bachillerato «1», «1.1»; FP «1.», «a)»). No lo recompongas ni lo normalices: si lo citas,
   cítalo con el código y la norma.
6. **En Madrid se dice «contenidos»**, no «saberes básicos».
7. **Di de dónde sale**: al citar, añade la norma y la página (`procedencia`) si el documento lo
   admite.

## Flujo de trabajo
1. `normativa-madrid catalogo [--etapa primaria|eso|bachillerato|fp_gs]`: qué hay. Es la lista
   exacta de lo que se puede citar.
2. `normativa-madrid ficha <codigo> [--curso N | --ciclo CN]`: todos los elementos de una
   materia, módulo o área, con su texto y su procedencia (`--formato md` para leerlo).
3. `normativa-madrid buscar "<texto>" [--en <codigo>]`: localizar por tema (sin distinguir tildes
   ni mayúsculas). `elemento <codigo>`: un elemento concreto.
4. `normativa-madrid norma "Decreto 61/2022"`: datos de una norma y de sus modificaciones.
5. `normativa-madrid programacion <eso|bachillerato|fp>`: lo que la normativa exige de la
   programación didáctica de la etapa.
6. Redacta citando solo lo devuelto.
7. **`normativa-madrid comprobar documento.docx`** (acepta `.md`, `.txt`, `.docx` y `.odt`, y lee
   también las tablas). Si el texto está en el chat, guárdalo antes en un fichero y comprueba ese
   fichero.
   - Salida 0: los códigos existen. Si no cita ninguno y debería, el comprobador no los ha leído
     (p. ej. la numeración de un libro de texto): no lo des por bueno.
   - Salida 1: hay `desconocidos`, con sugerencias; corrígelos y repite.
   - Salida 2: algún documento no se pudo leer (sale en `ilegibles`, con su motivo; conviértelo a
     uno de los formatos admitidos) o hay un error de uso.

Con `--curso-academico AAAA-AA` se consulta otro curso académico; por defecto, el de hoy.

## Primaria: etapa, curso y ciclo
Primaria se organiza por ciclos: C1 (1.º y 2.º), C2 (3.º y 4.º) y C3 (5.º y 6.º). **Pregunta
siempre la etapa y el curso** si no están claros, y pasa `--curso` (da el ciclo) o `--ciclo` al
pedir un área (`ficha MAD.EP.MAT --curso 3`): algunas competencias se redactan distinto en cada
ciclo y sin él podrías citar la equivocada.
- Educación en Valores Cívicos y Éticos (`MAD.EP.VCE`) solo se imparte en 5.º; con otro curso la
  consulta falla con `CURSO_SIN_DATOS`: dilo al docente.
- Segunda Lengua Extranjera (`MAD.EP.SLE`) y Tecnología y Robótica (`MAD.EP.TYR`) son de toda la
  etapa: cualquier curso sirve.
- Si el área es ambigua, mira `catalogo --etapa primaria` y pregunta.
- Los códigos de Primaria son `MAD.EP.<ÁREA>.<CICLO>.<TIPO>.<n>`; los descriptores,
  `MAD.EP.DESC.<CLAVE><n>`. Las competencias de Ciencias de la Naturaleza y Ciencias Sociales
  traen en `datos.equivalencia_rd` su equivalencia en el Real Decreto 157/2022.
- Los contenidos de Primaria no tienen numeración oficial: regla 4.

## Programa bilingüe
Según el artículo 9.1 del Decreto 61/2022, en la redacción del Decreto 59/2024, en Primaria los
centros pueden impartir las áreas en lengua extranjera **a excepción de Matemáticas y Lengua
Castellana y Literatura, así como de los contenidos relacionados con la Historia de España del
área de Ciencias Sociales**. Tenlo en cuenta al proponer actividades en inglés. (En ESO, el
Decreto 65/2022 excluye además Latín y Segunda Lengua Extranjera y los contenidos de Historia de
España de Geografía e Historia; consulta la norma antes de dar por válido otro caso.)
El texto está en el artículo primero del Decreto 59/2024 (BOCM n.º 140, 13-06-2024); el paquete
trae la norma (`normativa-madrid norma "Decreto 59/2024"`) pero no el articulado.

## Si la consulta no tiene lo que buscas
Si `catalogo` no lista la materia, el curso o el módulo, o una consulta responde
`NORMATIVA_SIN_DATOS` o `CODIGO_DESCONOCIDO`:
- **Díselo con claridad** al docente: «normativa-madrid no trae esa materia» (o «ese código no
  existe»).
- **Pide el PDF del boletín** (o el fragmento) y trabaja con él, citando la norma y la página, sin
  código del paquete.
- Ofrece lo más cercano que sí exista (las sugerencias y `disponibles`) o redactarlo como objetivo
  propio, sin código oficial y marcado como tal.
- **Nunca inventes un código**, ni adaptes uno de otra materia o de otro curso.
- Un error `DATOS_INVALIDOS` o `SALIDA_INVALIDA` es un fallo del paquete: no uses esa respuesta.

## Si el docente aporta otra numeración
Si pega criterios de su libro de texto, del currículo estatal o de otra comunidad, no mezcles
numeraciones. Pásalos por `comprobar` o búscalos con `buscar`, propón el equivalente de Madrid y
pide confirmación. Los códigos del formato antiguo (p. ej. `MAT.3.1.C2`) salen como
desconocidos con el código nuevo sugerido.

## Límites
Los datos están revisados en la fecha `version_datos` de la respuesta. El paquete no sabe si una
norma cambió después ni de recursos judiciales: hay un contencioso contra el Decreto 61/2022 cuyo
resultado no consta. Para un documento oficial, confirma en el boletín.
