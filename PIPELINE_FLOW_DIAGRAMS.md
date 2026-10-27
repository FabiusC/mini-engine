# Flujo de ejecución del pipeline

Este documento describe el funcionamiento actual del motor mediante cuatro diagramas Mermaid.
Los JSON de la carpeta [dag](dag) son snapshots de respuestas de la API: el programa no hace solicitudes HTTP.

## 1. Flujo general: respuestas de la API → preparación → ejecución

Referencias: [main.py](main.py), [pipeline_clean.py](engine/core/pipeline_clean.py), [pipeline_graph.py](engine/core/pipeline_graph.py), [pipeline_runner.py](engine/core/pipeline_runner.py) y [operation_registry.py](engine/core/operation_registry.py).

```mermaid
flowchart TD
    START([Inicio: main]) --> BUILD{"¿build_pipeline_clean?"}

    subgraph PREP[Preparación de snapshots de respuestas de la API]
        READ["Leer dag/nodes.json y dag/edges.json"]
        IDS["Obtener operation_id de los nodos activos"]
        OPS["Leer dag/ID_OPERACION.json por cada ID<br/>y reunir sus registros data"]
        CLEAN["merge_pipeline_clean<br/>Normalizar respuestas y parámetros<br/>Omitir registros eliminados<br/>Validar referencias y nodos"]
        SAVE["Escribir dag/pipeline_clean.json<br/>con listas nodes y edges"]
        READ --> IDS --> OPS --> CLEAN --> SAVE
    end

    BUILD -- Sí --> READ
    BUILD -- No --> SELECT
    SAVE --> SELECT["Seleccionar pipeline_file<br/>Por defecto: pipeline_test.json"]
    SELECT --> LOAD["run_pipeline: leer y deserializar<br/>el JSON seleccionado en dag"]

    subgraph ENGINE[Motor de ejecución]
        INIT["Crear PipelineRunner<br/>pipeline y base_dir = raíz del proyecto"]
        GRAPH["pipeline_graph<br/>collect_nodes + topological_order<br/>Obtener nodos y orden de dependencias"]
        RUN["PipelineRunner.run<br/>Recorrer nodos en orden topológico"]
        RESOLVE["Resolver DataFrames de entrada<br/>y parámetros del nodo"]
        REGISTRY["operation_registry.execute_operation<br/>Buscar operación y validar número de entradas"]
        PROCESSOR["Invocar método del procesador concreto<br/>IO, estructura, filas, texto, números,<br/>conversión, fechas o lógica"]
        STORE["Guardar DataFrame en results por ID de nodo"]
        MORE{"¿Quedan nodos?"}
        INIT --> GRAPH --> RUN --> RESOLVE --> REGISTRY --> PROCESSOR --> STORE --> MORE
        MORE -- Sí --> RUN
    end

    LOAD --> INIT
    EXTERNAL["datasources opcionales<br/>DataFrames por ID de puerto"] -.-> RESOLVE
    PARAMS["parameters opcionales<br/>Sobrescrituras por ID de nodo"] -.-> RESOLVE
    MORE -- No --> RESULTS["Devolver results de todos los nodos"]
    RESULTS --> TERMINALS["run_pipeline consulta output_node_ids<br/>e imprime filas y columnas de los nodos terminales"]
    TERMINALS --> END([Fin])
```

**Importante:** generar el pipeline limpio y elegir el pipeline que se ejecuta son pasos independientes. Por defecto, `main` genera [dag/pipeline_clean.json](dag/pipeline_clean.json), pero ejecuta [dag/pipeline_test.json](dag/pipeline_test.json). Para ejecutar el generado, se debe seleccionar `pipeline_file="pipeline_clean.json"` al invocar `main`.

La limpieza conserva las operaciones y los parámetros declarados; no inventa la configuración de los orígenes de datos. Los errores de preparación, grafo o ejecución se propagan y detienen el flujo.

## 2. PipelineRunner: resolver entradas, parámetros y resultados

Referencia: [pipeline_runner.py](engine/core/pipeline_runner.py).

```mermaid
flowchart TD
    START([Crear PipelineRunner]) --> COLLECT["collect_nodes: obtener nodos"]
    COLLECT --> ORDER["topological_order: calcular orden<br/>Guardar aristas y base_dir"]
    ORDER --> CALL["run: recibir datasources y parameters<br/>Usar diccionarios vacíos si no se indican"]
    CALL --> INDEX["Indexar aristas por target_input_port_id<br/>Inicializar results vacío"]
    INDEX --> NEXT{"¿Quedan nodos en self.order?"}
    NEXT -- No --> RETURN["Devolver results<br/>ID de nodo → DataFrame"]
    NEXT -- Sí --> NODE["Obtener nodo y operation.name<br/>Convertir nombre a minúsculas"]
    NODE --> PORTS["_inputs: ordenar input_ports por ordinal<br/>Inicializar lista de entradas"]
    PORTS --> PORT{"¿Quedan puertos de entrada?"}
    PORT -- Sí --> EDGE{"¿Hay arista entrante<br/>para este puerto?"}
    EDGE -- Sí --> UPSTREAM["Obtener results del source_node_id<br/>Añadir DataFrame a entradas"]
    EDGE -- No --> SOURCE["Buscar DataFrame en datasources<br/>con el ID del puerto"]
    SOURCE --> EXISTS{"¿El valor es distinto de None?"}
    EXISTS -- No --> ERROR["Lanzar ValueError<br/>Falta datasource para el puerto"]
    EXISTS -- Sí --> APPEND["Añadir DataFrame a entradas"]
    UPSTREAM --> PORT
    APPEND --> PORT
    PORT -- No --> PARAMS["_parameters: combinar parámetros almacenados<br/>con sobrescrituras de este nodo<br/>Las sobrescrituras tienen prioridad"]
    PARAMS --> PATHS["Con base_dir, resolver rutas relativas en<br/>filepath, filepath_or_connection y output_path<br/>Excluir filepath_or_connection si source_type es sql"]
    PATHS --> EXEC["execute_operation<br/>nombre, lista de entradas y parámetros"]
    EXEC --> STORE["results del ID del nodo = DataFrame devuelto"]
    STORE --> NEXT
```

- `run` ejecuta todos los nodos, incluidos los aislados; no solamente los terminales.
- Las entradas se ordenan por `ordinal`, lo que determina, por ejemplo, el lado izquierdo y derecho de un join.
- `output_node_ids` devuelve los IDs de nodos sin consumidores posteriores.
- `datasource_port_ids` devuelve los IDs ordenados de los puertos sin arista entrante.
- El runner no lee los snapshots ni limpia sus respuestas: recibe el diccionario del pipeline ya cargado.

## 3. PipelineGraph: recolectar nodos y ordenar dependencias

Referencia: [pipeline_graph.py](engine/core/pipeline_graph.py).

```mermaid
flowchart TD
    START([Recibir pipeline]) --> EDGES{"¿edges es una lista?"}
    EDGES -- No --> BAD_EDGES["Lanzar ValueError<br/>Falta una lista de aristas"]
    EDGES -- Sí --> DECLARED{"¿nodes es distinto de None?"}
    DECLARED -- Sí --> MAP["Indexar nodos declarados por ID"]
    MAP --> UNIQUE{"¿Los IDs son únicos?"}
    UNIQUE -- No --> DUP["Lanzar ValueError<br/>IDs de nodo duplicados"]
    UNIQUE -- Sí --> READY["Nodos recolectados"]

    DECLARED -- No --> EMBED["Recorrer source_node y target_node<br/>embebidos en cada arista<br/>Omitir extremos ausentes"]
    EMBED --> VALID{"¿Cada extremo presente tiene ID<br/>y las definiciones repetidas coinciden?"}
    VALID -- No --> CONFLICT["Lanzar ValueError<br/>ID ausente o definiciones en conflicto"]
    VALID -- Sí --> READY

    READY --> DEPS["topological_order<br/>Crear conjunto de dependencias por nodo"]
    DEPS --> KNOWN{"¿Origen y destino de todas<br/>las aristas existen en nodes?"}
    KNOWN -- No --> UNKNOWN["Lanzar ValueError<br/>Arista con nodo desconocido"]
    KNOWN -- Sí --> FILL["Añadir source_node_id a las<br/>dependencias de target_node_id"]
    FILL --> INIT["Inicializar ordered, visiting y visited"]
    INIT --> EACH{"¿Quedan nodos del grafo?"}
    EACH -- No --> RETURN["Devolver ordered<br/>Productores antes que consumidores"]
    EACH -- Sí --> VISIT["Llamar visit para el siguiente nodo<br/>y esperar su retorno"]
    VISIT --> EACH

    subgraph DFS[Subrutina recursiva visit]
        ENTRY([visit: recibir node_id]) --> ACTIVE{"¿Está en visiting?"}
        ACTIVE -- Sí --> CYCLE["Lanzar ValueError<br/>Ciclo detectado"]
        ACTIVE -- No --> DONE{"¿Está en visited?"}
        DONE -- Sí --> EXIT([Retornar al llamador])
        DONE -- No --> MARK["Añadir nodo a visiting"]
        MARK --> SOURCE{"¿Quedan dependencias del nodo?"}
        SOURCE -- Sí --> RECURSE["Llamar visit para la dependencia<br/>y esperar su retorno"]
        RECURSE --> SOURCE
        SOURCE -- No --> FINISH["Quitar nodo de visiting<br/>Añadir a visited<br/>Añadir al final de ordered"]
        FINISH --> EXIT
    end

    VISIT -. "Detalle de la llamada" .-> ENTRY
    RECURSE -. "Nueva llamada recursiva" .-> ENTRY
```

`visiting` representa la rama recursiva activa y permite detectar ciclos; `visited` evita procesar dos veces un nodo. No se garantiza un único orden entre nodos independientes: la garantía es que cada productor se ejecuta antes que sus consumidores.

## 4. OperationRegistry: seleccionar y ejecutar el procesador

Referencia: [operation_registry.py](engine/core/operation_registry.py).

```mermaid
flowchart TD
    START([execute_operation]) --> LOWER["Convertir operation a minúsculas"]
    LOWER --> LOOKUP["get_operation: buscar en OPERATION_PROCESSORS<br/>Nombre o alias → método concreto"]
    LOOKUP --> FOUND{"¿La operación está registrada?"}
    FOUND -- No --> UNSUPPORTED["Lanzar ValueError<br/>Operación no soportada"]
    FOUND -- Sí --> ARGS["Copiar parameters a arguments<br/>Aplicar overrides con prioridad"]

    ARGS --> ZERO{"¿Es input o read_csv?"}
    ZERO -- Sí --> N0{"¿Recibe exactamente 0 entradas?"}
    N0 -- Sí --> F0["function con argumentos nombrados<br/>Sin DataFrames de entrada"]
    N0 -- No --> ERROR["Lanzar ValueError<br/>Número de entradas incorrecto"]

    ZERO -- No --> UNION{"¿Es union?"}
    UNION -- Sí --> NM{"¿Recibe al menos 1 entrada?"}
    NM -- Sí --> FM["function con la lista completa inputs<br/>y argumentos nombrados"]
    NM -- No --> ERROR

    UNION -- No --> JOIN{"¿Es join, inner_join, outer_join,<br/>left_join o right_join?"}
    JOIN -- Sí --> N2{"¿Recibe exactamente 2 entradas?"}
    N2 -- Sí --> F2["function con inputs primero y segundo<br/>y argumentos nombrados"]
    N2 -- No --> ERROR

    JOIN -- No --> N1{"¿Recibe exactamente 1 entrada?"}
    N1 -- Sí --> F1["function con el primer DataFrame<br/>y argumentos nombrados"]
    N1 -- No --> ERROR

    F0 --> PROCESSOR["Ejecutar método del procesador registrado"]
    FM --> PROCESSOR
    F2 --> PROCESSOR
    F1 --> PROCESSOR
    PROCESSOR --> RESULT["Devolver DataFrame al PipelineRunner"]
```

El registro adapta los argumentos, pero no implementa las transformaciones: estas viven en los procesadores. Algunos nombres son alias del mismo método; otros usan `partial` para fijar argumentos, como el tipo de join o la operación lógica.

**Validación de `union`:** el registro admite una o más entradas; el procesador puede imponer validaciones adicionales. Los errores del procesador se propagan al runner sin capturarse en este flujo.
