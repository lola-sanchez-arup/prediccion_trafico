import os
import geopandas as gpd
import numpy as np
import networkx as nx
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree
import json

# -------------------------
# Parámetros / archivos
# -------------------------
GEOJSON_CALLES = "data/callesconzonas.geojson" 
CRS_PROJECTED = 25830   # ETRS89 / UTM zone 30N (m)

# -------------------------
# Carga y Validación
# -------------------------
if not os.path.exists(GEOJSON_CALLES):
    raise FileNotFoundError(f"❌ No encuentro {GEOJSON_CALLES}")

print(f"🔄 Cargando red viaria exacta desde {GEOJSON_CALLES}...")
gdf_edges = gpd.read_file(GEOJSON_CALLES)

if gdf_edges.crs and gdf_edges.crs.to_epsg() != CRS_PROJECTED:
    gdf_edges = gdf_edges.to_crs(epsg=CRS_PROJECTED)

# -------------------------
# Funciones de ayuda 
# -------------------------
def parse_numeric_tag(val):
    if val is None: return None
    try:
        return float(str(val).lower().replace("km/h","").strip())
    except: return None

def speed_for_row(row):
    ms = parse_numeric_tag(row.get('maxspeed'))
    if ms: return ms
    hw = row.get('highway', '')
    # Mapa de velocidades estándar
    if hw in ['motorway', 'trunk']: return 80.0
    if hw in ['primary', 'secondary']: return 50.0
    return 30.0

def interpret_oneway(val):
    if val is None: return 'no'
    v = str(val).strip().lower()
    if v in ['yes', 'true', '1', 'y', 'only']: return 'yes'
    if v == '-1': return '-1'
    return 'no'

# Asegurar columna zona
if 'zona' not in gdf_edges.columns:
    gdf_edges['zona'] = 'Desconocida'
else:
    gdf_edges['zona'] = gdf_edges['zona'].astype(str).str.strip()

gdf_edges['oneway_norm'] = gdf_edges['oneway'].apply(interpret_oneway)

# -------------------------
# Construcción del Grafo 
# -------------------------
G = nx.DiGraph()
node_id_map = {} # Mapeo de coordenadas (x,y) -> ID entero

def get_node_id(coord):
    # Redondeamos para asegurar que puntos muy cercanos se unan (conectar calles)
    key = (round(coord[0], 3), round(coord[1], 3))
    if key not in node_id_map:
        node_id_map[key] = len(node_id_map)
        # Guardamos coords reales para luego recuperar geometría
        G.add_node(node_id_map[key], x=coord[0], y=coord[1])
    return node_id_map[key]

print("⚙️ Construyendo grafo detallado segmento a segmento...")

for idx, row in gdf_edges.iterrows():
    geom = row.geometry
    speed_kph = speed_for_row(row)
    zona = row['zona']
    
    # 1. Analizar dirección
    raw_oneway = row.get('oneway')
    raw_junction = str(row.get('junction', '')).lower()
    
    # LÓGICA CORREGIDA:
    # Si es rotonda, SIEMPRE es oneway (OpenStreetMap dibuja las rotondas en dirección del tráfico)
    if 'roundabout' in raw_junction:
        oneway = 'yes'
    else:
        oneway = interpret_oneway(raw_oneway)

    # Manejar MultiLineStrings si las hubiera
    lines = [geom] if geom.geom_type == 'LineString' else list(geom.geoms)

    for ls in lines:
        coords = list(ls.coords)
        # Iteramos segmento a segmento (Esto preserva las curvas)
        for i in range(len(coords) - 1):
            a, b = coords[i], coords[i+1]
            u = get_node_id(a)
            v = get_node_id(b)

            # Distancia y tiempo base de este pequeño segmento
            seg_len = LineString([a, b]).length
            seg_time = seg_len / (speed_kph / 3.6)

            attr = {
                'length_m': seg_len,
                'travel_time_s': seg_time,
                'zona': zona
            }

            if oneway == 'yes':
                G.add_edge(u, v, **attr)
            elif oneway == '-1':
                G.add_edge(v, u, **attr)
            else:
                G.add_edge(u, v, **attr)
                G.add_edge(v, u, **attr)

print(f"✅ Grafo cargado: {len(G.nodes)} nodos, {len(G.edges)} aristas.")

# -------------------------
# KDTree (Búsqueda rápida)
# -------------------------
node_items = list(G.nodes(data=True))
# Extraemos coordenadas (x, y) de los datos del nodo
coords_list = np.array([[d['x'], d['y']] for _, d in node_items])
kdtree = cKDTree(coords_list)

def nearest_node_by_point(point_geom):
    _, idx = kdtree.query([point_geom.x, point_geom.y])
    return node_items[idx][0]

# -------------------------
# API: Rutas
# -------------------------
def generar_ruta_geojson_coords(orig_lat, orig_lon, dest_lat, dest_lon, traffic_predictions=None):
    # 1. Convertir Lat/Lon a UTM
    p_orig = gpd.GeoSeries([Point(orig_lon, orig_lat)], crs="EPSG:4326").to_crs(epsg=CRS_PROJECTED).iloc[0]
    p_dest = gpd.GeoSeries([Point(dest_lon, dest_lat)], crs="EPSG:4326").to_crs(epsg=CRS_PROJECTED).iloc[0]

    # 2. Buscar nodos más cercanos
    origin_node = nearest_node_by_point(p_orig)
    dest_node = nearest_node_by_point(p_dest)

    # 3. Función de peso dinámica (lógica de tráfico)
    def dynamic_weight(u, v, d):
        base = d.get('travel_time_s', 1)
        zona_edge = d.get('zona', 'Desconocida')
        factor = 1.0
        
        if traffic_predictions and zona_edge in traffic_predictions:
            nivel = traffic_predictions[zona_edge]
            if nivel == 1: factor = 1.5   # Medio
            elif nivel == 2: factor = 3.0 # Alto
            
        return base * factor

    try:
        # Usamos Dijkstra con el peso dinámico
        path = nx.dijkstra_path(G, origin_node, dest_node, weight=dynamic_weight)
    except nx.NetworkXNoPath:
        return None

    # 4. Reconstruir geometría y calcular totales
    
    path_coords = []
    total_len = 0
    total_time_real = 0
    
    # Recopilar coordenadas y datos
    for i in range(len(path) - 1):
        u = path[i]
        v = path[i+1]
        
        # Coordenadas
        # El nodo u ya tiene x,y guardados
        path_coords.append((G.nodes[u]['x'], G.nodes[u]['y']))
        
        # Datos de arista
        data = G[u][v]
        total_len += data['length_m']
        total_time_real += dynamic_weight(u, v, data)
    
    # Añadir el último punto
    last = path[-1]
    path_coords.append((G.nodes[last]['x'], G.nodes[last]['y']))

    line = LineString(path_coords)
    
    # Convertir a WGS84 para el mapa web
    gdf_route = gpd.GeoDataFrame(geometry=[line], crs=CRS_PROJECTED).to_crs(epsg=4326)
    geo_dict = json.loads(gdf_route.to_json())
    
    # Solo Km y Minutos 
    
    geo_dict['features'][0]['properties'] = {
        "length_m": round(total_len, 2),
        "time_s": round(total_time_real, 2),
        "traffic_impact": "Calculado" # Placeholder, en el front ya no lo muestras
    }
    
    return geo_dict

def get_network_wgs84():
    """Devuelve la red para pintar en Cesium"""
    gdf_wgs84 = gdf_edges.to_crs(epsg=4326)
    cols = ['geometry', 'zona', 'name', 'highway'] 
    valid_cols = [c for c in cols if c in gdf_wgs84.columns]
    return gdf_wgs84[valid_cols].to_json()