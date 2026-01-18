import streamlit as st
import pandas as pd
import joblib
import os
from src.feature_eng import prepare_upcoming_matches

# Configuración Inicial
st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# Estilos CSS
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
        text-align: center; min-width: 40px;
    }
    .pred-1 { background-color: #4CAF50; }
    .pred-X { background-color: #FFC107; color: black !important; }
    .pred-2 { background-color: #F44336; }
    
    /* Botones de Navegación */
    .nav-btn { width: 100%; }
</style>
""", unsafe_allow_html=True)

MODEL_PATH = 'data/model_winner.pkl'
FIXTURES_PATH = 'data/laliga_fixtures.csv'
RAW_DATA_PATH = 'data/laliga_results_raw.csv'

# Tamaño de Jornada (Partidos por página)
MATCHES_PER_ROUND = 10 

def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

def main():
    st.title("⚽ La Quiniela IA")
    st.caption("Predicciones para las próximas jornadas")

    model = load_model()
    if not model:
        st.error("⚠️ Modelo no encontrado.")
        return

    # 1. Obtener Datos (Ya filtrados por fecha futura en feature_eng)
    X_pred, df_info = prepare_upcoming_matches(FIXTURES_PATH, RAW_DATA_PATH)

    if X_pred.empty:
        st.info("📅 No hay partidos pendientes. La temporada puede haber terminado.")
        return

    # 2. Resetear índices para evitar errores de sincronización
    # ESTO ES CRÍTICO PARA EVITAR EL ERROR 'IndexError'
    df_info = df_info.reset_index(drop=True)
    
    # 3. Predicciones Globales
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- LÓGICA DE PAGINACIÓN (JORNADAS) ---
    
    # Inicializar estado de sesión para saber en qué página estamos
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 0

    total_matches = len(df_info)
    total_pages = (total_matches // MATCHES_PER_ROUND) + (1 if total_matches % MATCHES_PER_ROUND > 0 else 0)
    
    # Asegurar que no nos salimos de rango
    current_page = max(0, min(st.session_state.page_number, total_pages - 1))
    
    # Calcular índices de inicio y fin para el slice
    start_idx = current_page * MATCHES_PER_ROUND
    end_idx = min(start_idx + MATCHES_PER_ROUND, total_matches)
    
    # Slice de datos para mostrar AHORA
    current_matches = df_info.iloc[start_idx:end_idx]
    
    # --- INTERFAZ DE NAVEGACIÓN ---
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if current_page > 0:
            if st.button("⬅️ Anterior", use_container_width=True):
                st.session_state.page_number -= 1
                st.rerun()

    with col_info:
        # Texto dinámico: Si es la página 0, es la "Jornada Actual"
        label = "Jornada Actual" if current_page == 0 else f"Próxima Jornada (+{current_page})"
        st.markdown(f"<div style='text-align:center; font-weight:bold; padding-top:10px;'>{label}<br><span style='color:#888; font-size:0.8em'>Partidos {start_idx+1} al {end_idx}</span></div>", unsafe_allow_html=True)

    with col_next:
        if current_page < total_pages - 1:
            if st.button("Siguiente ➡️", use_container_width=True):
                st.session_state.page_number += 1
                st.rerun()

    st.divider()

    # --- RENDERIZADO DE PARTIDOS ---
    # Usamos enumerate sobre el slice, pero necesitamos el índice GLOBAL para buscar la predicción correcta
    for local_idx, row in current_matches.iterrows():
        # local_idx es el índice real del DataFrame global (gracias al reset_index previo)
        
        home = row['home_team']
        away = row['away_team']
        
        # Accedemos a la predicción usando el mismo índice
        pred = predictions[local_idx]
        prob = probs[local_idx]
        
        # Formatear
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        # HTML Card
        st.markdown(f"""
        <div class="match-card">
            <div style="text-align:center; margin-bottom:5px; color:#aaa; font-size:0.8em;">{row.get('date_str', 'Próximamente')}</div>
            <div class="team-row">
                <div style="flex:1; text-align:right; font-weight:bold; font-size:1.1em;">{home}</div>
                <div class="vs">vs</div>
                <div style="flex:1; text-align:left; font-weight:bold; font-size:1.1em;">{away}</div>
            </div>
            <div style="display:flex; justify-content:center; margin-top:10px; align-items:center; gap:10px;">
                <span>Predicción:</span>
                <div class="pred-badge {color_class}">{winner_code}</div>
                <span style="font-size:0.8em; color:#ccc;">(Confianza: {confidence:.0f}%)</span>
            </div>
             <div style="display:flex; margin-top:10px; height:6px; border-radius:3px; overflow:hidden;">
                <div style="width:{prob[0]*100}%; background-color:#4CAF50;" title="Local: {prob[0]*100:.1f}%"></div>
                <div style="width:{prob[1]*100}%; background-color:#FFC107;" title="Empate: {prob[1]*100:.1f}%"></div>
                <div style="width:{prob[2]*100}%; background-color:#F44336;" title="Visitante: {prob[2]*100:.1f}%"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()