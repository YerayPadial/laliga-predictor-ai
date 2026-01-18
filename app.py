import streamlit as st
import pandas as pd
import joblib
import os
from src.feature_eng import prepare_upcoming_matches

st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# Estilos CSS Mejorados para la Barra
st.markdown("""
<style>
    .match-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border: 1px solid #444;
    }
    .team-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
    .vs { font-weight: bold; color: #888; padding: 0 10px; }
    
    /* Badges de Predicción */
    .pred-badge {
        font-weight: bold; padding: 5px 12px; border-radius: 5px; color: white;
        text-align: center; min-width: 40px; display: inline-block;
    }
    .pred-1 { background-color: #4CAF50; } /* Verde */
    .pred-X { background-color: #FFC107; color: black !important; } /* Amarillo */
    .pred-2 { background-color: #F44336; } /* Rojo */
    
    /* Barra de Probabilidad */
    .prob-container {
        display: flex; margin-top: 12px; height: 8px; border-radius: 4px; overflow: hidden; width: 100%;
    }
    .prob-segment { height: 100%; }
    
    /* Textos debajo de la barra */
    .prob-labels {
        display: flex; justify-content: space-between; 
        font-size: 0.75em; color: #ccc; margin-top: 4px;
    }
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
        st.info("📅 Calendario actualizado. No hay partidos pendientes.")
        return

    df_info = df_info.reset_index(drop=True)
    
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- NAVEGACIÓN POR JORNADA ---
    if 'matchday' in df_info.columns:
        available_matchdays = sorted(df_info['matchday'].unique())
    else:
        available_matchdays = [1]

    if 'current_md_index' not in st.session_state:
        st.session_state.current_md_index = 0
    
    md_idx = max(0, min(st.session_state.current_md_index, len(available_matchdays) - 1))
    current_matchday = available_matchdays[md_idx]
    
    matches_mask = df_info['matchday'] == current_matchday
    current_matches = df_info[matches_mask]

    # Botones
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

    # --- RENDERIZADO VISUAL ---
    for local_idx, row in current_matches.iterrows():
        pred = predictions[local_idx]
        prob = probs[local_idx] # [Prob_1, Prob_X, Prob_2]
        
        # Calcular porcentajes para la visualización
        p1 = prob[0] * 100
        pX = prob[1] * 100
        p2 = prob[2] * 100
        
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        # HTML Block
        st.markdown(f"""
        <div class="match-card">
            <div style="text-align:center; color:#aaa; font-size:0.85em; margin-bottom:8px;">
                {row['date_str']}
            </div>
            
            <div class="team-row">
                <div style="flex:1; text-align:right; font-weight:bold; font-size:1.2em;">{row['home_team']}</div>
                <div class="vs">vs</div>
                <div style="flex:1; text-align:left; font-weight:bold; font-size:1.2em;">{row['away_team']}</div>
            </div>
            
            <div style="display:flex; justify-content:center; align-items:center; gap:10px; margin-bottom:10px;">
                <span style="font-size:0.9em;">Predicción:</span>
                <div class="pred-badge {color_class}">{winner_code}</div>
                <span style="font-size:0.8em; color:#ccc;">(Confianza: {confidence:.0f}%)</span>
            </div>
            
            <div class="prob-container">
                <div class="prob-segment" style="width:{p1}%; background-color:#4CAF50;" title="Local: {p1:.1f}%"></div>
                <div class="prob-segment" style="width:{pX}%; background-color:#FFC107;" title="Empate: {pX:.1f}%"></div>
                <div class="prob-segment" style="width:{p2}%; background-color:#F44336;" title="Visitante: {p2:.1f}%"></div>
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