import streamlit as st
import pandas as pd
import joblib
import os
from src.feature_eng import prepare_upcoming_matches

st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

st.markdown("""
<style>
    .match-card { background-color: #262730; padding: 15px; border-radius: 10px; margin-bottom: 15px; border: 1px solid #444; }
    .team-row { display: flex; justify-content: space-between; align-items: center; }
    .vs { font-weight: bold; color: #888; padding: 0 10px; }
    .pred-badge { font-weight: bold; padding: 5px 10px; border-radius: 5px; color: white; text-align: center; min-width: 40px; }
    .pred-1 { background-color: #4CAF50; }
    .pred-X { background-color: #FFC107; color: black !important; }
    .pred-2 { background-color: #F44336; }
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

    X_pred, df_info = prepare_upcoming_matches(FIXTURES_PATH, RAW_DATA_PATH)

    if X_pred.empty:
        st.info("📅 Calendario actualizado. No hay partidos pendientes descargados.")
        return

    # Reset index vital
    df_info = df_info.reset_index(drop=True)
    
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- LÓGICA DE JORNADAS (MATCHDAYS) ---
    # Obtenemos la lista de jornadas disponibles en los datos
    if 'matchday' in df_info.columns:
        available_matchdays = sorted(df_info['matchday'].unique())
    else:
        available_matchdays = [1] # Fallback si no hay columna

    if 'current_md_index' not in st.session_state:
        st.session_state.current_md_index = 0
    
    # Navegación segura
    md_idx = max(0, min(st.session_state.current_md_index, len(available_matchdays) - 1))
    current_matchday = available_matchdays[md_idx]
    
    # Filtrar solo los partidos de ESTA jornada
    matches_mask = df_info['matchday'] == current_matchday
    current_matches = df_info[matches_mask]

    # --- INTERFAZ ---
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if md_idx > 0:
            if st.button(f"⬅️ Jornada {available_matchdays[md_idx-1]}"):
                st.session_state.current_md_index -= 1
                st.rerun()
    with c2:
        st.markdown(f"<h3 style='text-align:center'>Jornada {current_matchday}</h3>", unsafe_allow_html=True)
    with c3:
        if md_idx < len(available_matchdays) - 1:
            if st.button(f"Jornada {available_matchdays[md_idx+1]} ➡️"):
                st.session_state.current_md_index += 1
                st.rerun()

    st.divider()

    # Renderizar
    for local_idx, row in current_matches.iterrows():
        # Usamos el índice global para sacar la predicción correcta
        pred = predictions[local_idx]
        prob = probs[local_idx]
        
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        st.markdown(f"""
        <div class="match-card">
            <div style="text-align:center; color:#aaa; font-size:0.8em;">{row['date_str']}</div>
            <div class="team-row">
                <div style="flex:1; text-align:right; font-weight:bold; font-size:1.1em;">{row['home_team']}</div>
                <div class="vs">vs</div>
                <div style="flex:1; text-align:left; font-weight:bold; font-size:1.1em;">{row['away_team']}</div>
            </div>
            <div style="display:flex; justify-content:center; margin-top:10px; gap:10px;">
                <div class="pred-badge {color_class}">{winner_code}</div>
                <span style="align-self:center; font-size:0.8em;">({confidence:.0f}%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()