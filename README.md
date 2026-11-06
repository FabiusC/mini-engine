# DAG Script Builder

El repositorio genera un **script genérico** a partir de un DAG. Un worker lo
ejecuta después. Está dividido en dos partes independientes:

| Carpeta | Responsabilidad |
|---|---|
| [`script-builder/src/`](script-builder/src) | Lee el DAG, valida su topología y genera `<pipeline_id>.py` + `manifest.json` en `output/<pipeline_id>/`. No ejecuta operaciones ni lee datasets. |
| [`workers/src/`](workers/src) | Emula los workers de Pandas y Polars: verifica el manifest, inyecta la ruta del archivo de entrada y ejecuta el script generado. |

En la raíz se quedan los insumos y la documentación compartidos: `dag/` (respuestas
JSON guardadas de los endpoints), `data/` (archivos de entrada), `docs/`, `catalogo_operaciones.xlsx`, este
README, `requirements.txt` y `pytest.ini`.

```text
dag/*.json (respuestas de la API: pipelines, nodes, edges, operation)
    → script_builder.__main__     (CLI)
    → load_api_pipeline           (dag/pipeline_clean.py: clasifica por `code`, normaliza al formato del builder)
    → build_artifact              (codegen/builder.py)
        → build_plan              (ir/plan.py: catálogo, validaciones, orden topológico de dag/pipeline_graph.py)
        → PandasEmitter | PolarsEmitter (codegen/: extrae solo las operaciones usadas)
        → build_manifest          (artifacts/manifest.py: hashes, perfil, esquema de parámetros)
    → output/<pipeline_id>/<pipeline_id>.py + manifest.json
    → workers: load_artifact (verifica) → ruta de entrada (workers/settings.py) → PandasWorker | PolarsWorker → python <pipeline_id>.py
```

El builder **no consulta ningún endpoint**: solo consume las respuestas JSON que
ya están guardadas en `dag/` (ver [DAG desde las respuestas de la API](#dag-desde-las-respuestas-de-la-api)).

Diagramas: [docs/ARCHITECTURE_DAG_SCRIPT_BUILDER.md](docs/ARCHITECTURE_DAG_SCRIPT_BUILDER.md)
(contexto en la arquitectura), [docs/REPOSITORY_FLOW.md](docs/REPOSITORY_FLOW.md)
(flujo del repositorio) y [docs/CODEGEN_COMPONENTS.md](docs/CODEGEN_COMPONENTS.md)
(clases y funciones).

## Estructura

```text
script-builder/
  requirements.txt
  src/
    main.py                     # entrada: python script-builder/src/main.py
    script_builder/
      __main__.py               # CLI del builder
      dag/                      # pipeline_graph (topología) y pipeline_clean (respuestas API → pipeline)
      ir/                       # catálogo de operaciones, validación, expresiones fx, plan ordenado
      codegen/                  # builder, emitters pandas/polars, runtime y notebook
      artifacts/manifest.py     # contrato manifest.json
      operations/pandas/        # implementaciones fuente que el emitter pandas copia al script
      operations/polars/        # implementaciones fuente que el emitter polars copia al script
  tests/
    fixtures/                   # DAG de ejemplo en el formato interno (pipeline_test, pipeline, pipeline_codegen)
workers/
  requirements-pandas.txt
  requirements-polars.txt
  src/
    main.py                     # entrada: python workers/src/main.py
    workers/
      __main__.py               # CLI del worker
      settings.py               # RUTA HARDCODEADA del archivo de entrada (INPUT_FILE_PATH / INPUT_FILE_PATHS)
      artifact.py               # load_artifact: valida manifest y hashes SHA-256
      base.py                   # Worker.run: comprueba framework y módulos, inyecta rutas, lanza <pipeline_id>.py sin shell
      pandas_worker.py, polars_worker.py
  tests/
```

El script generado **no importa `script_builder`**. El builder transforma el AST
de los métodos de `operations/<framework>/` en funciones independientes. El
script solo incluye las operaciones que usa el DAG, así que el worker no necesita
este repositorio, solo el framework.

## Uso

```bash
python -m pip install -r requirements.txt   # builder + ambos workers + pytest

# 1. Generar el script (por defecto: dag/ → output/<pipeline_id>/<pipeline_id>.py, pandas)
python script-builder/src/main.py
python script-builder/src/main.py --framework polars --notebook
python script-builder/src/main.py script-builder/tests/fixtures/pipeline_codegen.json --pipeline-id orders

# 2. Ejecutarlo con el worker (por defecto: el último artefacto generado en output/)
python workers/src/main.py
python workers/src/main.py e6b4f425-1133-4cae-97ec-442f4cf2a24b
python workers/src/main.py output/orders --worker pandas
```

Opciones del builder:

| Opción | Por defecto |
|---|---|
| `pipeline` | carpeta `dag/` (respuestas de la API); también acepta un JSON ya normalizado |
| `--output-dir` | `output/<pipeline_id>/` (se reemplaza en cada ejecución) |
| `--pipeline-id` | carpeta: obligatorio solo si hay varios pipelines; archivo: su `pipeline_id` o el nombre del JSON |
| `--pipeline-version` | `current_version_id` del pipeline; si no hay, `1` |
| `--framework` | `pandas` (`pandas` o `polars`) |
| `--engine` | `python` |
| `--notebook` | también genera `<pipeline_id>.ipynb` |

Opciones del worker: `artifact` (carpeta del artefacto o `pipeline_id` dentro
de `output/`; por defecto, el último generado), `--worker` (por defecto el
framework del manifest), y `--params-file`, `--datasources-file` y `--base-dir`.
`--base-dir` es la base de las rutas relativas del DAG; por defecto, la raíz del
repositorio.

### Archivo de entrada del worker (ruta hardcodeada)

Los nodos "Leer archivo" de la API solo traen el ID del archivo (`archivo`), no
su ruta. El worker la toma de
[`workers/src/workers/settings.py`](workers/src/workers/settings.py):

```python
INPUT_FILE_PATH = REPOSITORY_ROOT / "data" / "netflix_titles.xlsx"   # lo leen todos los nodos de lectura
INPUT_FILE_PATHS: dict[str, Path] = {}                                # opcional: {file_id: ruta} por archivo
```

El manifest lista esos archivos en `input_files` (`file_<id>` → ID). El worker
pasa la ruta al script como parámetro `file_<id>`; un `--params-file` explícito
tiene prioridad. Si el archivo no existe, el worker falla antes de ejecutar.
`read_csv` lee `.csv`, `.xlsx`/`.xlsm`/`.xls` (Excel) y `.parquet` según la
extensión; Polars usa `fastexcel` para Excel.

El fixture `script-builder/tests/fixtures/pipeline_test.json` lee `data/orders_south_2018.csv` y
`data/Orders_Central.csv`.
Los une por `Customer ID`, aplica operaciones de texto, numéricas, lógicas y de
fecha, y escribe `output/processed_orders.csv` (1627 filas, 10 columnas). Pandas
y Polars producen el mismo CSV; una prueba end-to-end lo verifica.

El script también se ejecuta sin worker:

```bash
python output/<pipeline_id>/<pipeline_id>.py --base-dir . --params-file p.json [--datasources-file d.json]
```

El proceso imprime un resumen JSON con filas y columnas por nodo. Los errores se
propagan con traceback y un código de salida distinto de cero.

### API Python del builder

```python
import json
from pathlib import Path

from script_builder.codegen import PandasEmitter, build_artifact
from script_builder.ir import build_plan

pipeline = json.loads(Path("script-builder/tests/fixtures/pipeline_test.json").read_text())
plan = build_plan(pipeline, engine="python", framework="pandas")   # IR ordenado y validado
script = PandasEmitter().emit(plan)                                 # código fuente de demo.py
manifest = build_artifact(pipeline, "output/demo", pipeline_id="demo", pipeline_version="1")
```

`build_artifact` no sobrescribe un directorio existente salvo con
`overwrite=True`, que es lo que usa el CLI. El módulo generado expone
`run(datasources=None, parameters=None, base_dir=None)` y devuelve los
DataFrames por ID de nodo.

## Contrato del plan y validaciones

- `ir/catalog.py`: operaciones lógicas, aridad, esquema de parámetros, aliases
  y destinos soportados. Importar `script_builder.ir` no carga pandas.
- `ir/plan.py`: pasos en orden topológico (`dag/pipeline_graph.py`), entradas
  por nodo o por puerto externo, nodos terminales y parámetros de ejecución.
- `ir/validate.py`: valida el subconjunto de JSON Schema que usa el catálogo y
  las restricciones entre parámetros.
- Se rechazan ciclos, nodos duplicados o desconocidos y puertos inválidos o que
  no pertenecen al nodo indicado. También se rechazan ordinales repetidos y
  varias aristas hacia un mismo puerto de entrada. Una salida puede alimentar
  varios consumidores.
- Cada nodo produce **un DataFrame de salida**. Se rechazan nodos con varios
  puertos de salida.
- Una entrada sin arista es un datasource externo, no un error de topología. Se
  proporciona por ID de puerto al ejecutar.
- Los parámetros deben ser valores JSON finitos. Los tipos, las opciones, los
  obligatorios y los nombres desconocidos se validan antes de generar código. No
  se inventan parámetros ausentes.
- Las columnas, los tipos reales y las claves de join que dependen del dataset
  se validan al ejecutar.

Un valor `{"$param": "nombre"}` referencia un parámetro de ejecución. Se admiten
referencias anidadas en listas y objetos. Los valores constantes quedan en el
script. Usa referencias para rutas variables, conexiones y secretos, y no
publiques credenciales en el DAG. Los valores de ejecución no se interpretan
como código. Antes de ejecutar cualquier nodo se validan los parámetros
resueltos de todos los pasos.

`--datasources-file` acepta un JSON `{"<id-del-puerto>": "/data/input.csv"}`
(solo CSV). Para otros formatos usa nodos `input`.

## Matriz de compatibilidad

| Categoría | Operaciones |
|---|---|
| IO | `read_csv`, `write_csv`, `input` (CSV, Excel, Parquet, SQL), `output` (CSV, Excel, Parquet; overwrite/append) |
| Structural | `add_column`, `drop_column`, `rename_column`, `change_data_type`, `join`, `union`, `aggregate`, `pivot` |
| Row | `filter`, `limit`, `sort`, `sample` |
| Expresiones | `fx` / `function` |
| Conversion | `date`, `datetime`, `float`, `int`, `str`, `make_date`, `make_time`, `make_date_time` |
| Numeric | `absolute`, `clean_float`, `ceiling`, `floor`, `max`, `min`, `power`, `round`, `arithmetic` |
| Text | `lowercase`, `uppercase`, `proper`, `trim`, `substring`, `replace`, `split`, `concat_column`, `concat_text`, `contains`, `starts_with`, `ends_with`, `transform_left`, `transform_right`, `length` |
| Logical | `logical`, `and`, `or`, `not`, `if`, `elseif`, `case`, `coalesce` / `ifnull`, `conditional_map` |
| Date | `date_parser`, `date_parse`, `date_trunc`, `day`, `month`, `year`, `week`, `quarter`, `iso_quarter`, `iso_week`, `iso_week_day`, `iso_year`, `now`, `today`, `date_add`, `date_sub`, `date_diff`, `date_name`, `extract_date_part` |

Los aliases (`drop-column`, `inner_join`, `date add`, etc.) se normalizan en el
IR. `script_builder.ir.catalog.compatibility_matrix()` confirma que cada
operación canónica existe en Pandas y en Polars. Una prueba ejecuta cada
operación del catálogo a través de un script Polars generado.

Las operaciones Polars son nativas: no convierten los datasets a pandas. Para
coincidir con pandas, `read_csv` reintenta en Latin-1, las fechas de texto
infieren su formato a partir del primer valor, y los joins conservan el orden de
filas de `pandas.merge`. Diferencias propias del backend:

- IO Polars: solo CSV y Parquet. Excel y SQL son exclusivos de Pandas.
- Polars no tiene índice: `write_csv(index=True)` no escribe índice.

## AST de expresiones y notebooks

Ejemplo de nodo:

```json
{
  "id": "calculate",
  "operation": {"name": "fx"},
  "input_ports": [{"id": "calculate_in", "ordinal": 0}],
  "output_ports": [{"id": "calculate_out", "ordinal": 0}],
  "parameters": {
    "column_name": "net_sales",
    "expression": "col('Sales') * param('factor') if col('Sales') > 0 else 0"
  }
}
```

`ir/expressions.py` convierte la expresión en un árbol lógico, y cada emitter lo
traduce a expresiones nativas. No usa `eval`. Se admiten:

- Literales escalares, `col("nombre")` y `param("nombre")`.
- Aritmética, comparaciones simples, `and`/`or`/`not` y `a if c else b`.
- Las funciones `abs`, `upper`, `lower`, `is_null`, `coalesce`, `year`, `month` y `day`.

Se rechaza todo lo demás.

`--notebook` añade `<pipeline_id>.ipynb` con tres celdas: definiciones, parámetros y
datasources editables, y ejecución. El worker sigue ejecutando `<pipeline_id>.py`.

## Manifest y responsabilidades del worker

`artifacts/manifest.py` produce un contrato versionado con:

- Identidad y versión del pipeline, versión del IR y hash SHA-256 del plan.
- Destino (`engine`, `framework`), perfil `python-<framework>-v1` y dependencias.
- Entrypoint `<pipeline_id>.py`, hash SHA-256 de cada archivo y los argumentos del script.
- JSON Schema de parámetros nombrados, puertos externos y nodos terminales.
- `input_files`: parámetros `file_<id>` que el worker debe resolver a una ruta.

La generación es determinista: no incluye timestamps, UUID ni rutas locales. Los
hashes verifican integridad, **no autenticidad**.

El worker emulado ([`workers/src/workers`](workers/src/workers)) hace lo mínimo
que haría el pod:

1. `load_artifact` lee `manifest.json`, exige `manifest_version` `1`, un
   entrypoint `.py` simple listado en `files`, solo archivos permitidos, hashes correctos y engine
   `python`.
2. `Worker.run` rechaza artefactos de otro framework y comprueba que estén
   instalados los módulos requeridos (`pandas`/`numpy` o `polars`).
3. Resuelve las rutas de `input_files` con `workers/settings.py` y las escribe
   en un `--params-file` temporal.
4. Ejecuta `python <pipeline_id>.py --params-file … --datasources-file … --base-dir …`
   sin shell, con `cwd` en el artefacto, y devuelve el exit code.

Dispatcher, Kafka y Kubernetes quedan fuera de este repositorio.

## DAG desde las respuestas de la API

`dag/` contiene las respuestas guardadas de los endpoints (no se hace ninguna
consulta). El nombre de archivo no importa: cada respuesta se clasifica por su
`code`:

| `code` | Contenido |
|---|---|
| `PIPELINE_RETRIEVED` | pipelines (`id`, `name`, `current_version_id`) |
| `PIPELINE_NODES_LIST_RETRIEVED` | nodos con puertos, operación y parámetros |
| `PIPELINE_EDGES_LIST_RETRIEVED` | aristas entre puertos |
| `OPERATION_RETRIEVED` | una operación (el `name` se usa como operación del catálogo) |

Los archivos vacíos y los `code` desconocidos (p. ej. `OPERATION__TEMPLATE_RETRIEVED`)
se ignoran; un JSON inválido o `success: false` provoca un error.
`load_api_pipeline("dag")` hace la conversión:

- Filtra nodos y aristas por la versión actual del pipeline y omite los eliminados.
- Convierte los valores tipados (`value_string`, `value_int`, `value_bool`, …) y
  los nombres visibles de los parámetros (`Archivo`, `Nueva columna`, …) a los
  nombres del catálogo (`file_id`, `create_new_column`, …).
- `archivo` se convierte en `{"$param": "file_<id>"}` sobre `filepath` y se
  lista en `input_files` para que el worker ponga la ruta.
- Un `write_csv` sin ruta escribe en `output/<pipeline_id>/<node_id>.csv`.

El pipeline actual (`Netflix0`, `e6b4f425-1133-4cae-97ec-442f4cf2a24b`) lee el
archivo configurado, crea `title_lower` con `lowercase` y escribe
`output/e6b4f425-1133-4cae-97ec-442f4cf2a24b/198e4b46-3715-4890-bb19-41ba6ccd81e2.csv`.

`export_clean_pipeline("dag")` escribe el resultado normalizado en
`dag/pipeline_clean.json` (útil para inspeccionarlo); el builder lo ignora al
leer la carpeta.

Otros DAG de ejemplo en formato interno, usados por las pruebas:
`script-builder/tests/fixtures/pipeline_test.json`, `pipeline.json`
(estructural) y `pipeline_codegen.json` (parametrizado con `$param`).

## Pruebas

```bash
python -m pytest -q                     # script-builder/tests + workers/tests
python -m pytest -q workers/tests       # solo workers
```

`pytest.ini` agrega `script-builder/src`, `workers/src` y
`script-builder/tests` al `PYTHONPATH`. Las pruebas de operaciones ejecutan
cada operación a través del script generado (`builder_testing.run_operation`).
Las comparaciones golden usan `reference_run`, que llama a las operaciones
Pandas directamente, sin generar código.

## Implementaciones de operaciones

Las clases `*Operations` de `script-builder/src/script_builder/operations/pandas/`
y de `.../operations/polars/` son la **fuente** del código generado. Cada carpeta
está segmentada igual (io, structural, row, text, numeric, date, logical,
conversion). Cada emitter copia al script solo los métodos que usa el DAG,
convertidos en funciones independientes. No se ejecutan desde el builder.

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

Se mantienen los nombres antiguos de operaciones: `uppercase`, `lowercase`,
`absolute`, `drop-column`, `rename-column`, `change-data-type` y `new_type`.
`create_new_column` es el único parámetro booleano para seleccionar una columna nueva.
Las extensiones `min` y `max` siguen requiriendo `new_column_name`.

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
| `date`, `datetime`, `float`, `int`, `str` | `column`, `create_new_column=false`, `new_column_name` cuando `create_new_column=true` |
| `make_date` | `column_day`, `column_month`, `column_year`, `create_new_column=true`, `new_column_name="date"` |
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
- Las conversiones `date`, `datetime`, `float`, `int` y `str` están disponibles
  en los pipelines. `date` normaliza la hora a medianoche; `datetime` conserva fecha y hora.
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
