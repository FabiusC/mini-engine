# Flujo interno del repositorio

El repositorio tiene dos partes independientes:

- `script-builder/src`: lee un DAG y genera el script.
- `workers/src`: emula los workers que ejecutan ese script.

Este documento describe sus módulos y el flujo completo desde las respuestas
de la API guardadas en `dag/` hasta la ejecución del script. No se consulta
ningún endpoint: solo se leen esos JSON.

## Componentes del repositorio

```mermaid
flowchart TB
    subgraph ROOT["Raíz del repositorio (insumos compartidos)"]
        SNAPSHOTS["dag/*.json<br/>respuestas guardadas de la API<br/>(pipeline, nodes, edges, operation)"]
        DATA[("data/*<br/>archivo de entrada")]
        OUT[("output/")]
    end

    subgraph SB["script-builder/src"]
        SB_MAIN["main.py<br/>entrada"]
        SB_CLI["script_builder/__main__.py<br/>CLI: lee dag/ y opciones"]
        subgraph DAG_PKG["script_builder/dag"]
            GRAPH["pipeline_graph<br/>collect_nodes + topological_order"]
            CLEAN["pipeline_clean<br/>load_api_pipeline: clasifica por code + normaliza"]
        end
        subgraph IR_PKG["script_builder/ir"]
            PLAN["plan.build_plan → ExecutionPlan"]
            CATALOG["catalog<br/>operaciones, aliases, targets"]
            VALIDATE["validate / targets<br/>esquemas y compatibilidad"]
            EXPR["expressions<br/>fx → AST seguro"]
        end
        subgraph CODEGEN_PKG["script_builder/codegen"]
            BUILDER["builder.build_artifact"]
            REGISTRY["registry.EMITTERS"]
            PANDAS_EM["PandasEmitter"]
            POLARS_EM["PolarsEmitter"]
            RUNTIME["runtime<br/>helpers copiados al script"]
            NOTEBOOK["notebook (opcional)"]
        end
        subgraph OPS["script_builder/operations"]
            PANDAS_OPS["pandas/*<br/>io, structural, row, text,<br/>numeric, date, logical, conversion"]
            POLARS_OPS["polars/*<br/>mismas categorías"]
        end
        MANIFEST["artifacts/manifest<br/>contrato + SHA-256"]
    end

    subgraph ARTIFACT["output/&lt;pipeline_id&gt;/"]
        SCRIPT["&lt;pipeline_id&gt;.py<br/>script autónomo"]
        MANIFEST_FILE["manifest.json"]
    end

    subgraph WK["workers/src"]
        WK_MAIN["main.py<br/>entrada"]
        WK_CLI["workers/__main__.py<br/>elige worker por manifest"]
        LOAD["artifact.load_artifact<br/>valida manifest y hashes"]
        SETTINGS["settings<br/>INPUT_FILE_PATH hardcodeado"]
        BASE["base.Worker.run<br/>framework + módulos → subprocess"]
        PW["PandasWorker"]
        LW["PolarsWorker"]
    end

    SNAPSHOTS --> SB_MAIN --> SB_CLI --> CLEAN
    CLEAN -->|"pipeline normalizado + input_files"| BUILDER
    BUILDER --> PLAN
    PLAN --> GRAPH
    PLAN --> CATALOG
    PLAN --> VALIDATE
    PLAN -.->|"nodo fx"| EXPR
    BUILDER --> REGISTRY
    REGISTRY --> PANDAS_EM
    REGISTRY --> POLARS_EM
    PANDAS_EM -->|"inspect + AST"| PANDAS_OPS
    POLARS_EM -->|"inspect + AST"| POLARS_OPS
    PANDAS_EM --> RUNTIME
    POLARS_EM --> RUNTIME
    BUILDER -.-> NOTEBOOK
    BUILDER --> MANIFEST
    BUILDER --> SCRIPT
    MANIFEST --> MANIFEST_FILE
    ARTIFACT --> OUT

    WK_MAIN --> WK_CLI --> LOAD
    WK_CLI --> PW
    WK_CLI --> LW
    PW --> BASE
    LW --> BASE
    LOAD -->|"lee"| MANIFEST_FILE
    BASE -->|"ruta de input_files"| SETTINGS
    BASE -->|"python &lt;pipeline_id&gt;.py --params-file … --base-dir …"| SCRIPT
    SCRIPT <-->|"lee / escribe"| DATA

    classDef entry fill:#eaf3ff,stroke:#1565c0,color:#0d47a1;
    classDef core fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef output fill:#fff3e0,stroke:#ef6c00,color:#e65100;
    class SNAPSHOTS,SB_MAIN,SB_CLI,WK_MAIN,WK_CLI entry;
    class CLEAN,SETTINGS,GRAPH,PLAN,CATALOG,VALIDATE,EXPR,BUILDER,REGISTRY,PANDAS_EM,POLARS_EM,RUNTIME,NOTEBOOK,PANDAS_OPS,POLARS_OPS,MANIFEST,LOAD,BASE,PW,LW core;
    class SCRIPT,MANIFEST_FILE output;
```

## Secuencia: del DAG al script ejecutado

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Usuario
    participant CLI as script-builder/src/main.py
    participant Clean as load_api_pipeline
    participant Builder as build_artifact
    participant Plan as build_plan
    participant Graph as pipeline_graph
    participant Contracts as catalog + validate
    participant Emitter as PandasEmitter / PolarsEmitter
    participant Ops as operations/{framework}
    participant Manifest as build_manifest
    participant Disk as output/{pipeline_id}/
    participant Worker as workers/src/main.py
    participant Script as {pipeline_id}.py generado

    Dev->>CLI: python script-builder/src/main.py
    CLI->>Clean: load_api_pipeline(dag/)
    Clean-->>CLI: pipeline normalizado, id y versión actual
    CLI->>Builder: build_artifact(pipeline, output/{pipeline_id}, overwrite=True)
    Builder->>Plan: build_plan(pipeline, engine, framework)
    Plan->>Graph: collect_nodes(pipeline)
    Plan->>Contracts: operación/alias, aridad, puertos y parámetros
    Plan->>Graph: topological_order(nodes, edges)
    Graph-->>Plan: orden productores → consumidores (rechaza ciclos)
    Plan-->>Builder: ExecutionPlan (steps ordenados)
    Builder->>Emitter: emit(plan)
    Emitter->>Ops: inspect.getsource de los métodos usados
    Ops-->>Emitter: funciones independientes (AST sin self)
    Emitter-->>Builder: código Python con run() y CLI
    Builder->>Manifest: target, perfil, esquema de parámetros, sha256
    Builder->>Disk: escribe {pipeline_id}.py y, al final, manifest.json
    Dev->>Worker: python workers/src/main.py [pipeline_id | carpeta]
    Worker->>Disk: load_artifact: manifest, hashes y entrypoint
    Worker->>Worker: framework del manifest = worker y módulos instalados
    Worker->>Worker: input_files → ruta de settings.py → params temporal
    Worker->>Script: python {pipeline_id}.py --params-file … --base-dir raíz del repo (sin shell)
    Script->>Script: valida parámetros, ejecuta los nodos en orden
    Script-->>Worker: resumen JSON + exit code
```

## Qué ocurre en cada etapa

1. **Entrada:** `python script-builder/src/main.py` llama a
   `script_builder.__main__.main`. Por defecto lee la carpeta `dag/` con
   `load_api_pipeline`, que clasifica cada respuesta por su `code`, filtra por la
   versión actual y normaliza nodos, aristas y parámetros. Escribe en
   `output/<pipeline_id>/`. Cada ejecución reemplaza esa carpeta.
2. **Nodos y aristas:** `build_plan` (`ir/plan.py`) obtiene los nodos con
   `collect_nodes` y las aristas de `pipeline["edges"]`.
3. **DAG y validación:** `build_plan` comprueba lo siguiente:
   - Puertos, ordinales y que cada arista pertenezca a sus nodos.
   - Operación y alias (`catalog`), aridad y parámetros (`validate`).
   - Compatibilidad con el framework (`targets`).

   `topological_order` rechaza ciclos y fija el orden de ejecución. El resultado
   es un `ExecutionPlan` independiente del framework.
4. **Script:** `EMITTERS[framework]` elige el emitter. El emitter copia al
   script, como funciones independientes, solo los métodos de
   `operations/<framework>/` que usa el DAG, más los helpers de `runtime`.
   Genera una llamada por nodo dentro de `run()` y una CLI. El script no importa
   `script_builder`.
5. **Manifest:** `build_manifest` registra target, perfil, dependencias, el
   esquema de parámetros, los puertos externos, los nodos terminales y los
   hashes. Se escribe al final como marca de que la generación terminó.
6. **Worker:** `load_artifact` verifica el manifest y los hashes. El worker del
   framework indicado comprueba sus módulos, resuelve las rutas de `input_files`
   con `workers/src/workers/settings.py` y ejecuta
   `python <pipeline_id>.py --params-file … --datasources-file … --base-dir …` en un
   subproceso sin shell. Devuelve el exit code.

## `pipeline_clean`

`script_builder.dag.pipeline_clean` convierte las respuestas de la API guardadas
en `dag/` (`PIPELINE_RETRIEVED`, `PIPELINE_NODES_LIST_RETRIEVED`,
`PIPELINE_EDGES_LIST_RETRIEVED`, `OPERATION_RETRIEVED`) en un pipeline
normalizado. El nombre del archivo no importa; los vacíos y los `code`
desconocidos se ignoran. El parámetro `archivo` (ID de archivo) se convierte en
el parámetro de ejecución `file_<id>`, listado en `input_files` del manifest; el
worker le asigna la ruta de `settings.py`. Un `write_csv` sin ruta escribe en
`output/<pipeline_id>/<node_id>.csv`. `export_clean_pipeline("dag")` guarda el
resultado en `dag/pipeline_clean.json` solo para inspección.

## Comandos

```bash
python script-builder/src/main.py                     # pandas → output/<pipeline_id>/<pipeline_id>.py
python script-builder/src/main.py --framework polars
python workers/src/main.py                            # ejecuta el último artefacto generado
python workers/src/main.py <pipeline_id>              # o una carpeta de artefacto
```
