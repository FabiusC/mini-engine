# mini-engine

Motor simple para transformar texto con dos funciones: `UPPER` y `LOWER`.

## Flujo

`main.py` lee `data/orders_south_2018.csv`, carga `pipeline.dag.json`, ejecuta
las transformaciones y guarda `output/processed_orders.csv`. El CSV Central se
conserva como dato de entrada disponible, pero ya no se combina con South.

El DAG contiene una lista de nodos ordenados y un `output`. Cada nodo declara:

- `id`: identificador único; `source` está reservado para el dataframe original.
- `input`: `source` o el ID de un nodo anterior.
- `operation`: `UPPER` o `LOWER`.
- `column`: columna de texto que se transforma.

Para modificar el flujo, edita las operaciones, columnas o conexiones del JSON.
Los nodos se ejecutan en el orden escrito: no hay ordenamiento automático ni AST.
Las referencias hacia nodos posteriores o inexistentes se rechazan. Cada operación
produce una copia y conserva los valores nulos. Una columna inexistente genera
un `KeyError` de Pandas.

El runner solo conecta nodos; `TextInterface` selecciona la función atómica de
`tableau_engine/functions/text/`. La lectura y escritura CSV pertenecen a `main.py`.

## Ejecución

```bash
python -m pip install -r requirements.txt
python main.py
python -m pytest -q
```