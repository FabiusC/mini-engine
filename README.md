# DAG JSON normalizado

`main.py` no consulta la API: consume las respuestas guardadas como snapshots en
`dag/`: `nodes.json`, `edges.json` y los archivos de operación cuyo nombre es su ID. Llama a
`merge_pipeline_clean(edges_json, nodes_json, operations_json)` y escribe el resultado
normalizado en `dag/pipeline_clean.json`, sobrescribiendo el archivo en cada generación.

La construcción de `pipeline_clean.json` está activada por defecto. Para omitirla al
invocar `main.py` desde Python, usa `main(build_pipeline_clean=False)`; el pipeline
de prueba `dag/pipeline_test.json` seguirá ejecutándose.

La salida tiene el mismo formato que `dag/pipeline.json`: listas `nodes` y `edges`,
sin duplicar los nodos dentro de las aristas. Cada nodo conserva `id`,
`input_ports`/`output_ports` (solo `id`, `ordinal`), `operation` (`id`, `name`) y
`parameters` como objeto. Se conservan también los nodos aislados.

Los parámetros se toman de cada nodo: se aceptan objetos o listas de registros
`{"name": "column", "value": "sales"}`. Las listas vacías o parámetros ausentes
se convierten en `{}`; se conservan los tipos JSON, incluidos `false`, `0`, listas,
objetos y `null`. Las listas con nombres duplicados o sin `name`/`value` provocan
errores explícitos. No se inventan valores a partir del pipeline de ejemplo.

Se omiten nodos, puertos, operaciones y aristas eliminados; también se omiten las
aristas conectadas a nodos eliminados. Una operación ausente, un ID de nodo
duplicado o una arista que referencia un nodo desconocido provoca un error.

`main.py` regenera `dag/pipeline_clean.json` desde las respuestas guardadas en
`nodes.json`, `edges.json` y los snapshots de operaciones, pero ejecuta
`dag/pipeline_test.json`. Este último es un pipeline de prueba independiente y
no se sobrescribe al generar el pipeline limpio. Para elegir el archivo ejecutado:

```python
from main import main

main(pipeline_file="pipeline_test.json")
```

El flujo normal ejecuta `pipeline_test.json`; `pipeline_clean.json` se conserva
como salida generada para inspección y no se usa para la ejecución de pruebas.

Los snapshots se completaron con dos nodos locales `read_csv` que leen
`data/orders_south_2018.csv` y `data/Orders_Central.csv`. `pipeline_clean.json`
refleja solamente los nodos y conexiones presentes en esos snapshots; no se le
inyecta un nodo de escritura durante la generación. El pipeline de prueba
`pipeline_test.json` incluye su propio `write_csv`, que persiste el resultado en
`output/processed_orders.csv`. El nodo de
`Orders_Central.csv` alimenta tanto el primer join como el segundo join (`name_1`);
por tanto, el DAG no tiene puertos externos desconectados. Los parámetros de los
nodos están en `dag/nodes.json` y se copian al pipeline limpio:
los tres joins usan `Customer ID`, el filtro usa `Profit > 100` y el límite es 100.
Los parámetros almacenados pueden sobreescribirse con `parameters=...` en el runner
o en `main` si se necesita otro comportamiento.

## Ejecutar el pipeline local

`dag/pipeline.json` define el DAG estructural que ejecuta `main.py`: lee los CSV,
los une por `Customer ID`, ordena por `Sales_south`, elimina `Discount`, renombra
`Profit_south`, convierte `Postal Code_south` a texto y escribe
`output/processed_orders.csv`. Cada nodo declara `operation.name`, sus puertos y
`parameters`; las aristas conectan puertos por ID. Las rutas son relativas a la raíz
del proyecto.

El pipeline previo de lectura, join, operaciones de texto y transformaciones
numéricas se conserva en `dag/pipeline_join_text_numeric.json`.

`PipelineRunner` ordena los nodos por sus aristas y busca cada operación en
`core/operation_registry.py`, que la dirige directamente al método estático del
procesador concreto. Las clases de `tableau_engine/interfaces/` definen contratos
abstractos por categoría; los procesadores en `tableau_engine/functions/` los
implementan:

| Categoría | Operaciones | Parámetros |
|---|---|---|
| io | `read_csv`, `write_csv` | `filepath` |
| structural | `inner_join`, `outer_join`, `sort`, `add_column`, `drop-column`, `rename-column`, `change-data-type` | `left_on`, `right_on`, `suffixes`; `column`, `direction`; `column_name`, `value`; `column`; `column`, `new_name`; `column`, `new_type` |
| row | `limit`, `filter` | `limit`; `column`, `operator`, `value` |
| text | `uppercase`, `lowercase` | `column`, `new_column`, `new_column_name` |
| numeric | `absolute`, `ceiling`, `clean_float`, `floor`, `max`, `min`, `power`, `round` | `column`, `new_column`, `new_column_name`; `column_a`, `column_b`, `new_column_name` para `max`/`min`; `value` para `power`; `decimals` para `round` |

En las operaciones antiguas de texto, `new_column: false` (por defecto) actualiza la columna
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

## Motor de operaciones de datos

Todas las operaciones siguientes se pueden ejecutar mediante `PipelineRunner` usando
el nombre en `operation.name` y los argumentos en `parameters`. Las clases de
`tableau_engine/interfaces/` son interfaces abstractas sin implementación; las
implementaciones pandas están en los procesadores de `tableau_engine/functions/`.
Para invocar desde Python, se llama directamente al procesador o se usa
`execute_operation` desde `tableau_engine.core.operation_registry`.

### API de procesadores

`PandasDataProcessor` es el punto de acceso unificado al backend pandas, equivalente
al agrupador `PolarDataProcessor` del backend Polars. Expone instancias independientes
por categoría:

| Atributo | Procesador |
|---|---|
| `structure` | `StructuralProcessor` |
| `text` | `TextProcessor` |
| `number` | `NumericProcessor` |
| `row` | `RowProcessor` |
| `io` | `IOProcessor` |
| `conversion` | `ConversionProcessor` |
| `datetime` | `DateTimeProcessor` |
| `logical` | `LogicalProcessor` |

```python
from tableau_engine import PandasDataProcessor

pandas_processor = PandasDataProcessor()
df = pandas_processor.io.read_csv("data/orders_south_2018.csv")
df = pandas_processor.text.trim(df, column="Customer Name")
df = pandas_processor.number.absolute(
    df, column="Sales", create_new_column=True
)
```

El agrupador reutiliza las operaciones existentes sin convertir entre pandas y
Polars ni añadir una dependencia de Polars. Los imports directos de los procesadores
y el funcionamiento del DAG siguen disponibles sin cambios.

Las operaciones ya no se importan como funciones sueltas. Se importan las clases
`NumericProcessor`, `TextProcessor`, `StructuralProcessor`, `RowProcessor`,
`IOProcessor`, `DateTimeProcessor` y `LogicalProcessor` desde sus módulos respectivos.
Son métodos estáticos sin estado compartido; no necesitan instanciarse:

```python
from tableau_engine.functions.numeric import NumericProcessor
from tableau_engine.functions.text import TextProcessor

result = NumericProcessor.absolute(
    df,
    column="sales",
    create_new_column=True,
    new_column_name="absolute_sales",
)
result = TextProcessor.trim(result, column="customer_name")
```

Los imports anteriores como `from tableau_engine.functions.numeric import absolute`
deben migrarse a `NumericProcessor.absolute`. Los nombres de operación y los
parámetros de los pipelines JSON no cambian. Los helpers compartidos también
pertenecen a los procesadores: `StructuralProcessor.resolve_output_column`,
`StructuralProcessor.assign_result` y `RowProcessor.condition_mask`.

Las transformaciones no modifican los DataFrames de entrada, de modo que las ramas
del DAG permanecen independientes. Los errores de columnas, conversiones y
configuración se propagan; no se evalúan expresiones Python procedentes del JSON.

### Selección de columna de salida

Las transformaciones de texto, numéricas, fechas, lógicas y `change_data_type` aceptan:

- `create_new_column: false` (por defecto): sobrescribe la columna fuente.
- `create_new_column: true`: conserva la fuente y escribe en `new_column_name`, o en
  `<columna>_processed` si no se proporciona. Ante una colisión del nombre generado
  se usa `_processed_1`, `_processed_2`, etc.
- Un nombre explícito vacío, ya existente o indicado sin activar la creación
  provoca un error; nunca se sobrescribe otra columna accidentalmente.

`concat` toma la primera columna como fuente; `arithmetic`, `column_a`; `date_diff`,
`start_column`. `drop_column` y `rename_column` son excepciones estructurales:
eliminan o renombran, sin parámetros de creación de columna.

Se mantienen los nombres antiguos y sus parámetros: `uppercase`, `lowercase`,
`absolute`, `drop-column`, `rename-column`, `change-data-type`, `new_type` y
`new_column`. Este último sigue generando nombres indexados como `City_1`; el
parámetro nuevo genera `City_processed`. No se deben combinar controles contradictorios.
Las extensiones antiguas `min` y `max` siguen requiriendo `new_column_name`.

### Operaciones de tabla

| Nombre | Entradas del DAG | Parámetros |
|---|---|---|
| `input` | 0 | `source_type`: `csv`, `excel`, `parquet`, `sql`; `filepath_or_connection`; `table_or_sheet` opcional; `encoding="utf-8"`, `delimiter=","` para CSV |
| `output` | 1 | `destination_type`: `csv`, `excel`, `parquet`; `output_path`; `write_mode="overwrite"` o `"append"`; `encoding` y `delimiter` para CSV |
| `sample` | 1 | `sample_type`: `random` o `head`; `fraction_or_count`; `random_state` opcional |
| `join` | 2 | `how="inner"`: `inner`, `left`, `right`, `outer`; `left_on`, `right_on`: string o lista; `suffixes` opcional |
| `union` | 2 o más | `match_type="auto"` por nombres o `"manual"` por posición |
| `aggregate` | 1 | `group_by`: lista; `aggregations`: diccionario de columnas a funciones pandas, por ejemplo `{"sales": "sum"}` |
| `pivot` | 1 | `pivot_type`: `columns_to_rows` o `rows_to_columns`; `index_cols`, `target_col`, `values_col` |
| `filter` | 1 | `column`, `operator`: `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `isnull`; `value` (se omite con `isnull`) |

- Las rutas locales nuevas también se resuelven respecto a `base_dir`; las conexiones
  SQL no se tratan como rutas. SQL requiere `table_or_sheet` como nombre de tabla y
  una URL SQLAlchemy. Para motores distintos de SQLite hay que instalar su driver.
- Excel lee la primera hoja si no se especifica otra. Se incluyen `openpyxl`,
  `pyarrow` y `SQLAlchemy` para XLSX, Parquet y SQL; otros formatos de Excel pueden
  requerir motores adicionales de pandas.
- `output` devuelve el DataFrame recibido para mantener el flujo del DAG, sin guardar
  el índice. Crea directorios de destino. `append` crea el archivo si no existe y,
  si existe, exige los mismos nombres y orden de columnas. Los tres formatos leen
  y reescriben los datos combinados en memoria; CSV conserva una sola cabecera.
  Excel actualiza la primera hoja y conserva las demás (no garantiza conservar su formato).
- `sample` interpreta un entero como cantidad y un float entre 0 y 1 como fracción:
  `1` es una fila, `1.0` es el 100%. `head` trunca la cantidad fraccional;
  `random` usa el redondeo de pandas y muestrea sin reemplazo.
- `union manual` exige igual número de columnas y usa los nombres del primer flujo.
  `auto` permite columnas diferentes y rellena ausencias con nulos.
- `aggregate` conserva los grupos con claves nulas; `group_by=[]` agrega la tabla
  completa. Si se pasan listas de funciones, pandas conserva columnas MultiIndex.
- Unpivot convierte todas las columnas no incluidas en `index_cols` en pares
  `target_col`/`values_col`. Pivot exige claves únicas; no agrega duplicados
  implícitamente.
- Los filtros excluyen nulos de las comparaciones; `isnull` los selecciona.
  `contains` busca texto literal, no expresiones regulares.

### Transformaciones de campos

Además de los controles de salida, aceptan:

| Nombre | Parámetros |
|---|---|
| `drop_column` | `columns`: lista de nombres (también se mantiene `column`) |
| `rename_column` | `column`, `new_name` |
| `change_data_type` | `column`, `target_type`: `int`, `float`, `str`, `bool`, `datetime` u otro dtype pandas |
| `lower`, `upper`, `trim`, `ltrim`, `rtrim` | `column` |
| `substring` | `column`, `start` (base cero, admite negativos), `length` no negativa |
| `replace` | `column`, `old_text`, `new_text` (sustitución literal) |
| `split` | `column`, `delimiter` literal no vacío, `index` opcional (admite negativos) |
| `concat` | `columns`: lista no vacía de columnas, `separator=""` |
| `ceiling`, `floor`, `abs` | `column` |
| `round` | `column`, `decimals=0` |
| `arithmetic` | `column_a`, `operator`: `+`, `-`, `*`, `/`; `column_b_or_value`: nombre de columna (string) o constante numérica |
| `date_parser` | `column`, `date_format` (formato de `pd.to_datetime`) |
| `date_add`, `date_sub` | `column`, `unit`: `days`, `months`, `years`; `amount`: entero |
| `date_diff` | `start_column`, `end_column`, `unit="days"`: `days`, `months`, `years` |
| `extract_date_part` | `column`, `part`: `year`, `month`, `day`, `weekday` |
| `date`, `datetime`, `float`, `int`, `str` | `column`, `replace=true`, `new_column_name` cuando `replace=false` |
| `make_date` | `column_day`, `column_month`, `column_year`, `replace=false`, `new_column_name="date"` |
| `make_time` | `column_hour`, `column_minute`, `column_second`, `new_column_name="time"` |
| `make_date_time` | `column_date`, `column_hour`, `new_column_name="datetime"` |
| `coalesce`, `ifnull` | `column`, `default_value` |
| `conditional_map` | `column`, `condition_func`, `true_value`, `false_value` |
| `and`, `or` | `column`, `sentencia1`, `sentencia2`, `reemplazar_campo`, `nombre_nueva_columna` |
| `not`, `if`, `case`, `elseif` | `column`, `sentencia1`, `sentencia2` (según la operación), `reemplazar_campo`, `nombre_nueva_columna` |

- Las cadenas usan el dtype nullable `string`; `concat` propaga los nulos.
  `split` con `index` devuelve nulo para posiciones inexistentes. Sin `index`,
  exige `create_new_column=true` y expande en `<nombre>_0`, `<nombre>_1`, etc.
  (`<nombre>` es `new_column_name` o el nombre generado). Las colisiones se rechazan.
- Las conversiones de tipo siguen `astype` de pandas (por ejemplo, `bool` usa
  veracidad, no interpreta palabras como `"false"`); `datetime` usa `pd.to_datetime`.
  No se sustituyen datos inválidos silenciosamente.
- La aritmética convierte columnas con `pd.to_numeric`; dividir por cero provoca
  error. `ceiling` y `floor` usan las ufuncs vectorizadas de NumPy porque pandas
  no ofrece un método equivalente de Series.
- Las fechas usan `pd.to_datetime` y `pd.DateOffset`; los meses/años ajustan fechas
  al último día disponible (31 de enero + un mes = 28/29 de febrero).
  `date_diff` calcula fin menos inicio: días transcurridos fraccionarios o meses/años
  completos con signo, comparando día y hora del aniversario (31 de enero a 29 de
  febrero no completa un mes). Propaga `NaT`. `weekday` usa lunes=0 y domingo=6.
- Las conversiones están disponibles en `PandasDataProcessor.conversion` y en los
  pipelines. `date` normaliza la hora a medianoche; `datetime` conserva fecha y hora.
  `float`, `int` y `str` convierten con pandas y propagan errores de datos inválidos;
  `int` usa el dtype nullable `Int64`. `make_date` ajusta los días que exceden la
  duración del mes (por ejemplo, 31 de abril a 30 de abril), pero rechaza meses
  fuera de 1–12. `make_time` valida horas, minutos y segundos y devuelve valores
  `time`; `make_date_time` combina una fecha con una columna de hora.
- `coalesce`/`ifnull` reemplazan nulos y la cadena vacía, no espacios, ceros o `False`.
  El valor predeterminado debe ser compatible con el dtype de la columna.
- `conditional_map` acepta en JSON `{"operator": ">", "value": 100}` con los mismos
  operadores que `filter`. Desde Python también acepta una función vectorizada,
  por ejemplo `lambda series: series.gt(100)`, que debe devolver una Series booleana
  con el mismo índice. Las condiciones nulas seleccionan `false_value`.
- Las operaciones lógicas aceptan dos condiciones como `edad >= 18` o
  `region == "West"` usando `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains` e
  `isnull`. No ejecutan código. Primero evalúan cada sentencia como una máscara
  booleana y luego aplican la operación: `and`/`if` requieren ambas verdaderas;
  `or`/`case` son verdaderas si cualquiera lo es; `elseif` conserva el resultado
  verdadero de la primera condición y, si es falsa, usa la segunda. `not` niega
  la primera sentencia. Los valores nulos no satisfacen comparaciones y producen
  `False` en resultados lógicos. Para reemplazar la columna fuente,
  `reemplazar_campo=true`; para crear una columna, usa `reemplazar_campo=false`
  y proporciona `nombre_nueva_columna`.

Ejemplo de parámetros de un nodo:

```json
{
  "operation": {"name": "arithmetic"},
  "parameters": {
    "column_a": "sales",
    "operator": "*",
    "column_b_or_value": 1.21,
    "create_new_column": true,
    "new_column_name": "sales_with_tax"
  }
}
```
