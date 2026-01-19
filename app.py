import streamlit as st
import pandas as pd
import joblib
import os
import textwrap
from src.feature_eng import prepare_upcoming_matches

# Configuración Inicial
st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .match-card {
        background-color: #262730;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 16px;
        border: 1px solid #444;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .team-row { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        margin-bottom: 15px; 
    }
    .vs { 
        font-weight: bold; 
        color: #888; 
        padding: 0 15px; 
        font-size: 0.9em;
    }
    .pred-badge {
        font-weight: bold; 
        padding: 6px 14px; 
        border-radius: 6px; 
        color: white; 
        text-align: center; 
        min-width: 45px; 
        display: inline-block;
    }
    .pred-1 { background-color: #4CAF50; border: 1px solid #43A047; }
    .pred-X { background-color: #FFC107; color: black !important; border: 1px solid #FFB300; }
    .pred-2 { background-color: #F44336; border: 1px solid #E53935; }
    
    /* Badges de Estado (LIVE / FINISHED) */
    .status-badge {
        font-size: 0.7em; 
        padding: 3px 8px; 
        border-radius: 4px; 
        margin-left: 8px; 
        text-transform: uppercase;
        font-weight: bold;
        vertical-align: middle;
    }
    .status-LIVE { background-color: #E53935; color: white; animation: pulse 2s infinite; }
    .status-FINISHED { background-color: #555; color: #ddd; border: 1px solid #777; }
    
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    
    .prob-container { 
        display: flex; 
        margin-top: 15px; 
        height: 10px; 
        border-radius: 5px; 
        overflow: hidden; 
        width: 100%; 
        background-color: #444;
    }
    .prob-segment { height: 100%; }
    
    .prob-labels { 
        display: flex; 
        justify-content: space-between; 
        font-size: 0.8em; 
        color: #bbb; 
        margin-top: 6px; 
        font-family: monospace;
    }
</style>
""", unsafe_allow_html=True)

MODEL_PATH = 'data/model_winner.pkl'
FIXTURES_PATH = 'data/laliga_fixtures.csv'
RAW_DATA_PATH = 'data/laliga_results_raw.csv'

# Tamaño de Jornada (aunque ahora la API manda, esto sirve de fallback)
MATCHES_PER_ROUND = 10 

def load_model():
    if os.path.exists(MODEL_PATH): return joblib.load(MODEL_PATH)
    return None

def main():
    st.title("⚽ La Quiniela IA")
    
    model = load_model()
    if not model:
        st.error("⚠️ Modelo no encontrado.")
        return

    # 1. Cargar Datos
    X_pred, df_info = prepare_upcoming_matches(FIXTURES_PATH, RAW_DATA_PATH)

    if X_pred.empty:
        st.info("📅 Calendario actualizado. Esperando datos de API.")
        return

    # 2. Resetear índices (CRÍTICO)
    df_info = df_info.reset_index(drop=True)
    
    # 3. Predicciones
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- LÓGICA DE NAVEGACIÓN (JORNADAS) ---
    if 'matchday' in df_info.columns:
        df_info['matchday'] = pd.to_numeric(df_info['matchday'], errors='coerce').fillna(0).astype(int)
        available_matchdays = sorted(df_info['matchday'].unique())
        # Eliminar jornadas 0 si las hubiera
        available_matchdays = [m for m in available_matchdays if m > 0]
        if not available_matchdays: available_matchdays = [1]
    else:
        available_matchdays = [1]

    if 'current_md_index' not in st.session_state:
        st.session_state.current_md_index = 0
    
    # Asegurar rango
    md_idx = max(0, min(st.session_state.current_md_index, len(available_matchdays) - 1))
    current_matchday = available_matchdays[md_idx]
    
    matches_mask = df_info['matchday'] == current_matchday
    current_matches = df_info[matches_mask]

    # --- BOTONERA ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if md_idx > 0:
            if st.button(f"⬅️ Jornada {available_matchdays[md_idx-1]}", use_container_width=True):
                st.session_state.current_md_index -= 1
                st.rerun()
    with c2:
        st.markdown(f"<h3 style='text-align:center; margin:0;'>Jornada {current_matchday}</h3>", unsafe_allow_html=True)
    with c3:
        if md_idx < len(available_matchdays) - 1:
            if st.button(f"Jornada {available_matchdays[md_idx+1]} ➡️", use_container_width=True):
                st.session_state.current_md_index += 1
                st.rerun()

    st.divider()

    # --- RENDERIZADO ---
    if current_matches.empty:
        st.info("No hay partidos para mostrar en esta jornada.")

    for local_idx, row in current_matches.iterrows():
        pred = predictions[local_idx]
        prob = probs[local_idx]
        p1, pX, p2 = prob[0]*100, prob[1]*100, prob[2]*100
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        # --- LÓGICA DE ESTADO (TU NUEVA FEATURE) ---
        status = row.get('status', 'SCHEDULED')
        status_html = ""
        result_display = "vs" # Por defecto
        
        # Si está en juego o pausa
        if status in ['IN_PLAY', 'PAUSED', 'LIVE']:
            status_html = f"<span class='status-badge status-LIVE'>EN JUEGO</span>"
        # Si terminó
        elif status == 'FINISHED':
            status_html = f"<span class='status-badge status-FINISHED'>FINALIZADO</span>"
            result_display = row.get('real_result', 'vs') # Muestra "2-1" o "vs" si falla

        # --- HTML BLINDADO CON DEDENT ---
        html_code = f"""
<div class="match-card">
    <div style="text-align:center; color:#aaa; font-size:0.85em; margin-bottom:12px; font-family:monospace;">
        📅 {row['date_str']} {status_html}
    </div>
    
    <div class="team-row">
        <div style="flex:1; text-align:right; font-weight:bold; font-size:1.2em;">{row['home_team']}</div>
        <div class="vs" style="font-size: 1.4em; color: white;">{result_display}</div>
        <div style="flex:1; text-align:left; font-weight:bold; font-size:1.2em;">{row['away_team']}</div>
    </div>
    
    <div style="display:flex; justify-content:center; align-items:center; gap:12px; margin-bottom:12px;">
        <span style="font-size:0.9em; color:#ddd;">IA Predice:</span>
        <div class="pred-badge {color_class}">{winner_code}</div>
        <span style="font-size:0.85em; color:#aaa;">({confidence:.0f}%)</span>
    </div>
    
    <div class="prob-container">
        <div class="prob-segment" style="width:{p1}%; background-color:#4CAF50;" title="Local: {p1:.1f}%"></div>
        <div class="prob-segment" style="width:{pX}%; background-color:#FFC107;" title="Empate: {pX:.1f}%"></div>
        <div class="prob-segment" style="width:{p2}%; background-color:#F44336;" title="Visitante: {p2:.1f}%"></div>
    </div>
    
    <div class="prob-labels">
        <span style="color:#4CAF50;">1: {p1:.0f}%</span>
        <span style="color:#FFC107;">X: {pX:.0f}%</span>
        <span style="color:#F44336;">2: {p2:.0f}%</span>
    </div>
</div>
"""
        st.markdown(html_code, unsafe_allow_html=True)

if __name__ == "__main__":
    main()