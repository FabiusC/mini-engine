# Pipeline de prueba

El directorio `dag/` contiene snapshots locales de la API: `nodes.json`,
`edges.json` y una respuesta de operación por ID. `load_dag("dag")` enlaza
los puertos usando `source_output_port_id` y `target_input_port_id`, y ordena
los nodos por sus dependencias.

## Ejecución

`python main.py` muestra el orden de ejecución y los puertos requeridos que no
tienen conexión. Para ejecutar el DAG con datos de prueba, crea `dag/runtime.json`
con DataFrames de entrada identificados por **input port ID** y los parámetros
locales para cada nodo:

```json
{
  "datasources": {
    "<unconnected-input-port-id>": "data/example.csv"
  },
  "parameters": {
    "<node-id>": {
      "left_on": "id",
      "right_on": "id",
      "limit": 100,
      "column": "Region",
      "operator": "==",
      "value": "South"
    }
  }
}
```

Los parámetros deben coincidir con la operación correspondiente: joins requieren
`left_on` y `right_on`, `limit` requiere `limit`, y `filter` requiere `column`,
`operator` y `value`. No se infieren claves ni condiciones. Las respuestas actuales
de la API dejan tres puertos requeridos desconectados y no incluyen esos parámetros;
por eso el runner los exige al configurar la ejecución. El AST no forma parte de este
flujo.

Las operaciones se mantienen modulares: `StructuralInterface` enruta
`inner_join`/`outer_join`, `RowInterface` enruta `limit`/`filter` y `TextInterface`
enruta `UPPER`/`LOWER`. Cada interfaz delega a funciones puras de `functions/`.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python main.py
```