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

## Construcción y ejecución del DAG

`build_dag` en `tableau_engine/core/dag_graph.py` convierte las respuestas de la API
en objetos que el runner puede consumir:

1. Lee los registros de `data` en las respuestas de nodos y edges.
2. Indexa nodos y puertos por ID. Esto permite validar que cada edge conecte el puerto
  de salida de su nodo origen con el puerto de entrada de su nodo destino.
3. Guarda cada conexión usando el ID del input port como clave.
4. Recorre las dependencias recursivamente para ordenar productores antes que sus
  consumidores y detectar ciclos.
5. Une cada nodo con la definición de operación cuyo ID coincide con `operation_id`.
  Así obtiene el nombre de la operación y el orden de sus puertos.

Los helpers de `build_dag` corresponden a esas etapas: `_index_nodes`, `_index_ports`,
`_connect_edges`, `_topological_order` y `_build_operation_node`. La función principal
solo coordina el flujo.

`DAGRunner.run` en `tableau_engine/core/dag_runner.py` recibe un mapa de DataFrames
externos por input-port ID y, opcionalmente, parámetros por node ID. Para cada nodo:

1. `_resolve_inputs` toma cada DataFrame desde el output port anterior o desde el mapa
  de datasources si el puerto no tiene edge.
2. `_node_parameters` combina los parámetros guardados en el nodo con los overrides
  locales de prueba.
3. `_execute_node` selecciona la fachada de la operación: estructural, filas o texto.
4. El resultado se guarda por node ID y por output-port ID para los siguientes nodos.

En el snapshot actual, `Nodo_4` requiere dos datasources externos y `name_1` requiere
uno. Esos puertos no tienen edge, así que deben aparecer en `datasources`; el runner
se detiene con un error claro si falta alguno. Los inputs conectados se procesan solo
después de que su productor haya generado el DataFrame.
python -m pip install -r requirements.txt
python -m pytest -q
python main.py
```
