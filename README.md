# mini-engine

## DAG y AST

`pipeline.dag.json` es la definición editable del DAG; `main.py` la carga y resuelve
las rutas relativas desde la raíz del proyecto. Cada nodo declara `id`, `operation`,
`inputs` y `parameters`. Edita ahí la operación o sus parámetros y vuelve a ejecutar
`python main.py` para generar `pipeline.ast.json` y procesar los datos.

El AST usa llamadas genéricas con referencias explícitas (`{"ref": "node_id"}`),
orden topológico y lista de salidas, por lo que puede inspeccionarse o consumirse sin
instanciar objetos Python del proyecto. La API también permite editar el DAG desde
Python; `to_ast()` compila el AST y `PipelineAST.run()` lo ejecuta:

```python
from src.engine import DAG

dag = DAG()
dag.add_node("orders", "load_csv", filepath="data/orders_south_2018.csv")
dag.add_node(
	"normalize_segment",
	"transform_string",
	inputs=("orders",),
	column="Segment",
	method="upper",
)

# Cambia los parámetros conservando las conexiones.
dag.update_operation(
	"normalize_segment",
	"transform_string",
	column="Segment",
	method="lower",
)
# O reemplaza la operación del nodo sin reconstruir el resto del DAG.
dag.update_operation(
	"normalize_segment",
	"filter_data",
	column="Segment",
	operator="==",
	value="Consumer",
)
pipeline_ast = dag.to_ast()
result = pipeline_ast.run()
```

Usa `dag.set_inputs(node_id, inputs)` para cambiar las conexiones. El DAG valida que
las referencias existan y rechaza ciclos. Las operaciones disponibles por defecto
son `load_csv`, `join_datasets`, `union_datasets`, `aggregate_data`, `drop_columns`,
`filter_data` y `transform_string`.