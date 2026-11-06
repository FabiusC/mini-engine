# SCRIPT BUILDER
>cd script-builder

>pip install -r requirements.txt

### Generar con los valores por defecto (lee ../dag/, pandas)
>python src/main.py
Salida: ../output/<pipeline_id>/<pipeline_id>.py y manifest.json

### Generar para Polars e incluir notebook
>python src/main.py --framework polars --notebook

### Elegir otra carpeta de respuestas de la API o un pipeline concreto
>python src/main.py ../dag --pipeline-id e6b4f425-1133-4cae-97ec-442f4cf2a24b

### Compilar un DAG ya normalizado (formato interno)
>python src/main.py tests/fixtures/pipeline_test.json --output-dir ../output/my_pipeline --pipeline-id my_pipeline --pipeline-version 2

# WORKER
### Cambiar desde script-builder/:
>cd ../workers

### Instalar las dependencias del backend que se utilizara
>pip install -r requirements-pandas.txt
>pip install -r requirements-polars.txt

### Ruta del archivo de entrada (hardcodeada)
Editar INPUT_FILE_PATH (o INPUT_FILE_PATHS por file id) en src/workers/settings.py

### Ejecutar el ultimo artefacto generado; el backend se detecta desde el manifiesto
>python src/main.py

### Ejecutar un artefacto por pipeline id o por carpeta
>python src/main.py e6b4f425-1133-4cae-97ec-442f4cf2a24b
>python src/main.py ../output/my_pipeline

# TESTS (desde la raiz del repositorio) #
### Cambiar desde workers/:
cd ..
python -m pytest -q script-builder/tests
python -m pytest -q workers/tests
python -m pytest -q
