# Flujo interno del repositorio

Este documento describe los módulos que existen en este repositorio y el flujo
actual para compilar un DAG y generar un script ejecutable.

## Componentes del repositorio

```mermaid
flowchart TB
    subgraph INPUTS["Entradas disponibles"]
        JSON["Pipeline JSON normalizado<br/>nodes + edges + operation + parameters"]
        API_SNAPSHOTS["Snapshots JSON<br/>nodes.json + edges.json + operation IDs"]
        USER_CODE["Uso como librería<br/>build_artifact(pipeline, ...)"]
        EXAMPLE["dag/pipeline_codegen.json<br/>ejemplo compilable"]
    end

    subgraph CLI["Entrypoints"]
        MAIN["main.py<br/>CLI de compilación"]
        CODEGEN_CLI["python -m engine.codegen"]
        PY_API["API Python"]
        DEBUG["Funciones históricas de debug<br/>export_clean_pipeline / run_pipeline"]
    end

    subgraph CLEANING["Normalización de respuestas"]
        MERGE["engine.core.pipeline_clean<br/>merge_pipeline_clean(...)"]
        CLEAN_JSON["pipeline_clean.json"]
        DEBUG_RUNNER["PipelineRunner<br/>solo referencia/debug"]
    end

    subgraph COMPILER["Compilador · engine.codegen + engine.ir"]
        BUILDER["engine.codegen.builder<br/>build_artifact"]
        PLAN["engine.ir.plan<br/>build_plan → ExecutionPlan"]
        GRAPH["engine.core.pipeline_graph<br/>collect_nodes + topological_order"]
        CATALOG["engine.ir.catalog<br/>operaciones, aliases y targets"]
        VALIDATOR["engine.ir.validate / targets<br/>schemas, parámetros y compatibilidad"]
        EXPRESSIONS["engine.ir.expressions<br/>parsear fx seguro a AST"]
        REGISTRY["engine.codegen.registry<br/>elegir emitter"]
        PANDAS["PandasEmitter"]
        NATIVE["PolarsEmitter<br/>PyArrowEmitter<br/>PySparkEmitter"]
        PROCESSORS["engine.processors/*<br/>helpers confiables locales<br/>AST → funciones del script"]
        NATIVE_OPS["engine.codegen.native_ops<br/>helpers nativos para runtimes"]
        NOTEBOOK["engine.codegen.notebook<br/>opcional"]
        MANIFEST["engine.artifacts.manifest<br/>contrato + hashes"]
    end

    subgraph OUTPUT["Artefactos locales generados"]
        SCRIPT["main.py<br/>script autónomo por framework"]
        MANIFEST_FILE["manifest.json"]
        IPYNB["pipeline.ipynb<br/>opcional"]
    end

    JSON --> CODEGEN_CLI
    EXAMPLE --> CODEGEN_CLI
    USER_CODE --> PY_API
    MAIN --> CODEGEN_CLI
    CODEGEN_CLI --> BUILDER
    PY_API --> BUILDER

    API_SNAPSHOTS --> DEBUG
    DEBUG --> MERGE --> CLEAN_JSON
    CLEAN_JSON -.->|"entrada manual/archivo al CLI"| CODEGEN_CLI
    DEBUG --> DEBUG_RUNNER
    CLEAN_JSON -.->|"debug independiente"| DEBUG_RUNNER

    BUILDER -->|"1. crear plan"| PLAN
    PLAN --> GRAPH
    PLAN --> CATALOG
    PLAN --> VALIDATOR
    PLAN --> EXPRESSIONS
    PLAN -->|"ExecutionPlan"| REGISTRY
    REGISTRY -->|"framework=pandas"| PANDAS
    REGISTRY -->|"framework nativo"| NATIVE
    PANDAS -->|"inspecciona métodos necesarios"| PROCESSORS
    NATIVE --> NATIVE_OPS
    NATIVE -->|"reutiliza wiring"| PROCESSORS
    PANDAS -->|"script source"| BUILDER
    NATIVE -->|"script source"| BUILDER
    BUILDER -->|"calcula manifest y sha256"| MANIFEST
    BUILDER -.->|"si notebook=true"| NOTEBOOK
    NOTEBOOK -->|"notebook source"| MANIFEST
    BUILDER --> SCRIPT
    MANIFEST --> MANIFEST_FILE
    NOTEBOOK --> IPYNB

    classDef entry fill:#eaf3ff,stroke:#1565c0,color:#0d47a1;
    classDef core fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef output fill:#fff3e0,stroke:#ef6c00,color:#e65100;
    classDef legacy fill:#f3f4f6,stroke:#616161,color:#212121;
    class JSON,API_SNAPSHOTS,USER_CODE,EXAMPLE,MAIN,CODEGEN_CLI,PY_API entry;
    class BUILDER,PLAN,GRAPH,CATALOG,VALIDATOR,EXPRESSIONS,REGISTRY,PANDAS,NATIVE,PROCESSORS,NATIVE_OPS,NOTEBOOK,MANIFEST,MERGE core;
    class SCRIPT,MANIFEST_FILE,IPYNB output;
    class DEBUG,CLEAN_JSON,DEBUG_RUNNER legacy;
```

## Secuencia de compilación y generación

```mermaid
sequenceDiagram
    autonumber
    actor Caller as Usuario / DataIntegration
    participant CLI as main.py o engine.codegen CLI
    participant Builder as build_artifact
    participant Plan as build_plan / ExecutionPlan
    participant Graph as pipeline_graph
    participant Contracts as catalog + validate + targets
    participant Expr as expressions
    participant Registry as emitter registry
    participant Emitter as PandasEmitter o emitter nativo
    participant Helpers as processors / native_ops
    participant Notebook as emit_notebook
    participant Manifest as manifest
    participant Disk as directorio de salida

    Caller->>CLI: ruta JSON de pipeline normalizado + target
    CLI->>Builder: build_artifact(pipeline, output_dir, metadata, framework)
    Builder->>Plan: build_plan(pipeline, engine, framework)
    Plan->>Graph: collect_nodes + topological_order(edges)
    Graph-->>Plan: nodos y orden determinista
    Plan->>Contracts: validar puertos, aliases, aridad y parámetros
    Contracts-->>Plan: contratos de operación / compatibilidad
    opt Nodo fx
        Plan->>Expr: parse_expression(expression)
        Expr-->>Plan: AST lógico permitido
    end
    Plan-->>Builder: ExecutionPlan validado
    Builder->>Registry: seleccionar emitter por framework
    Registry-->>Builder: PandasEmitter / Polars / PyArrow / PySpark
    Builder->>Emitter: emit(plan)
    Emitter->>Helpers: copiar solo helpers requeridos
    Helpers-->>Emitter: funciones nativas serializadas como código
    Emitter-->>Builder: texto Python standalone con run() y CLI
    opt notebook=true
        Builder->>Notebook: emit_notebook(script, framework)
        Notebook-->>Builder: pipeline.ipynb determinista
    end
    Builder->>Manifest: construir schema, target, entradas/salidas y hashes
    Manifest-->>Builder: manifest.json
    Builder->>Disk: crear output_dir (debe no existir)
    Builder->>Disk: escribir main.py
    opt notebook=true
        Builder->>Disk: escribir pipeline.ipynb
    end
    Builder->>Disk: escribir manifest.json al final
    Builder-->>Caller: manifest y ruta de artefactos
```

## Qué ocurre en cada etapa

1. **Entrada:** `python main.py <pipeline.json> ...` delega en el CLI de
   `engine.codegen`. También se puede llamar directamente a
   `engine.codegen.builder.build_artifact`. En ambos casos el pipeline se
   entrega como JSON con nodos, aristas, operaciones y parámetros. Si no se
   especifica `--output-dir`, la CLI usa `output/<nombre-del-JSON>/`.
2. **Plan lógico:** `build_plan` no carga datasets ni importa pandas/Polars/Spark.
   `pipeline_graph` valida referencias de nodos y calcula el orden topológico.
   `catalog`, `validate` y `targets` verifican nombres/aliases de operaciones,
   número de entradas, puertos, parámetros y soporte en el framework destino.
3. **Expresiones:** si el pipeline contiene `fx`, la expresión se analiza con
   una gramática limitada y se almacena como AST lógico. El emitter la renderiza
   como expresión del framework elegido; no se ejecuta código Python arbitrario
   ni `eval`.
4. **Selección del backend:** `engine.codegen.registry` selecciona un emitter
   para `pandas`, `polars`, `pyarrow` o `pyspark`. La matriz de compatibilidad
   rechaza durante la planificación las operaciones que el destino no soporta.
5. **Emisión del código:** el emitter crea llamadas explícitas por nodo, wiring
   de inputs/outputs, validación de parámetros runtime, `run(...)` y una CLI.
   Para pandas extrae del AST los métodos/helper confiables necesarios desde
   `engine.processors`; para los runtimes nativos usa implementaciones de
   `engine.codegen.native_ops`. El artefacto no importa este repositorio.
6. **Manifest y escritura:** se calcula SHA-256 del plan y de los archivos.
   El directorio de salida se crea en modo exclusivo: si ya existe, la
   compilación falla en lugar de sobrescribir artefactos. El manifest se escribe
   al final como marca de que la generación concluyó.
7. **Notebook opcional:** `--notebook` añade un notebook determinista con
   definiciones, celdas para parámetros/datasources y ejecución. El entrypoint
   principal del worker sigue siendo `main.py`.

## Límite actual con `pipeline_clean`

`engine.core.pipeline_clean.merge_pipeline_clean` normaliza snapshots de
respuestas `nodes`, `edges` y `operations`. En el estado actual es invocado por
las funciones históricas de debug de `main.py`; **no se llama automáticamente
dentro de `build_artifact` ni del CLI de compilación**. Por tanto, el caller
debe proporcionar a `build_artifact` un pipeline que ya esté en el formato
normalizado esperado. La conexión directa API → cleaner → builder queda como
integración del plano DataIntegration pendiente.

El `PipelineRunner`, `operation_registry` y los procesadores son referencia de
ejecución local y soporte del código confiable que reutiliza el emitter; no son
dependencias del script generado ni del worker que lo ejecuta.

## Comandos

```bash
# Compilar desde un pipeline JSON normalizado
python main.py dag/pipeline_codegen.json \
  --pipeline-id orders --pipeline-version 1

# Elegir explícitamente otra carpeta de artefactos
python main.py dag/pipeline_codegen.json \
  --output-dir /tmp/orders-pandas \
  --pipeline-id orders --pipeline-version 1

# Seleccionar otro backend y generar notebook adicional
python -m engine.codegen dag/pipeline_codegen.json \
  --output-dir /tmp/orders-polars \
  --pipeline-id orders --pipeline-version 1 \
  --framework polars --notebook
```

El resultado es un artefacto con `main.py`, `manifest.json` y, de solicitarse,
`pipeline.ipynb`. Este diagrama termina en la generación del artefacto; la
publicación, Kafka, Job Dispatcher y ejecución de workers están descritos en el
[diagrama de arquitectura de integración](ARCHITECTURE_DAG_SCRIPT_BUILDER.md).
Sin `--output-dir`, el ejemplo genera los archivos en
`output/pipeline_codegen/`; como el artefacto es inmutable, esa carpeta debe no
existir antes de compilar.
