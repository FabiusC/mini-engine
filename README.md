# DAG Script Builder

El proyecto permite **compilar un DAG a un artefacto ejecutable**, sin ejecutar
operaciones ni leer datasets durante la generación:

```text
API responses / pipeline JSON
    → (optional caller step) merge_pipeline_clean
    → normalized pipeline JSON
    → build_plan (IR lógico y validaciones)
    → Emitter (pandas / Polars / PyArrow / PySpark)
    → main.py + manifest.json [+ pipeline.ipynb]
    → solicitud de ejecución → dispatcher → worker del perfil aprobado
```

El diagrama de contexto que conecta el builder con la UI/API, Kafka y los workers
de Kubernetes está en [ARCHITECTURE_DAG_SCRIPT_BUILDER.md](ARCHITECTURE_DAG_SCRIPT_BUILDER.md).
El detalle de los módulos del repositorio y del flujo interno de generación de
scripts está en [REPOSITORY_FLOW.md](REPOSITORY_FLOW.md).
`merge_pipeline_clean` no se invoca automáticamente desde el CLI ni desde
`build_artifact`: quien integra el builder debe entregar el pipeline normalizado.

El worker no necesita instalar este proyecto ni tener nuestro catálogo de
operaciones. El script generado incluye llamadas explícitas por nodo y **solo las
funciones nativas necesarias**, junto con sus auxiliares. El builder transforma a
funciones independientes el AST de métodos locales de operaciones;
así reutiliza sus validaciones y semántica sin duplicar implementaciones. No se
procesa texto del DAG como código Python ni se usa `eval`.

`python main.py ...` ahora compila artefactos, con los mismos argumentos que
`python -m engine.codegen ...`. `PipelineRunner` y las funciones Python históricas
de `main.py` se mantienen solo como referencia para tests y debug local.
Los scripts no requieren este repositorio. El launcher opcional del worker usa
únicamente `engine/dispatch`, el validador de esquemas y los inicializadores de
paquete; no importa el catálogo, los emitters ni nuestros processors.

## Compilar y ejecutar

Desde la raíz del proyecto:

```bash
python -m engine.codegen dag/pipeline_codegen.json \
  --output-dir /tmp/orders-v1-pandas \
  --pipeline-id orders \
  --pipeline-version 1
```

Para Polars y notebook:

```bash
python main.py dag/pipeline_codegen.json \
  --output-dir /tmp/orders-v1-polars \
  --pipeline-id orders --pipeline-version 1 \
  --framework polars --notebook
```

También se aceptan `--framework pyarrow` y `--framework pyspark`. Todos usan
`--engine python`. La compilación no importa ni ejecuta los runtimes opcionales;
deben estar instalados en el entorno que ejecuta el artefacto.
PySpark se inicia con `spark-submit`, no con un worker pandas:

```bash
spark-submit --master 'local[1]' /tmp/orders-v1-spark/main.py \
  --params-file /tmp/orders-params.json
```

La ruta del ejemplo Spark presupone haber generado ese artefacto con
`--framework pyspark`.

El directorio de salida **no debe existir**: los artefactos publicados no se
sobrescriben. Usa otra ruta para una nueva compilación. También se puede compilar
`dag/pipeline.json`, que contiene el ejemplo estructural con parámetros fijos.

Para el ejemplo parametrizado, crea un archivo de parámetros de ejecución:

```json
{
  "source_csv": "data/orders_south_2018.csv",
  "output_csv": "/tmp/orders-result.csv",
  "row_limit": 100
}
```

Guardándolo como `/tmp/orders-params.json`, ejecuta:

```bash
python /tmp/orders-v1-pandas/main.py \
  --params-file /tmp/orders-params.json \
  --base-dir /workspaces/mini-engine
```

`--base-dir` debe apuntar al directorio de datos del entorno de ejecución; la ruta
mostrada es solo la de este workspace. Si no se proporciona, las rutas relativas
usan el directorio de trabajo del proceso. Las conexiones SQL y URI con esquema
no se resuelven como rutas relativas.

El proceso imprime un resumen final JSON con filas y columnas por nodo. Spark
puede emitir diagnósticos adicionales antes del resumen. Los datos se
persisten únicamente mediante los nodos de salida declarados en el DAG. Los
errores se propagan con traceback y código de salida distinto de cero; no se
reportan como ejecuciones exitosas.

### API Python

```python
import json
from pathlib import Path

from engine.ir import build_plan
from engine.codegen import PandasEmitter, build_artifact

pipeline = json.loads(Path("dag/pipeline_codegen.json").read_text())
plan = build_plan(pipeline, engine="python", framework="pandas")
logical_plan = plan.to_dict()  # Representación JSON independiente de pandas.
script = PandasEmitter().emit(plan)

manifest = build_artifact(
    pipeline,
    "/tmp/orders-v2-pandas",
    pipeline_id="orders",
    pipeline_version="2",
)
```

El módulo generado expone
`run(datasources=None, parameters=None, base_dir=None)`, que devuelve DataFrames
por ID de nodo, como `PipelineRunner.run`. Aquí `parameters` es un mapa de
**parámetros nombrados**, no las sobreescrituras por nodo del runner.

## Contrato del plan y validaciones

- `engine/ir/catalog.py`: operaciones lógicas, aridad, esquema de parámetros y
  destinos soportados. Importar `engine.ir` no carga pandas.
- `engine/ir/plan.py`: pasos ordenados, entradas por nodo o puerto externo, nodos
  terminales y parámetros de ejecución requeridos. Reutiliza `pipeline_graph`.
- `engine/ir/validate.py`: valida el subconjunto de JSON Schema utilizado por el
  catálogo y restricciones entre parámetros.
- Se rechazan ciclos, nodos duplicados o desconocidos, puertos inválidos o que no
  pertenecen al nodo indicado, ordinales repetidos y varias aristas hacia un mismo
  puerto de entrada. Una salida puede alimentar varios consumidores.
- Esta versión admite **un DataFrame de salida por nodo**. Se rechazan nodos con
  múltiples puertos de salida, en lugar de tratar resultados distintos como uno.
- Una entrada sin arista representa un datasource externo, no un error de
  topología. Debe proporcionarse por ID de puerto al ejecutar.
- Los parámetros deben ser valores JSON finitos; los tipos, opciones, parámetros
  obligatorios y nombres desconocidos se validan antes de generar código.
  `limit` requiere un entero no negativo, sin las conversiones implícitas del
  runner. No se inventan parámetros ausentes en snapshots.
- Las columnas, tipos reales de datos y claves de join que dependan del dataset
  se validan al ejecutar. Esta fase no implementa inferencia de esquemas.

Un valor `{"$param": "nombre"}` referencia un parámetro de ejecución. Se admiten
referencias anidadas en listas y objetos; esta sintaxis queda reservada en las
declaraciones. Los valores constantes permanecen en el script: usa referencias
para rutas variables, conexiones y secretos, y no publiques credenciales dentro
del DAG. Los valores proporcionados en ejecución no se interpretan como código.

Los parámetros nombrados faltantes o desconocidos y los datasources ausentes
producen errores explícitos. Antes de ejecutar cualquier nodo se validan los
parámetros resueltos de todos los pasos.

Para entradas externas desde CLI, `--datasources-file` acepta un JSON
`{"<id-del-puerto>": "/data/input.csv"}`. Desde Python,
`datasources={"<id-del-puerto>": dataframe}` permite conservar tipos e índices.
La interfaz CLI admite CSV para estos puertos; usa nodos `input` para otros
formatos compatibles con el destino.

## Matriz de compatibilidad

| Categoría | Operaciones |
|---|---|
| IO | `read_csv`, `write_csv`, `input` (CSV, Excel, Parquet, SQL), `output` (CSV, Excel, Parquet; overwrite/append) |
| Structural | `add_column`, `drop_column`, `rename_column`, `change_data_type`, `join`, `union`, `aggregate`, `pivot` |
| Row | `filter`, `limit`, `sort`, `sample` |
| Expresiones | `fx` / `function` |
| Logical (pandas) | `logical`, `and`, `or`, `not`, `if`, `elseif`, `case`, `coalesce` / `ifnull`, `conditional_map` |
| Date (pandas) | `date_parser`, `date_parse`, `date_trunc`, `day`, `month`, `year`, `week`, `quarter`, `iso_quarter`, `iso_week`, `iso_week_day`, `iso_year`, `now`, `today`, `date_add`, `date_sub`, `date_diff`, `date_name`, `extract_date_part` |

Se conservan los aliases `drop-column`, `rename-column`, `change-data-type`,
`inner_join`, `outer_join`, `left_join` y `right_join`; se normalizan en el IR.
Para muestreos reproducibles usa `random_state`. La matriz por destino está en
`engine.ir.catalog.compatibility_matrix()`:

| Operaciones | pandas | Polars | PyArrow | PySpark |
|---|---|---|---|---|
| IO CSV/Parquet, add/drop/rename, filter/limit/sort, union | Sí | Sí | Sí | Sí |
| IO Excel/SQL, append | Sí | No | No | No |
| join, change_data_type | Sí | Sí | No | Sí |
| aggregate, pivot, sample | Sí | No | No | No |
| fx (incluye lógica y extracción de fechas) | Sí | Sí | No | Sí |
| year/month/day | Sí | Sí | No | Sí |
| Demás nodos lógicos históricos y fechas | Sí | No | No | No |

No se convierten datasets a pandas para simular una operación en otro destino.
Las combinaciones no soportadas se rechazan al compilar. Las restricciones sobre
parámetros dinámicos se vuelven a comprobar antes de ejecutar los nodos:

- IO nativo: UTF-8, delimitador de un carácter, CSV/Parquet y overwrite.
- Joins nativos: claves explícitas con el mismo nombre en ambos lados,
  sufijos predeterminados `_x`/`_y`, inner/left/right/outer y coincidencia de nulls.
- Cast nativo: int/int64, float/float64, str/string, bool y datetime.
- Los destinos nativos no tienen índice pandas: se rechaza `write_csv(index=True)`.
- Spark escribe **directorios** con part-files, no un único CSV/Parquet.
- Spark no garantiza orden de filas sin `sort`. No se promete igualdad universal
  de tipos, NaN, nulos, booleanos o parsing de fechas entre frameworks: se utilizan
  sus semánticas nativas. Las pruebas comparan resultados para contratos comunes.
- Spark 4 requiere Java >=17. Master, credenciales, conectores, timezone y
  configuración de executors pertenecen a la imagen/perfil de ejecución.
  Los contadores CLI de Spark ejecutan acciones; no se añade caching implícito.

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

`engine/ir/expressions.py` convierte la expresión a un árbol lógico incluido en el
IR v2, y el emitter lo traduce a expresiones nativas. No usa `eval` ni interpreta
Python arbitrario. Se admiten literales escalares, `col("nombre")`, `param("nombre")`,
aritmética, comparaciones simples, `and`/`or`/`not`, condicionales `a if c else b`,
y las funciones `abs`, `upper`, `lower`, `is_null`, `coalesce`, `year`, `month`, `day`.
Se rechazan atributos, indexación, imports, lambdas, comprehensions y llamadas
fuera de esa lista; las expresiones tienen límites de longitud y complejidad.
La expresión debe ser estática al compilar; sus valores variables usan `param`.
`fx` crea o reemplaza la columna indicada sin modificar el input.

Los nodos lógicos históricos conservan su contrato en pandas. No se cambia su
significado: por ejemplo, `if`/`case` históricos producen máscaras booleanas;
para valores condicionales nuevos se usa `fx` o `conditional_map`.

`--notebook` añade `pipeline.ipynb` con tres celdas: definiciones, parámetros y
datasources editables, y ejecución. El notebook no contiene la llamada argparse
del script. Completa la segunda celda antes de ejecutar un DAG parametrizado.
El worker sigue ejecutando `main.py`; el notebook es una salida adicional para
inspección y ejecución interactiva, con hash propio en el manifest.

## Manifest y responsabilidades del worker

`engine/artifacts/manifest.py` produce un contrato versionado con:

- Identidad y versión del pipeline, versión del IR y hash SHA-256 del plan.
- Destino, perfil `python-<framework>-v1` y dependencias requeridas.
- Entrypoint `main.py`, hash SHA-256 del script y argumentos del launcher.
- JSON Schema de parámetros nombrados, puertos externos y nodos terminales.

La generación es determinista: no agrega timestamps, UUID ni rutas locales del
builder al artefacto. Los hashes verifican integridad, **no autenticidad**.
El script necesita Python >=3.10 y las dependencias del perfil indicadas en el
manifest, preinstaladas en una imagen aprobada; no instala paquetes.

El dispatcher debe resolver el perfil a una imagen permitida. El worker debe
descargar desde almacenamiento autorizado, validar el manifest y los hashes,
preparar parámetros y secretos, ejecutar con argumentos separados (sin shell)
y reportar logs y exit code. El script no se autoverifica: la verificación
corresponde al launcher externo.

## Dispatcher y Kafka en entorno aislado

`engine/dispatch` implementa el contrato de solicitud, un dispatcher que prepara
Jobs, un launcher que verifica y ejecuta artefactos y adaptadores Kafka opcionales.
**No se conecta a Kafka ni Kubernetes al importar o compilar.** No se ha desplegado
ningún servicio. El adaptador de almacenamiento incluido solo lee `file://` dentro
de una raíz permitida (incluidos controles sobre symlinks); S3/HTTPS requieren
implementar el protocolo `ArtifactStore.read(uri)` con autorización y límites
apropiados. No hay un downloader remoto abierto por defecto.

Crear una solicitud local:

```bash
python -m engine.dispatch request \
  --artifact-dir /tmp/orders-v1-polars \
  --execution-id orders-run-001 \
  --params-file /tmp/orders-params.json \
  --output /tmp/orders-request.json
```

La solicitud v1 incluye `execution_id`, `manifest_uri`, `manifest_sha256`,
`parameters` y `datasources`. El dispatcher valida el hash y contrato del manifest,
y resuelve su perfil contra un registro administrado, nunca contra una imagen o
comando proporcionados por el mensaje. Ejemplo de registro JSON:

```json
{
  "python-polars-v1": {
    "image": "registry.example/worker-polars:approved",
    "framework": "polars",
    "command": ["python"]
  }
}
```

En producción fija imágenes por digest. Para Spark usa framework `pyspark` y
command `["spark-submit"]`. El comando del perfil es una validación de contrato;
el launcher selecciona su ejecutable desde el framework, no desde el manifest.

Guardar ese registro como `/tmp/profiles.json` permite preparar un Job sin enviarlo:

```bash
python -m engine.dispatch prepare \
  --request /tmp/orders-request.json \
  --artifact-root /tmp \
  --profiles /tmp/profiles.json \
  --output /tmp/orders-job.json
```

El Job generado presupone un PVC `pipeline-artifacts` montado en `artifact_root`.
Antes de desplegar debes configurar PVC, namespace, permisos, recursos y montajes
de datos/resultados. Las rutas del request deben existir **dentro del pod**. El
ejemplo de parámetros anterior usa rutas del workspace y hay que adaptarlas a esos
montajes. `Dispatcher(..., worker_secret_name="worker-kafka")` añade un Secret por
`envFrom` para la configuración externa. La imagen necesita el launcher y sus
dependencias mínimas, además del framework. No necesita los processors ni emitters.
El Job no crea por sí mismo un cluster Spark: el perfil/imagen debe configurar
`spark-submit` para enviar al cluster; este código no instala Spark Operator.

Para publicación real, instala las dependencias opcionales e inyecta la configuración:

```bash
python -m pip install -r requirements-workers.txt
export KAFKA_BOOTSTRAP_SERVERS=broker.example:9093
# KAFKA_CONFIG_JSON: objeto de configuración librdkafka con TLS/SASL,
# inyectado desde un secreto; no guardar contraseñas en el DAG ni en Git.
python -m engine.dispatch publish \
  --request /tmp/orders-request.json --topic pipeline.executions
```

`KafkaPublisher` usa claves `execution_id`, productor idempotente y `acks=all`;
espera confirmación y propaga errores o timeouts. Para consumir:

```python
from engine.dispatch.kafka import KafkaExecutionConsumer, kafka_config_from_env

# dispatcher debe tener submit=adaptador_kubernetes configurado explícitamente.
consumer = KafkaExecutionConsumer(
    kafka_config_from_env(), "pipeline.executions", "pipeline-dispatchers",
    dispatcher.dispatch,
)
try:
    while True:
        consumer.poll_once()
finally:
    consumer.close()
```

La confirmación de offset es manual y posterior a la aceptación por `submit`.
Si falla un mensaje, el consumidor bloquea nuevas lecturas: hay que cerrarlo y
recrearlo para reintentar sin confirmar accidentalmente offsets posteriores.
No se omiten mensajes inválidos; un consumidor de producción debe definir su
política de reintentos/DLQ. El adaptador Kubernetes debe aceptar idempotentemente
el nombre de Job determinista y verificar que una ejecución existente corresponde
al mismo request. No se promete exactly-once: los efectos sobre los datasets y
la deduplicación de ejecuciones necesitan política persistente externa.

El launcher `python -m engine.dispatch.worker` recibe `EXECUTION_REQUEST`,
`RUNTIME_PROFILE`, `ARTIFACT_ROOT` y opcionalmente `PIPELINE_BASE_DIR`. Verifica
manifest, perfil y todos los archivos antes de lanzar un subproceso sin shell.
Publica `started` y `succeeded`/`failed` con exit code, sin incluir parámetros.
Si se configura `KAFKA_EVENTS_TOPIC`, usa Kafka con las mismas variables TLS/SASL;
si no, escribe eventos JSON a stdout para uso aislado. Errores de publicación
no se silencian.

Los SHA-256 no autentican al productor: restringe escritura al almacenamiento,
ACL de topics e identidades de ejecución. No pongas secretos en los parámetros
del mensaje, que también aparecen en la especificación del Job; inyecta secretos
al worker mediante mecanismos del entorno. Ejecuta artefactos aprobados con
ServiceAccounts mínimos, límites de recursos y aislamiento de red.

Las pruebas en `tests/test_script_builder.py` comparan DataFrames y archivos
generados contra `PipelineRunner`, comprueban hashes y determinismo y ejecutan
el script desde un directorio donde el paquete `engine` no está disponible:

```bash
python -m pytest -q tests/test_script_builder.py tests/test_pipeline_runner.py
python -m pytest -q tests/test_native_codegen.py tests/test_dispatch.py
```

Las pruebas nativas usan Polars/PyArrow reales, Spark `local[1]`, `spark-submit`,
un notebook ejecutado con Jupyter y Kafka simulado sin broker. Instala
`requirements-workers.txt` para ejecutarlas todas; las pruebas que requieren
runtimes opcionales se omiten si faltan. Java debe estar disponible para Spark.

## DAG JSON normalizado

La función de debug `export_clean_pipeline` de `main.py` no consulta la API:
consume las respuestas guardadas como snapshots en
`dag/`: `nodes.json`, `edges.json` y los archivos de operación cuyo nombre es su ID. Llama a
`merge_pipeline_clean(edges_json, nodes_json, operations_json)` y escribe el resultado
normalizado en `dag/pipeline_clean.json`, sobrescribiendo el archivo en cada generación.

En la función histórica `main()` la construcción del pipeline limpio está activada
por defecto. Para omitirla desde Python, usa `main(build_pipeline_clean=False)`; el pipeline
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

La función histórica `main()` regenera `dag/pipeline_clean.json` desde las respuestas guardadas en
`nodes.json`, `edges.json` y los snapshots de operaciones, pero ejecuta
`dag/pipeline_test.json`. Este último es un pipeline de prueba independiente y
no se sobrescribe al generar el pipeline limpio. Para elegir el archivo ejecutado:

```python
from main import main

main(pipeline_file="pipeline_test.json")
```

Ese flujo de debug ejecuta `pipeline_test.json`; `pipeline_clean.json` se conserva
como salida generada para inspección y no se usa para la ejecución de pruebas.

Los snapshots actuales de `dag/nodes.json` contienen cuatro nodos, parámetros
vacíos y una operación `avg` sin contrato de compilación. No constituyen un
pipeline ejecutable completo: el builder no inventa parámetros ni sustituye esa
operación. Usa `dag/pipeline_codegen.json` para el ejemplo multi-framework, o
`dag/pipeline.json` para el ejemplo estructural pandas. Algunas pruebas históricas
de API esperan snapshots anteriores con siete nodos; no se alteraron esos datos
para ocultar esa discrepancia.

## Ejecutar el pipeline local

`dag/pipeline.json` define un DAG estructural para compilación pandas o debug: lee los CSV,
los une por `Customer ID`, ordena por `Sales_south`, elimina `Discount`, renombra
`Profit_south`, convierte `Postal Code_south` a texto y escribe
`output/processed_orders.csv`. Cada nodo declara `operation.name`, sus puertos y
`parameters`; las aristas conectan puertos por ID. Las rutas son relativas a la raíz
del proyecto.

El pipeline previo de lectura, join, operaciones de texto y transformaciones
numéricas se conserva en `dag/pipeline_join_text_numeric.json`.

`PipelineRunner` ordena los nodos por sus aristas y busca cada operación en
`engine/core/operation_registry.py`, que la dirige directamente al método estático del
procesador concreto. El registro de operaciones es la única fachada del runner;
las implementaciones funcionales están agrupadas en `engine/processors/`:

| Categoría | Operaciones | Parámetros |
|---|---|---|
| io | `read_csv`, `write_csv` | `filepath` |
| structural | `inner_join`, `outer_join`, `sort`, `add_column`, `drop-column`, `rename-column`, `change-data-type` | `left_on`, `right_on`, `suffixes`; `column`, `direction`; `column_name`, `value`; `column`; `column`, `new_name`; `column`, `new_type` |
| row | `limit`, `filter` | `limit`; `column`, `operator`, `value` |
| text | `uppercase`, `lowercase` | `column`, `create_new_column`, `new_column_name` |
| numeric | `absolute`, `ceiling`, `clean_float`, `floor`, `max`, `min`, `power`, `round` | `column`, `create_new_column`, `new_column_name`; `column_a`, `column_b`, `new_column_name` para `max`/`min`; `value` para `power`; `decimals` para `round` |

`create_new_column: false` (por defecto) actualiza la columna original. Con `true`,
el resultado va a `new_column_name` o, si no se indica, a una nueva columna
`<columna>_processed` (con sufijo incremental si ese nombre ya existe).

Las operaciones numéricas usan la misma selección de columna destino. `round` acepta
`decimals`; en el pipeline de ejemplo, `absolute` y `ceiling` crean columnas nuevas,
mientras que `floor` y `round` actualizan las columnas originales.

Los joins infieren la clave solo si hay una única columna común; con estos CSV hay que
indicar `left_on` y `right_on`.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python main.py dag/pipeline.json --output-dir /tmp/structural-pandas \
  --pipeline-id structural --pipeline-version 1
```

## Implementaciones de referencia

Las clases de `engine/processors/` contienen implementaciones confiables que usa
el compilador para emitir helpers al script destino. `PipelineRunner` y
`operation_registry` se conservan exclusivamente para pruebas y debug local; no
forman parte del worker ni del contrato de ejecución. No existe un agregador
`PandasDataProcessor`: el artefacto generado es la interfaz que recibe el worker.

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
