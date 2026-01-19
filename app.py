import streamlit as st
import pandas as pd
import joblib
import os
from src.feature_eng import prepare_upcoming_matches

# Configuración Inicial
st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# --- ESTILOS CSS (Añadí los estilos para la barra y los estados) ---
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
    
    /* Nuevos Estilos para Estado y Barra */
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

MODEL_PATH = 'data/model_winner.pkl'
FIXTURES_PATH = 'data/laliga_fixtures.csv'
RAW_DATA_PATH = 'data/laliga_results_raw.csv'

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

    # 2. Resetear índices
    df_info = df_info.reset_index(drop=True)
    
    # 3. Predecir
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- LÓGICA DE JORNADAS ---
    if 'matchday' in df_info.columns:
        df_info['matchday'] = pd.to_numeric(df_info['matchday'], errors='coerce').fillna(0).astype(int)
        available_matchdays = sorted(df_info['matchday'].unique())
        available_matchdays = [m for m in available_matchdays if m > 0]
        if not available_matchdays: available_matchdays = [1]
    else:
        available_matchdays = [1]

    if 'current_md_index' not in st.session_state:
        st.session_state.current_md_index = 0
    
    md_idx = max(0, min(st.session_state.current_md_index, len(available_matchdays) - 1))
    current_matchday = available_matchdays[md_idx]
    
    matches_mask = df_info['matchday'] == current_matchday
    current_matches = df_info[matches_mask]

    # --- BOTONES ---
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

    if current_matches.empty:
        st.info("No hay partidos para mostrar en esta jornada.")

    # --- RENDERIZADO (ESTILO CLÁSICO) ---
    for local_idx, row in current_matches.iterrows():
        pred = predictions[local_idx]
        prob = probs[local_idx]
        p1, pX, p2 = prob[0]*100, prob[1]*100, prob[2]*100
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        # Estado del partido
        status = row.get('status', 'SCHEDULED')
        status_html = ""
        result_display = "vs"
        
        if status in ['IN_PLAY', 'PAUSED', 'LIVE']:
            status_html = f"<span class='status-badge status-LIVE'>EN JUEGO</span>"
        elif status == 'FINISHED':
            status_html = f"<span class='status-badge status-FINISHED'>FINALIZADO</span>"
            result_display = row.get('real_result', 'vs')

        # --- AQUI ESTÁ TU ESTRUCTURA ORIGINAL + BARRA ---
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