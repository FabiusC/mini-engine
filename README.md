# mini-engine

## Arquitectura

`pipeline.dag.json` define el DAG con nodos que declaran `category`, `operation`,
`inputs` y `params`. `main.py` carga el JSON y `DAGRunner` recorre las dependencias
en orden topológico, despachando cada nodo a la interfaz de su categoría. La ejecución
no depende del AST; `pipeline.ast.json` se genera como representación genérica para
inspección o consumo por otras herramientas.

Las operaciones atómicas viven en `tableau_engine/functions/` y sus routers en
`tableau_engine/interfaces/`. Cada categoría tiene dos funciones:

- `io`: `LOAD_CSV`, `SAVE_CSV`
- `text`: `UPPER`, `LOWER`
- `numeric`: `CEILING`, `FLOOR`
- `dates`: `PARSE`, `DATE_PART`
- `casting`: `CHANGE_TYPE`, `TO_NUMERIC`
- `structural`: `JOIN`, `UNION`

Para cambiar el pipeline, edita el nodo correspondiente en `pipeline.dag.json`. Por
ejemplo, cambia `operation` de `UPPER` a `LOWER` para pasar `Segment` a minúsculas.
Para cambiar la normalización, edita `operation` a `LOWER`. Cada nodo usa solo
operaciones de su categoría, y las conexiones se cambian editando sus IDs en `inputs`.

La estructura JSON del DAG es versionada y portable; las rutas relativas se resuelven
desde la raíz del proyecto. La exportación AST usa llamadas con referencias explícitas
como `{"ref": "combined_orders"}` y puede generarse sin utilizarse para ejecutar.

## Ejecución

```bash
python -m pip install -r requirements.txt
python main.py
```

El resultado se escribe en `output/processed_orders.csv`; la representación AST se
escribe en `pipeline.ast.json`.