# normativa-madrid

La normativa educativa de la Comunidad de Madrid como fuente de datos fiable para agentes: texto literal del boletín, códigos estables y procedencia (norma, ubicación y página) de cada elemento. Solo biblioteca estándar y sin red al consultar.

Origen: el código y los datos salen de la carpeta `normativa` del proyecto tiza (MIT, mismo autor), commit `210d608`.

## Uso

```
uv run normativa-madrid catalogo
uv run normativa-madrid ficha MAD.ESO.TECDIG.2
uv run normativa-madrid elemento <codigo>
uv run normativa-madrid norma "Decreto 27/2025"
uv run normativa-madrid buscar "texto" [--en <codigo>]
uv run normativa-madrid programacion <eso|bachillerato|fp>
```

Todas admiten `--curso-academico AAAA-AA` (salvo `norma`). Cada consulta imprime un único JSON en stdout y sale con 0; si falla, imprime `{"error": ..., "detalle": ..., "disponibles": [...]}` y sale con 2.

Como biblioteca: `normativa_madrid.cargar()`, `normativa_madrid.consulta` y `normativa_madrid.salida`.

## Desarrollo

```
uv run pytest -q
```

Las herramientas para regenerar los datos desde el boletín están en `herramientas/normativa/`.

## Licencia

Código bajo licencia MIT. Los textos normativos no tienen derechos de autor (art. 13 del Real Decreto Legislativo 1/1996, Ley de Propiedad Intelectual).
