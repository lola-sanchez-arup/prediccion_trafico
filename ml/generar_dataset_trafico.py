import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# -------------------------
# Configuración
# -------------------------
zonas = [
    "Centro",
    "Norte – Universidad",
    "Sur – Este",
    "Oeste",
    "Parque Coimbra – Guadarrama",
    "Sur"
]

# Periodos vacacionales (Tráfico baja en zonas escolares/laborales, sube en salidas)
vacaciones_periodos = [
    ("2024-03-22", "2024-04-01"), # Semana Santa
    ("2024-07-15", "2024-08-31"), # Verano
    ("2024-12-22", "2025-01-07"), # Navidad
]

def es_vacaciones(fecha):
    s_fecha = fecha.strftime("%Y-%m-%d")
    for ini, fin in vacaciones_periodos:
        if ini <= s_fecha <= fin:
            return True
    return False

def obtener_trafico_zona(fecha, zona):
    """
    Devuelve nivel de tráfico (0, 1, 2) basado en reglas de negocio específicas
    0: Fluido | 1: Moderado | 2: Denso
    """
    dia_semana = fecha.weekday() # 0=Lun, 1=Mar, ..., 5=Sab, 6=Dom
    vacaciones = es_vacaciones(fecha)
    
    # Probabilidad base [Bajo, Medio, Alto]
    probs = [1.0, 0.0, 0.0] 

    # ---------------------------------------------------------
    # 1. OESTE (Acceso A-5) - CRÍTICA
    # Obras A-5 + Tráfico diario fuerte
    # ---------------------------------------------------------
    if zona == "Oeste":
        if vacaciones:
            # En vacaciones baja el laboral pero se mantiene el de viaje
            probs = [0.2, 0.5, 0.3]
        elif dia_semana <= 4: # Lunes a Viernes
            # Altísima probabilidad de atasco por obras y pendularidad
            probs = [0.05, 0.25, 0.70] 
        else: # Finde
            probs = [0.4, 0.4, 0.2]

    # ---------------------------------------------------------
    # 2. SUR - ESTE (Polígonos / M-506) - CRÍTICA LABORAL
    # Fuerte Martes-Jueves
    # ---------------------------------------------------------
    elif zona == "Sur – Este":
        if vacaciones:
            # Polígonos vacíos
            probs = [0.8, 0.2, 0.0]
        elif dia_semana in [1, 2, 3]: # Martes, Miércoles, Jueves
            probs = [0.1, 0.3, 0.6]
        elif dia_semana in [0, 4]: # Lunes, Viernes
            probs = [0.2, 0.5, 0.3]
        else: # Finde
            probs = [0.9, 0.1, 0.0]

    # ---------------------------------------------------------
    # 3. CENTRO (ZBE / Comercial)
    # Lento siempre, peor Sábados y viernes tarde
    # ---------------------------------------------------------
    elif zona == "Centro":
        if dia_semana == 5: # Sábado (Comercio)
            probs = [0.1, 0.3, 0.6]
        elif dia_semana == 4: # Viernes (Víspera festivo/ocio)
            probs = [0.2, 0.4, 0.4]
        elif dia_semana == 6: # Domingo (Cerrado)
            probs = [0.8, 0.2, 0.0]
        else: # L-J (ZBE hace que sea fluido/medio, no colapsado)
            probs = [0.4, 0.5, 0.1]

    # ---------------------------------------------------------
    # 4. NORTE – UNIVERSIDAD (Hospital / URJC)
    # ---------------------------------------------------------
    elif zona == "Norte – Universidad":
        if vacaciones:
            # Sin universidad baja drásticamente
            probs = [0.9, 0.1, 0.0]
        elif dia_semana <= 4: # Lunes a Viernes (Clases/Hospital)
            probs = [0.1, 0.5, 0.4]
        else: # Finde
            probs = [0.8, 0.2, 0.0]

    # ---------------------------------------------------------
    # 5. SUR (PAU-4) - Residencial / Salida M-50
    # ---------------------------------------------------------
    elif zona == "Sur":
        if dia_semana == 0 or dia_semana == 4: # Lun/Vie (Salida/Entrada fin de semana)
            probs = [0.2, 0.4, 0.4]
        elif dia_semana <= 3: # Mar-Jue
            probs = [0.4, 0.5, 0.1]
        else: # Finde
            probs = [0.7, 0.3, 0.0]

    # ---------------------------------------------------------
    # 6. PARQUE COIMBRA (A-5 km 22-25) - VARIABLE
    # ---------------------------------------------------------
    elif zona == "Parque Coimbra – Guadarrama":
        if dia_semana == 4: # Viernes tarde (Salida Madrid)
            probs = [0.3, 0.3, 0.4]
        elif dia_semana == 6: # Domingo tarde (Retorno Madrid)
            probs = [0.2, 0.3, 0.5]
        else: # Resto de días fluido (es una urba externa)
            probs = [0.9, 0.1, 0.0]

    # Elegir nivel basado en probabilidad (añade "ruido" natural)
    return np.random.choice([0, 1, 2], p=probs)

# -------------------------
# Generación
# -------------------------
print("Generando dataset de tráfico realista...")
data = []

# Últimos 12 meses
fecha_fin = datetime.now()
fecha_ini = fecha_fin - timedelta(days=365)
dias_totales = (fecha_fin - fecha_ini).days

for i in range(dias_totales):
    fecha_actual = fecha_ini + timedelta(days=i)
    fecha_str = fecha_actual.strftime("%Y-%m-%d")
    
    dia_semana = fecha_actual.weekday()
    es_finde = 1 if dia_semana >= 5 else 0
    vacaciones = 1 if es_vacaciones(fecha_actual) else 0

    for zona in zonas:
        nivel = obtener_trafico_zona(fecha_actual, zona)
        
        data.append({
            "fecha": fecha_str,
            "dia_semana": dia_semana,
            "es_fin_de_semana": es_finde,
            "vacaciones": vacaciones,
            "zona": zona,
            "nivel_trafico": nivel
        })

# Crear DataFrame y guardar
df = pd.DataFrame(data)
csv_name = "trafico_sintetico_mostoles.csv"
df.to_csv(csv_name, index=False)

print(f"✅ Dataset generado: {csv_name} con {len(df)} registros.")
print(df.sample(10)) # Muestra aleatoria para verificar variedad