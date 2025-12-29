from flask import Flask, request, jsonify, render_template, Response
from flasgger import Swagger
from callejero_mostoles_mod import generar_ruta_geojson_coords, get_network_wgs84
import json
import os
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

app = Flask(__name__)

# Puerto configurable
PORT = int(os.environ.get("PORT", 8080))

# ---------------------------------------------
# 1. Carga del Modelo de Machine Learning
# ---------------------------------------------
MODEL_PATH = "modelo_trafico.pkl"
ENCODER_PATH = "encoder_zona.pkl"
model = None
le_zona = None

try:
    if os.path.exists(MODEL_PATH) and os.path.exists(ENCODER_PATH):
        model = joblib.load(MODEL_PATH)
        le_zona = joblib.load(ENCODER_PATH)
    else:
        # Mensaje interno silencioso para no ensuciar el arranque
        pass 
except Exception as e:
    print(f"❌ Error cargando modelos: {e}")

ZONAS_LISTA = [
    "Centro", "Norte – Universidad", "Sur – Este", 
    "Oeste", "Parque Coimbra – Guadarrama", "Sur"
]

# ---------------------------------------------
# 2. Configuración Swagger 
# ---------------------------------------------
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/docs"
}

swagger_template = {
    "info": {
        "title": "API Rutas Móstoles",
        "description": "API para calcular rutas óptimas en la red viaria de Móstoles con IA.",
        "version": "2.0.0",
        "contact": {
            "name": "Simulación Rutas Móstoles"
        }
    },
    "basePath": "/",
    "schemes": ["http", "https"]
}

swagger = Swagger(app, config=swagger_config, template=swagger_template)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

# ---------------------------------------------
# 3. Lógica Auxiliar IA
# ---------------------------------------------
def es_vacaciones(fecha_dt):
    vacaciones_periodos = [
        ("2024-08-01", "2024-08-31"), ("2024-12-20", "2025-01-07"),
        ("2024-04-01", "2024-04-15"), ("2025-08-01", "2025-08-31"),
        ("2025-12-20", "2026-01-07")
    ]
    s_fecha = fecha_dt.strftime("%Y-%m-%d")
    for ini, fin in vacaciones_periodos:
        if ini <= s_fecha <= fin: return 1
    return 0

def predecir_trafico_por_fecha(fecha_str):
    if not model or not le_zona: return {}
    try:
        dt = pd.to_datetime(fecha_str)
        dia = dt.weekday()
        finde = 1 if dia >= 5 else 0
        vac = es_vacaciones(dt)
        preds = {}
        for zona in ZONAS_LISTA:
            try:
                z_code = le_zona.transform([zona])[0]
                nivel = model.predict(pd.DataFrame([[dia, finde, vac, z_code]], 
                                      columns=["dia_semana", "es_fin_de_semana", "vacaciones", "zona_encoded"]))[0]
                preds[zona] = int(nivel)
            except: continue
        return preds
    except: return {}

# ---------------------------------------------
# 4. Endpoints
# ---------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/callejero_full")
def get_full_network():
    try:
        return Response(get_network_wgs84(), mimetype='application/json')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/prediccion_trafico", methods=['GET'])
def api_prediccion():
    """
    Devuelve el nivel de tráfico por zona para una fecha.
    ---
    tags:
      - Inteligencia Artificial
    parameters:
      - name: date
        in: query
        type: string
        required: true
        description: Fecha en formato YYYY-MM-DD
    responses:
      200:
        description: Diccionario con niveles de tráfico (0=Bajo, 1=Medio, 2=Alto)
        schema:
          type: object
          additionalProperties:
            type: integer
    """
    fecha = request.args.get("date")
    if not fecha: return jsonify({"error": "Falta parámetro date"}), 400
    return jsonify(predecir_trafico_por_fecha(fecha))

@app.route("/ruta", methods=["GET"])
def obtener_ruta():
    """
    Calcular ruta óptima entre dos puntos con predicción de tráfico.
    ---
    tags:
      - Rutas
    parameters:
      - name: orig_lat
        in: query
        type: number
        required: true
        description: Latitud del punto de origen
        example: 40.324
      - name: orig_lon
        in: query
        type: number
        required: true
        description: Longitud del punto de origen
        example: -3.867
      - name: dest_lat
        in: query
        type: number
        required: true
        description: Latitud del punto de destino
        example: 40.322
      - name: dest_lon
        in: query
        type: number
        required: true
        description: Longitud del punto de destino
        example: -3.858
      - name: date
        in: query
        type: string
        required: false
        description: Fecha para predicción de tráfico (YYYY-MM-DD). Opcional.
        example: "2025-12-29"
    responses:
      200:
        description: GeoJSON con la ruta calculada
        schema:
          type: object
          properties:
            type:
              type: string
              example: FeatureCollection
            features:
              type: array
              items:
                type: object
                properties:
                  type:
                    type: string
                    example: Feature
                  geometry:
                    type: object
                    properties:
                      type:
                        type: string
                        example: LineString
                      coordinates:
                        type: array
                        items:
                          type: array
                          items:
                            type: number
                  properties:
                    type: object
                    properties:
                      length_m:
                        type: number
                        description: Distancia total en metros
                        example: 1250.5
                      time_s:
                        type: number
                        description: Tiempo estimado en segundos
                        example: 180.3
      400:
        description: Error en la solicitud
      404:
        description: No existe ruta entre los puntos
      500:
        description: Error interno
    """
    try:
        orig_lat = float(request.args.get("orig_lat"))
        orig_lon = float(request.args.get("orig_lon"))
        dest_lat = float(request.args.get("dest_lat"))
        dest_lon = float(request.args.get("dest_lon"))
        fecha = request.args.get("date")

        trafico_preds = {}
        if fecha:
            trafico_preds = predecir_trafico_por_fecha(fecha)

        geojson = generar_ruta_geojson_coords(
            orig_lat, orig_lon,
            dest_lat, dest_lon,
            traffic_predictions=trafico_preds
        )

        if geojson is None:
            return jsonify({"error": "No existe ruta entre los puntos"}), 404

        return Response(json.dumps(geojson), status=200, mimetype="application/geo+json")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------------------------------------
# 5. Configuración de ARRANQUE
# ---------------------------------------------
WORKERS = int(os.environ.get("WORKERS", 4))

try:
    from gunicorn.app.base import BaseApplication
    GUNICORN_AVAILABLE = True
except ImportError:
    GUNICORN_AVAILABLE = False

def run_development():
    print(f"🚀 Servidor de DESARROLLO iniciando en http://localhost:{PORT}")
    print(f"📖 Swagger UI disponible en http://localhost:{PORT}/docs")
    print("⚠️  Usa Gunicorn para producción")
    app.run(host="0.0.0.0", port=PORT, debug=True)

def run_production():
    class GunicornApp(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()
        def load_config(self):
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:
                    self.cfg.set(key.lower(), value)
        def load(self): return self.application

    options = {
        "bind": f"0.0.0.0:{PORT}",
        "workers": WORKERS,
        "accesslog": "-",
        "errorlog": "-",
        "capture_output": True,
    }
    print(f"🚀 Servidor de PRODUCCIÓN (Gunicorn) iniciando en http://localhost:{PORT}")
    print(f"📖 Swagger UI disponible en http://localhost:{PORT}/docs")
    print(f"👷 Workers: {WORKERS}")
    GunicornApp(app, options).run()

if __name__ == "__main__":
    import sys
    use_dev = "--dev" in sys.argv or os.environ.get("FLASK_ENV") == "development"
    if use_dev: run_development()
    elif GUNICORN_AVAILABLE: run_production()
    else:
        print("⚠️  Gunicorn no está instalado. Usando servidor de desarrollo Flask.")
        print("   Para instalar: pip install gunicorn")
        run_development()