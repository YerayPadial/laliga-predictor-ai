import streamlit as st
import pandas as pd
import joblib
import os
import matplotlib.pyplot as plt

# Importamos la función de predicción
# Asegúrate de que src.feature_eng tiene prepare_upcoming_matches
from src.feature_eng import prepare_upcoming_matches

# Configuración Inicial
st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .match-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #444;
    }
    .team-row { display: flex; justify-content: space-between; align-items: center; }
    .vs { font-weight: bold; color: #888; padding: 0 10px; }
    .pred-badge {
        font-weight: bold; padding: 5px 10px; border-radius: 5px; color: white;
        text-align: center; min-width: 40px; display: inline-block;
    }
    .pred-1 { background-color: #4CAF50; border: 1px solid #43A047; }
    .pred-X { background-color: #FFC107; color: black !important; border: 1px solid #FFB300; }
    .pred-2 { background-color: #F44336; border: 1px solid #E53935; }
    
    .status-badge {
        font-size: 0.7em; padding: 2px 8px; border-radius: 4px; margin-left: 5px; text-transform: uppercase; font-weight: bold;
    }
    .status-LIVE { background-color: #E53935; color: white; animation: pulse 2s infinite; }
    .status-FINISHED { background-color: #555; color: #ddd; }
    
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    
    .prob-container { display: flex; margin-top: 10px; height: 6px; border-radius: 3px; overflow: hidden; }
    .prob-labels { display: flex; justify-content: space-between; font-size: 0.7em; color: #888; margin-top: 2px; }
</style>
""", unsafe_allow_html=True)

# Rutas actualizadas
MODEL_PATH = 'data/model_winner.pkl'
FIXTURES_PATH = 'data/laliga_fixtures.csv'
HISTORY_PATH = 'data/laliga_advanced_stats.csv'

def load_resources():
    # 1. Cargar Modelo
    if not os.path.exists(MODEL_PATH):
        st.error("❌ No se encontró el modelo. Ejecuta src/models.py")
        return None, None
    model = joblib.load(MODEL_PATH)

    # 2. Cargar Calendario
    if not os.path.exists(FIXTURES_PATH):
        st.error("❌ No hay calendario. Ejecuta src/api_client.py")
        return model, pd.DataFrame()
    
    fixtures = pd.read_csv(FIXTURES_PATH)
    return model, fixtures

def main():
    st.title("⚽ La Quiniela IA (Versión Experta)")
    
    model, df_fixtures = load_resources()
    if not model or df_fixtures.empty:
        return

    # Preparar datos para la IA
    # Le pasamos el calendario y el historial para que calcule rachas y H2H
    try:
        # DESEMPAQUETAMOS LOS DOS VALORES
        X_pred, matches_info = prepare_upcoming_matches(df_fixtures, HISTORY_PATH)
    except Exception as e:
        st.error(f"Error procesando datos: {e}")
        return

    # Verificamos si X_pred es válido y no está vacío
    if X_pred is None or X_pred.empty:
        st.info("📅 Calendario actualizado, pero no hay datos suficientes para predecir (quizás inicio de temporada o equipos nuevos).")
        return

    # Predecir
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- LÓGICA DE JORNADA ---
    # Igual que antes: Buscamos la próxima jornada activa
    df_fixtures['matchday'] = pd.to_numeric(df_fixtures['matchday'], errors='coerce').fillna(0).astype(int)
    pending = df_fixtures[df_fixtures['status'] != 'FINISHED']
    
    if not pending.empty:
        # Ordenar por fecha real para encontrar el "próximo partido" real
        pending = pending.sort_values('utc_date')
        active_matchday = pending.iloc[0]['matchday']
    else:
        active_matchday = df_fixtures['matchday'].max()

    # Filtramos solo los partidos de esa jornada que la IA ha podido procesar
    # OJO: X_pred puede tener menos filas que df_fixtures si faltan datos de algún equipo
    # Necesitamos alinear las predicciones con los partidos originales
    
    # Creamos una lista visual solo con los partidos que están en X_pred (los que tienen predicción)
    # X_pred conserva el índice original del DataFrame de fixtures, así que usamos eso para unir
    
    indices_predichos = X_pred.index
    matches_to_show = df_fixtures.loc[indices_predichos]
    
    # Filtramos por jornada activa
    matches_to_show = matches_to_show[matches_to_show['matchday'] == active_matchday]

    if matches_to_show.empty:
        st.info(f"No hay predicciones disponibles para la Jornada {active_matchday}.")
        return

    st.markdown(f"<h3 style='text-align:center; margin-bottom: 20px;'>Jornada {active_matchday}</h3>", unsafe_allow_html=True)

    # --- RENDERIZADO VISUAL ---
    # Iteramos por los partidos filtrados
    for idx, row in matches_to_show.iterrows():
        # Buscamos la predicción correspondiente a este índice
        # Como X_pred y matches_to_show comparten índice, podemos buscar por posición relativa
        
        # Truco: Encontrar en qué posición de X_pred está este índice
        loc_idx = X_pred.index.get_loc(idx)
        
        pred = predictions[loc_idx]
        prob = probs[loc_idx]
        
        p1, pX, p2 = prob[0]*100, prob[1]*100, prob[2]*100
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        status = row.get('status', 'SCHEDULED')
        status_html = ""
        result_display = "vs"
        
        if status in ['IN_PLAY', 'PAUSED', 'LIVE']:
            status_html = "<span class='status-badge status-LIVE'>EN JUEGO</span>"
        elif status == 'FINISHED':
            status_html = "<span class='status-badge status-FINISHED'>FINALIZADO</span>"
            result_display = row.get('real_result', 'vs')

        st.markdown(f"""
    <div class="match-card">
        <div style="text-align:center; color:#aaa; font-size:0.8em; margin-bottom:5px;">
        {row['date_str']} {status_html}
        </div>
        <div class="team-row">
        <div style="flex:1; text-align:right; font-weight:bold; font-size:1.1em;">{row['home_team']}</div>
        <div class="vs" style="color:white; font-size:1.2em;">{result_display}</div>
        <div style="flex:1; text-align:left; font-weight:bold; font-size:1.1em;">{row['away_team']}</div>
        </div>

        <div style="display:flex; justify-content:center; align-items:center; gap:10px; margin-top:10px;">
        <span style="font-size:0.8em; color:#bbb;">IA:</span>
        <div class="pred-badge {color_class}">{winner_code}</div>
        <span style="font-size:0.8em; color:#ccc;">({confidence:.0f}%)</span>
        </div>

        <div class="prob-container">
        <div style="width:{p1}%; background-color:#4CAF50;" title="Local: {p1:.0f}%"></div>
        <div style="width:{pX}%; background-color:#FFC107;" title="Empate: {pX:.0f}%"></div>
        <div style="width:{p2}%; background-color:#F44336;" title="Visitante: {p2:.0f}%"></div>
        </div>
        <div class="prob-labels">
        <span>1: {p1:.0f}%</span>
        <span>X: {pX:.0f}%</span>
        <span>2: {p2:.0f}%</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()