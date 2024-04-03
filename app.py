import os
from flask import Flask
from dotenv import load_dotenv
from flask_cors import CORS
import pandas as pd
import requests
from google.cloud.sql.connector import Connector, IPTypes
from google.cloud import sql


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes and origins

# Configure FLASK_DEBUG from environment variable
app.config['DEBUG'] = os.environ.get('FLASK_DEBUG')

@app.route('/')
def hello():
    return "Hello World!"

if __name__ == '__main__':
    # Cargar datos desde archivo xslx y json en bucket de amazon s3
    RUTA_ORIGEN_1 = 'datos/origen_1.xlsx'
    RUTA_ORIGEN_2 = 'https://prueba-inteia.s3.amazonaws.com/origen_2.json'

    df_origen_1 = pd.read_excel(RUTA_ORIGEN_1)
    df_origen_2 = pd.read_json(RUTA_ORIGEN_2)
    df_unido = pd.concat([df_origen_1, df_origen_2])

    # Formatear correctamente los campos
    df_unido['titulo'] = df_unido['titulo'].astype(str)
    df_unido['autor_nombre'] = df_unido['autor_nombre'].astype(str)
    df_unido['autor_nacionalidad'] = df_unido['autor_nacionalidad'].astype(str)
    df_unido['autor_fecha_nacimiento'] = df_unido['autor_fecha_nacimiento'].astype(str)
    df_unido['autor_genero'] = df_unido['autor_genero'].astype(str)
    df_unido['nombre_editorial'] = df_unido['nombre_editorial'].astype(str)
    df_unido['ubicacion_editorial'] = df_unido['ubicacion_editorial'].astype(str)
    df_unido['isbn'] = df_unido['isbn'].astype(str)
    df_unido['precio'] = df_unido['precio'].astype(float)
    df_unido['cantidad_stock'] = df_unido['cantidad_stock'].astype(int)

    #Separar libros, autores y ediciones y eliminar repetidos
    df_libros = df_unido[['isbn','titulo', 'precio', 'cantidad_stock', 'autor_nombre', 'nombre_editorial']]
    df_libros = df_libros.drop_duplicates(subset='isbn')

    df_autores = df_unido[['autor_nombre', 'autor_nacionalidad', 'autor_fecha_nacimiento', 'autor_genero']]
    df_autores = df_autores.rename(columns={'autor_nombre': 'nombre', 'autor_nacionalidad': 'nacionalidad', 'autor_fecha_nacimiento': 'fecha_nacimiento', 'autor_genero': 'genero'})
    df_autores = df_autores.drop_duplicates(subset='nombre')

    df_editoriales = df_unido[['nombre_editorial', 'ubicacion_editorial']]
    df_editoriales = df_editoriales.rename(columns={'nombre_editorial':'nombre', 'ubicacion_editorial':'ubicacion'})
    df_editoriales = df_editoriales.drop_duplicates(subset='nombre')                                                    

    def obtener_coordenadas_pais(pais):
        # URL base de la API de geocodificación de OpenStreetMap Nominatim
        URL = "https://nominatim.openstreetmap.org/search"

        # Parámetros de la solicitud GET
        params = {
            "q": pais,
            "format": "json",
        }

        # Realizar la solicitud GET a la API
        response = requests.get(URL, params=params)

        # Verificar el código de estado de la respuesta
        if response.status_code == 200:
            data = response.json()
            if data:
                # Extraer las coordenadas (latitud y longitud) del primer resultado
                latitud = data[0]["lat"]
                longitud = data[0]["lon"]
                return latitud, longitud
            else:
                print("No se encontraron coordenadas para el país:", pais)
                return None, None
        else:
            print("Error al obtener coordenadas:", response.status_code)
            return None, None

    # Obtener los valores únicos de la columna 'ubicacion_editorial'
    paises = df_editoriales['ubicacion'].unique()

    # Crear un diccionario para almacenar las coordenadas de cada país
    coordenadas_paises = {}

    # Iterar sobre los países y obtener las coordenadas para cada uno
    for pais in paises:
        latitud, longitud = obtener_coordenadas_pais(pais)
        coordenadas_paises[pais] = (latitud, longitud)

    # Agregar las coordenadas al df_editoriales
    df_editoriales['latitud'] = df_editoriales['ubicacion'].map(lambda x: coordenadas_paises[x][0] if x in coordenadas_paises else None)
    df_editoriales['longitud'] = df_editoriales['ubicacion'].map(lambda x: coordenadas_paises[x][1] if x in coordenadas_paises else None)

    from sqlalchemy import create_engine

    # Define your Cloud SQL connection parameters
    CONNECTION_NAME = 'plasma-minutia-419203:us-central1:db-inteia'
    DB_USER = 'mysql'
    DB_PASSWORD = 'belmont'
    DB_NAME = 'inteia-db'

    # Create connection string
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@/your_db_name?host=/cloudsql/{CONNECTION_NAME}"

    # Create SQLAlchemy engine
    engine = create_engine(connection_string)

    sql_query = f"INSERT INTO autores (nombre, nacionalidad, fecha_nacimiento, genero) VALUES ('autor', 'col', '1999-01-02', 'Fantasia')"

    # Execute query
    with engine.connect() as connection:
        connection.execute(sql_query)
    connection.commit()
    app.run()