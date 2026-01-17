import pandas as pd
import numpy as np
import joblib
import logging
import os
from typing import Dict, Any

from sklearn.model_selection import train_test_split, GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Rutas
DATA_PATH = "data/training_set.csv"
MODEL_PATH = "data/model_winner.pkl"

def load_data(path: str):
    """Carga el dataset procesado y separa Features (X) de Target (y)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"No se encontró el archivo {path}. Ejecuta feature_eng.py primero.")
    
    df = pd.read_csv(path)
    
    # Eliminar columnas que no son features numéricos para el modelo
    # Mantenemos solo lo numérico y relevante definido en el Schema
    features = [
        'last_5_home_points', 
        'last_5_away_points', 
        'rest_days_home', 
        'rest_days_away', 
        'h2h_home_wins'
        # Aquí se añadirían 'missing_players_value' si tuviéramos esa fuente activa
    ]
    
    X = df[features]
    y = df['TARGET'] # 0: Home, 1: Draw, 2: Away
    
    logger.info(f"Datos cargados. Features: {X.shape}, Target distribuido: {y.value_counts().to_dict()}")
    return X, y

def get_pipeline(model_type: str) -> Pipeline:
    """
    Fábrica de Pipelines con mejoras para desbalanceo de clases.
    """
    if model_type == 'rf':
        # CAMBIO CLAVE: balanced_subsample es más agresivo a favor de los empates
        clf = RandomForestClassifier(
            random_state=42, 
            class_weight='balanced_subsample', 
            n_estimators=200  # Aumentamos árboles para estabilizar
        )
    elif model_type == 'lr':
        clf = LogisticRegression(
            random_state=42, 
            multi_class='multinomial', 
            solver='lbfgs', 
            max_iter=1000,
            class_weight='balanced' # Importante para Regresión también
        )
    elif model_type == 'dt':
        clf = DecisionTreeClassifier(random_state=42, class_weight='balanced')
    else:
        raise ValueError("Modelo desconocido")
        
    return Pipeline([
        ('scaler', StandardScaler()), 
        ('clf', clf)
    ])

def train_and_evaluate():
    try:
        X, y = load_data(DATA_PATH)
        
        # Split Train/Test
        # Nota de Arquitecto: En series temporales estrictas se usa TimeSeriesSplit,
        # pero para esta versión MVP usamos train_test_split aleatorio.
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # Definir el "Torneo de Modelos"
        model_configs = [
            {
                'name': 'Random Forest',
                'pipeline': get_pipeline('rf'),
                'params': {
                    'clf__n_estimators': [50, 100, 200],
                    'clf__max_depth': [None, 10, 20],
                    'clf__min_samples_split': [2, 5]
                }
            },
            {
                'name': 'Logistic Regression',
                'pipeline': get_pipeline('lr'),
                'params': {
                    'clf__C': [0.1, 1.0, 10.0]
                }
            },
            {
                'name': 'Decision Tree',
                'pipeline': get_pipeline('dt'),
                'params': {
                    'clf__max_depth': [5, 10, 20],
                    'clf__criterion': ['gini', 'entropy']
                }
            }
        ]
        
        best_overall_model = None
        best_overall_score = -1
        
        logger.info("Iniciando Torneo de Modelos (GridSearchCV)...")
        
        for config in model_configs:
            print(f"\n--- Evaluando: {config['name']} ---")
            
            # Grid Search con Cross Validation (3-folds)
            grid = GridSearchCV(config['pipeline'], config['params'], cv=3, scoring='accuracy', n_jobs=-1)
            grid.fit(X_train, y_train)
            
            # Evaluación en Test Set (Datos no vistos)
            y_pred = grid.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            
            print(f"Mejores Parámetros: {grid.best_params_}")
            print(f"Accuracy en Test: {acc:.4f}")
            print("Matriz de Confusión:")
            print(confusion_matrix(y_test, y_pred))
            
            # Lógica de "Rey de la Colina"
            if acc > best_overall_score:
                best_overall_score = acc
                best_overall_model = grid.best_estimator_
                logger.info(f"¡Nuevo Líder! {config['name']} con accuracy {acc:.4f}")
        
        # Guardar el ganador absoluto
        if best_overall_model:
            joblib.dump(best_overall_model, MODEL_PATH)
            logger.info(f"\n✅ GANADOR GUARDADO: {MODEL_PATH}")
            logger.info(f"Modelo: {best_overall_model.named_steps['clf']}")
            logger.info(f"Accuracy Final: {best_overall_score:.4f}")
            
            # Generar reporte completo del ganador
            y_final_pred = best_overall_model.predict(X_test)
            print("\n--- REPORTE FINAL DEL GANADOR ---")
            print(classification_report(y_test, y_final_pred, target_names=['Local', 'Empate', 'Visitante']))
        else:
            logger.error("No se pudo entrenar ningún modelo.")

    except Exception as e:
        logger.error(f"Error crítico en el entrenamiento: {e}")
        raise e

if __name__ == "__main__":
    train_and_evaluate()