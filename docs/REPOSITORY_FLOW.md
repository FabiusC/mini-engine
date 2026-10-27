# Flujo interno del repositorio

El repositorio tiene dos partes independientes:

- `script-builder/src`: lee un DAG y genera el script.
- `workers/src`: emula los workers que ejecutan ese script.

Este documento describe sus módulos y el flujo completo desde
`dag/pipeline_test.json` hasta la ejecución del script.

## Componentes del repositorio

```mermaid
flowchart TB
    subgraph ROOT["Raíz del repositorio (insumos compartidos)"]
        TEST_DAG["dag/pipeline_test.json<br/>DAG de entrada por defecto"]
        SNAPSHOTS["dag/nodes.json, edges.json,<br/>&lt;operation-id&gt;.json<br/>respuestas guardadas de la API"]
        DATA[("data/*.csv")]
        OUT[("output/")]
    end

    subgraph SB["script-builder/src"]
        SB_MAIN["main.py<br/>entrada"]
        SB_CLI["script_builder/__main__.py<br/>CLI: lee el JSON y opciones"]
        subgraph DAG_PKG["script_builder/dag"]
            GRAPH["pipeline_graph<br/>collect_nodes + topological_order"]
            CLEAN["pipeline_clean<br/>merge_pipeline_clean + export_clean_pipeline"]
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

    subgraph ARTIFACT["output/&lt;pipeline&gt;/"]
        SCRIPT["main.py<br/>script autónomo"]
        MANIFEST_FILE["manifest.json"]
    end

    subgraph WK["workers/src"]
        WK_MAIN["main.py<br/>entrada"]
        WK_CLI["workers/__main__.py<br/>elige worker por manifest"]
        LOAD["artifact.load_artifact<br/>valida manifest y hashes"]
        BASE["base.Worker.run<br/>framework + módulos → subprocess"]
        PW["PandasWorker"]
        LW["PolarsWorker"]
    end

    TEST_DAG --> SB_MAIN --> SB_CLI --> BUILDER
    SNAPSHOTS -.->|"desconectado: manual"| CLEAN
    CLEAN -.->|"dag/pipeline_clean.json"| ROOT
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
    BASE -->|"python main.py --base-dir …"| SCRIPT
    SCRIPT <-->|"lee / escribe"| DATA

    classDef entry fill:#eaf3ff,stroke:#1565c0,color:#0d47a1;
    classDef core fill:#e8f5e9,stroke:#2e7d32,color:#1b5e20;
    classDef output fill:#fff3e0,stroke:#ef6c00,color:#e65100;
    classDef off fill:#f3f4f6,stroke:#616161,color:#212121;
    class TEST_DAG,SB_MAIN,SB_CLI,WK_MAIN,WK_CLI entry;
    class GRAPH,PLAN,CATALOG,VALIDATE,EXPR,BUILDER,REGISTRY,PANDAS_EM,POLARS_EM,RUNTIME,NOTEBOOK,PANDAS_OPS,POLARS_OPS,MANIFEST,LOAD,BASE,PW,LW core;
    class SCRIPT,MANIFEST_FILE output;
    class SNAPSHOTS,CLEAN off;
```

## Secuencia: del DAG al script ejecutado

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Usuario
    participant CLI as script-builder/src/main.py
    participant Builder as build_artifact
    participant Plan as build_plan
    participant Graph as pipeline_graph
    participant Contracts as catalog + validate
    participant Emitter as PandasEmitter / PolarsEmitter
    participant Ops as operations/{framework}
    participant Manifest as build_manifest
    participant Disk as output/pipeline_test/
    participant Worker as workers/src/main.py
    participant Script as main.py generado

    Dev->>CLI: python script-builder/src/main.py
    CLI->>CLI: lee dag/pipeline_test.json
    CLI->>Builder: build_artifact(pipeline, output/pipeline_test, overwrite=True)
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
    Builder->>Disk: escribe main.py y, al final, manifest.json
    Dev->>Worker: python workers/src/main.py [output/pipeline_test]
    Worker->>Disk: load_artifact: manifest, hashes y entrypoint
    Worker->>Worker: framework del manifest = worker y módulos instalados
    Worker->>Script: python main.py --base-dir raíz del repo (sin shell)
    Script->>Script: valida parámetros, ejecuta los nodos en orden
    Script-->>Worker: resumen JSON + exit code
```

## Qué ocurre en cada etapa

1. **Entrada:** `python script-builder/src/main.py` llama a
   `script_builder.__main__.main`. Por defecto lee `dag/pipeline_test.json` y
   escribe en `output/<nombre-del-JSON>/`. Cada ejecución reemplaza esa carpeta.
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
   framework indicado comprueba sus módulos y ejecuta
   `python main.py --params-file … --datasources-file … --base-dir …` en un
   subproceso sin shell. Devuelve el exit code.

## `pipeline_clean` (desconectado)

`script_builder.dag.pipeline_clean` convierte las respuestas de la API
(`nodes`, `edges`, `operation`) en un pipeline normalizado. Hoy **no forma parte
del flujo principal**. Se ejecuta a mano con `export_clean_pipeline("dag")`,
que escribe `dag/pipeline_clean.json`. Los snapshots actuales compilan y se
ejecutan en Pandas y Polars usando `dag/pipeline_clean_datasources.json` para
los tres puertos externos. Cuando exista la captura
de la API, su salida será la entrada de `build_artifact`.
El DAG termina en el nodo `guardar_csv` (`write_csv`), conectado a la salida de
`avg`, y el worker escribe el resultado agregado en
`output/segment_sales_by_segment.csv` relativo a la raíz del repositorio.

## Comandos

```bash
python script-builder/src/main.py                                   # pandas → output/pipeline_test/
python script-builder/src/main.py --framework polars --output-dir output/pipeline_test_polars
python workers/src/main.py                                          # ejecuta output/pipeline_test
python workers/src/main.py output/pipeline_test_polars              # worker polars (según manifest)
```

El contexto con la UI/API, Kafka, el Job Dispatcher y Kubernetes está en el
[diagrama de arquitectura](ARCHITECTURE_DAG_SCRIPT_BUILDER.md).
