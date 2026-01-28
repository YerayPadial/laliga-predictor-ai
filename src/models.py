import pandas as pd
import joblib
import logging
import os
import sys
import numpy as np

# Truco para imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.metrics import accuracy_score, classification_report, log_loss
from feature_eng import prepare_data

# Configuración
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "data")
MODEL_PATH = os.path.join(MODEL_DIR, "model_winner.pkl")
os.makedirs(MODEL_DIR, exist_ok=True)

def train_and_evaluate():
    logger.info("🚀 INICIANDO ENTRENAMIENTO 'NIVEL EXPERTO'...")
    
    # 1. Cargar datos
    df = prepare_data(train_mode=True)
    if df.empty:
        logger.error("❌ No hay datos. Ejecuta 'src/stats_scraper.py' primero.")
        return

    # 2. Separación Temporal Estricta
    # 85% para entrenar/optimizar, 15% para la prueba de fuego final
    split_idx = int(len(df) * 0.85)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    logger.info(f"📊 Dataset Total: {len(df)} partidos")
    logger.info(f"   🔸 Entrenamiento y Optimización: {len(train_df)} partidos")
    logger.info(f"   🔸 Validación Final (Futuro):    {len(test_df)} partidos")

    features = [c for c in df.columns if c not in ['date', 'home_team', 'away_team', 'TARGET']]
    X_train = train_df[features]
    y_train = train_df['TARGET']
    X_test = test_df[features]
    y_test = test_df['TARGET']

    # 3. DEFINICIÓN DEL BUSCADOR DE HIPERPARÁMETROS
    # En lugar de valores fijos, damos rangos para que la IA busque lo mejor
    param_dist = {
        'n_estimators': [100, 200, 300],        # ¿Cuántos árboles?
        'learning_rate': [0.01, 0.05, 0.1],     # ¿Qué tan rápido aprende?
        'max_depth': [3, 4, 5],                 # ¿Qué tan complejo es cada árbol?
        'subsample': [0.7, 0.8, 0.9, 1.0],      # ¿Cuánto dato usa para evitar memorizar?
        'min_samples_leaf': [1, 2, 4]           # Evitar reglas demasiado específicas
    }

    # Modelo base
    gbm = GradientBoostingClassifier(random_state=42)

    # Configuración de Validación Cruzada Temporal
    # Esto simula entrenar en 2020->Predecir 2021, Entrenar 2021->Predecir 2022...
    tscv = TimeSeriesSplit(n_splits=5)

    logger.info("🧠 Buscando la configuración perfecta (Grid Search)... Esto tomará unos segundos.")
    
    # Búsqueda Aleatoria (Más rápido y eficiente que probar todo)
    search = RandomizedSearchCV(
        estimator=gbm,
        param_distributions=param_dist,
        n_iter=20,              # Probar 20 combinaciones distintas
        scoring='neg_log_loss', # Optimizar para CONFIANZA (probabilidad), no solo acierto
        cv=tscv,                # Usar split temporal (vital en fútbol)
        n_jobs=-1,              # Usar todos los núcleos del PC
        random_state=42,
        verbose=1
    )

    search.fit(X_train, y_train)
    
    best_model = search.best_estimator_
    logger.info(f"✅ Mejor configuración encontrada: {search.best_params_}")

    # 4. Evaluación Final en datos nunca vistos (Test Set)
    predictions = best_model.predict(X_test)
    probs = best_model.predict_proba(X_test)
    
    acc = accuracy_score(y_test, predictions)
    loss = log_loss(y_test, probs)
    
    print("\n" + "="*40)
    print(f"🏆 RESULTADOS DEL MODELO EXPERTO")
    print("="*40)
    print(f"🎯 PRECISIÓN (Accuracy): {acc:.2%}")
    print(f"📉 LOG LOSS (Confianza): {loss:.4f} (Menor a 1.0 es excelente)")
    print("-" * 40)
    
    print("\n📝 Reporte por Resultado:")
    print(classification_report(y_test, predictions, target_names=['Local (1)', 'Empate (X)', 'Visitante (2)']))
    
    # 5. Análisis de Importancia (Qué mira la IA)
    importance = pd.DataFrame({
        'Variable': features,
        'Importancia': best_model.feature_importances_
    }).sort_values('Importancia', ascending=False)
    
    print("\n⭐ FACTORES CLAVE (Top 5):")
    print(importance.head(5).to_string(index=False))

    # 6. Guardar
    joblib.dump(best_model, MODEL_PATH)
    logger.info(f"\n💾 Cerebro optimizado guardado en: {MODEL_PATH}")

if __name__ == "__main__":
    train_and_evaluate()