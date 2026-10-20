# DAG JSON normalizado

`main.py` no consulta la API: consume las respuestas guardadas como snapshots en
`dag/`: `nodes.json`, `edges.json` y los archivos de operación cuyo nombre es su ID. Llama a
`merge_pipeline_clean(edges_json, nodes_json, operations_json)` y escribe el resultado
compacto en `dag/pipeline_clean.json`.

La construcción de `pipeline_clean.json` está activada por defecto. Para omitirla al
invocar `main.py` desde Python, usa `main(build_pipeline_clean=False)`; el pipeline
local de `dag/pipeline.json` seguirá ejecutándose.

La salida contiene una lista `edges`. Cada arista conserva sus IDs y añade `source_node`
y `target_node` con el ID, los puertos simplificados (`id`, `description`, `ordinal`) y
la operación (`id`, `name`). Los nodos eliminados se omiten. Si una arista referencia
un nodo que no está en la respuesta activa, el nodo anidado es `null`.

## Ejecutar el pipeline local

`dag/pipeline.json` define el DAG estructural que ejecuta `main.py`: lee los CSV,
los une por `Customer ID`, ordena por `Sales_south`, elimina `Discount`, renombra
`Profit_south`, convierte `Postal Code_south` a texto y escribe
`output/processed_orders.csv`. Cada nodo declara `operation.name`, sus puertos y
`parameters`; las aristas conectan puertos por ID. Las rutas son relativas a la raíz
del proyecto.

El pipeline previo de lectura, join, operaciones de texto y transformaciones
numéricas se conserva en `dag/pipeline_join_text_numeric.json`.

`PipelineRunner` ordena los nodos por sus aristas y delega cada operación en la
fachada de su categoría mediante `core/operation_registry.py`:

| Categoría | Operaciones | Parámetros |
|---|---|---|
| io | `read_csv`, `write_csv` | `filepath` |
| structural | `inner_join`, `outer_join`, `sort`, `add_column`, `drop-column`, `rename-column`, `change-data-type` | `left_on`, `right_on`, `suffixes`; `column`, `direction`; `column_name`, `value`; `column`; `column`, `new_name`; `column`, `new_type` |
| row | `limit`, `filter` | `limit`; `column`, `operator`, `value` |
| text | `uppercase`, `lowercase` | `column`, `new_column`, `new_column_name` |
| numeric | `absolute`, `ceiling`, `clean_float`, `floor`, `max`, `min`, `power`, `round` | `column`, `new_column`, `new_column_name`; `column_a`, `column_b`, `new_column_name` para `max`/`min`; `value` para `power`; `decimals` para `round` |

En las operaciones de texto, `new_column: false` (por defecto) actualiza la columna
original. Con `true`, el resultado va a `new_column_name` o, si no se indica, a la
columna original con el siguiente índice libre (`City_1`, `City_2`, ...).

Las operaciones numéricas usan la misma selección de columna destino. `round` acepta
`decimals`; en el pipeline de ejemplo, `absolute` y `ceiling` crean columnas nuevas,
mientras que `floor` y `round` actualizan las columnas originales.

Los joins infieren la clave solo si hay una única columna común; con estos CSV hay que
indicar `left_on` y `right_on`.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python main.py
```
