# SCRIPT BUILDER
>cd script-builder

>pip install -r requirements.txt

### Generar con los valores por defecto (pandas)
>python src/main.py

### Elegir otro DAG
>python src/main.py ../dag/pipeline_clean.json

### Generar para Polars en una carpeta independiente
>python src/main.py ../dag/pipeline_test.json --framework polars --output-dir ../output/pipeline_polars

### Personalizar salida, identificador y version; incluir notebook
>python src/main.py ../dag/pipeline_test.json --output-dir ../output/my_pipeline --pipeline-id my_pipeline --pipeline-version 2 --notebook
Salida por defecto: ../output/pipeline_test/main.py y manifest.json

# WORKER
### Cambiar desde script-builder/:
>cd ../workers

### Instalar las dependencias del backend que se utilizara
>pip install -r requirements-pandas.txt
>pip install -r requirements-polars.txt

### Ejecutar el artefacto por defecto; el backend se detecta desde el manifiesto
>python src/main.py

### Ejecutar un artefacto especifico
>python src/main.py ../output/my_pipeline

### Ejecutar el artefacto Polars generado arriba
>python src/main.py ../output/pipeline_polars --worker polars

# TESTS (desde la raiz del repositorio) #
### Cambiar desde workers/:
cd ..
python -m pytest -q script-builder/tests
python -m pytest -q workers/tests
python -m pytest -q
