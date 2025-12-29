# 🚨 Móstoles Traffic & Emergency Command

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)](https://flask.palletsprojects.com)
[![Scikit-Learn](https://img.shields.io/badge/AI-Scikit__Learn-orange.svg)](https://scikit-learn.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**GeoAI suite for predictive traffic routing and emergency simulations supporting the Digital Twin pilot project.**

This service provides real-time optimal route computation over urban road networks, powered by Machine Learning for traffic prediction. It integrates a high-fidelity graph engine with a CesiumJS 3D frontend for emergency response simulations.

## ✨ Features

- **🧠 AI Traffic Prediction** — Machine Learning model (Random Forest/XGBoost) predicting congestion based on dates and zones.
- **🛣️ High-Fidelity Routing** — Segment-by-segment graph construction that respects exact road curvature and topology.
- **🚒 Emergency Simulation** — Interactive dispatch system: Define Fire (🔥) -> Deploy Unit (🚒) -> Calculate Route.
- **⚡ Dynamic Weights** — Route calculation adjusts in real-time based on predicted traffic levels (Low/Medium/High).
- **🌍 3D Visualization** — CesiumJS frontend with traffic heatmaps and route visualization.
- **📖 Swagger UI** — Built-in interactive API documentation at `/docs`.
- **⚙️ Production Ready** — Hybrid boot system (Development/Gunicorn) with configurable workers.

## 🚀 Quick Start

```bash
# Clone and install
git clone <repository-url>
cd cam-gema-api
pip install -r requirements.txt

# Run server
python server.py

# Open in browser
# Command Center: http://localhost:8080
# API Docs:       http://localhost:8080/docs

## 📡 API Reference

### `GET /prediccion_trafico`

Returns the predicted traffic congestion level for each urban zone on a specific date.

| Parameter | Type | Description |
|-----------|------|-------------|
| `date` | string | Target date in YYYY-MM-DD format |

**Response:** JSON Object 

```json
{"Zone Name": Level (0-2), ...}
```

### `GET /ruta`

Returns the predicted traffic congestion level for each urban zone on a specific date.

| Parameter | Type | Description |
|-----------|------|-------------|
| `orig_lat` | float | Origin latitude |
| `orig_lon` | float | Origin longitude |
| `dest_lat` | float | Destination latitude |
| `dest_lon` | float | Destination longitude |
| `date` | string | Date for traffic prediction YYYY-MM-DD |


**Example Request:**

```bash
curl "http://localhost:8080/ruta?orig_lat=40.322&orig_lon=-3.857&dest_lat=40.324&dest_lon=-3.865&date=2025-12-30"
```

**Response:** GeoJSON FeatureCollection

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "geometry": {
      "type": "LineString",
      "coordinates": [[-3.857, 40.322], [-3.858, 40.323], ...]
    },
    "properties": {
      "length_m": 1250.5,
      "time_s": 210.3,
      "traffic_impact": "Calculado"
    }
  }]
}
```

## ⚙️ Configuration

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `PORT` | Server port | `8080` |
| `WORKERS` | Gunicorn workers | `4` |
| `FLASK_ENV` | Set to `development` for dev mode | - |

```bash
# Production (Gunicorn)
python server.py

# Development (Flask with hot-reload)
python server.py --dev

```

## 📁 Project Structure

```
├── server.py                 # Flask API + ML Inference Logic
├── callejero_mostoles_mod.py # High-Fidelity Graph Engine
├── modelo_trafico.pkl        # Trained ML Model (Output)
├── encoder_zona.pkl          # Label Encoder for Zones (Output)
├── ml/                       # Machine Learning Workflow
│   ├── generar_dataset_trafico.py # Synthetic data generation script
│   ├── train_trafico_model.py     # Training script (outputs .pkl files)
│   └── trafico_sintetico_mostoles.csv # Dataset used for training
├── data/
│   └── callesconzonas.geojson # Road network with zoning data
├── templates/
│   └── index.html            # CesiumJS Command Center
└── requirements.txt
```

## 🔧 How It Works

1. **Data & Training (ML Layer)** — The ml/ folder contains scripts to generate synthetic traffic patterns (generar_dataset_trafico.py) and train the Random Forest model (train_trafico_model.py), producing the .pkl artifacts used by the server.
2. **High-Fidelity Graph** — Unlike standard routers that simplify geometry, the engine iterates through every coordinate segment of LineStrings to preserve curves and prevent "building clipping."
3. **ML Inference** — On server start, modelo_trafico.pkl is loaded. Requests with a date trigger a prediction based on calendar features (day of week, holidays).
4. **Dynamic Pathfinding** — Dijkstra's algorithm uses a dynamic weight function:
-- Base Time = Length / Speed Limit
-- Final Weight = Base Time * Traffic Penalty (1.0x, 1.5x, or 3.0x based on ML output).
5. **Nearest Neighbor** — cKDTree provides O(log n) lookups to snap GPS clicks to the nearest valid graph node.

## 🗺️ Simulation Frontend

The web interface (`/`) acts as a Digital Twin control panel:

- 📅 Date Selector: Feeds the AI model to visualize future traffic scenarios.
- 🚦 Traffic Heatmap: Colors roads (Green/Orange/Red) based on ML predictions.
- 🚨 Emergency Dispatch Mode:
-- Define Incident: Click map to set Fire location (🔥).
-- Deploy Unit: Click anywhere to spawn a Unit (🚒).
-- Routing: Instantly calculates the path from Spawn -> Fire using the specific traffic conditions of the selected date.

## 📋 Requirements

- Python 3.11+
- See `requirements.txt` for dependencies

## 📄 License

MIT License — feel free to use and modify.
