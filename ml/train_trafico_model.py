import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
import joblib

# Cargar dataset
df = pd.read_csv("ml/trafico_sintetico_mostoles.csv")

# Codificar zona
le_zona = LabelEncoder()
df["zona_encoded"] = le_zona.fit_transform(df["zona"])

X = df[[
    "dia_semana",
    "es_fin_de_semana",
    "vacaciones",
    "zona_encoded"
]]

y = df["nivel_trafico"]

# Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Modelo
model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,
    random_state=42
)

model.fit(X_train, y_train)

# Guardar modelo y encoder
joblib.dump(model, "modelo_trafico.pkl")
joblib.dump(le_zona, "encoder_zona.pkl")

print("Modelo entrenado y guardado")
