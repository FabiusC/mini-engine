# DAG JSON normalizado

`main.py` lee los snapshots guardados en `dag/`: `nodes.json`, `edges.json` y los
archivos de operación cuyo nombre es su ID. Llama a
`merge_pipeline_clean(edges_json, nodes_json, operations_json)` y escribe el resultado
compacto en `dag/pipeline_clean.json`.

La salida contiene una lista `edges`. Cada arista conserva sus IDs y añade `source_node`
y `target_node` con el ID, los puertos simplificados (`id`, `description`, `ordinal`) y
la operación (`id`, `name`). Los nodos eliminados se omiten. Si una arista referencia
un nodo que no está en la respuesta activa, el nodo anidado es `null`.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python main.py
```
