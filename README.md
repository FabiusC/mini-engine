# mini-engine

Motor simple que cruza los CSV de South y Central y transforma columnas de texto
con `UPPER` y `LOWER`.

## Flujo

`main.py` lee ambos CSV, carga `pipeline.dag.json`, ejecuta el join y las
transformaciones de texto, y guarda `output/processed_orders.csv`.

El DAG contiene una lista de nodos ordenados y un `output`. Los nodos `JOIN` declaran
dos fuentes en `inputs`, sus claves y el tipo de cruce. Los nodos de texto declaran:

- `id`: identificador único; `source` está reservado para el dataframe original.
- `input`: una fuente o el ID de un nodo anterior.
- `operation`: `UPPER` o `LOWER` para texto.
- `column`: columna de texto que se transforma.

Para modificar el flujo, edita las operaciones, columnas o conexiones del JSON.
Los nodos se ejecutan en el orden escrito: no hay ordenamiento automático ni AST.
Las referencias hacia nodos posteriores o inexistentes se rechazan. Cada operación
produce una copia y conserva los valores nulos. Una columna inexistente genera
un `KeyError` de Pandas.

El runner solo conecta nodos; `TextInterface` selecciona la función atómica de
`tableau_engine/functions/text/`. El join usa `Customer ID` con tipo `inner`; al
coincidir varias órdenes de un mismo cliente, el resultado puede contener más filas
que cualquiera de las fuentes. El módulo `tableau_engine/io.py` expone
`read_datasource(filepath)`: lee un CSV y devuelve un DataFrame, intentando UTF-8
y luego Latin-1. Acepta rutas `str` o `Path`; los errores de archivo se propagan.
`main.py` usa este módulo para cargar los datos y guarda el resultado con `to_csv`.

## Structural

`tableau_engine/structural.py` contiene únicamente `join`, que cruza dos DataFrames
por una o varias columnas sin modificar las entradas:

```python
from tableau_engine.structural import join

result = join(orders, customers, left_on="Customer ID", right_on="Customer ID")
```

`how` admite `inner` (por defecto), `left`, `right` y `outer`. Esta función se usa
directamente desde Python; el DAGRunner sigue dedicado a texto.

## Ejecución

```bash
python -m pip install -r requirements.txt
python main.py
python -m pytest -q
```