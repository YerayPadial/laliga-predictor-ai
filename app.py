import streamlit as st
import pandas as pd
import joblib
import os
from src.feature_eng import prepare_upcoming_matches

st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# CSS para Tarjetas de Quiniela
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
    .pred-1 { background-color: #4CAF50; } /* Verde Local */
    .pred-X { background-color: #FFC107; color: black !important; } /* Amarillo Empate */
    .pred-2 { background-color: #F44336; } /* Rojo Visitante */
    .prob-bar { height: 4px; background-color: #555; margin-top: 5px; border-radius: 2px; }
    .prob-fill { height: 100%; border-radius: 2px; transition: width 0.5s; }
</style>
""", unsafe_allow_html=True)

MODEL_PATH = 'data/model_winner.pkl'
FIXTURES_PATH = 'data/laliga_fixtures.csv'
RAW_DATA_PATH = 'data/laliga_results_raw.csv'

def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

def main():
    st.title("⚽ La Quiniela IA")
    st.caption("Predicciones automatizadas para la próxima jornada")

    model = load_model()
    if not model:
        st.error("⚠️ Modelo no encontrado. Esperando re-entrenamiento.")
        return

    # Cargar y Preparar Partidos
    X_pred, df_info = prepare_upcoming_matches(FIXTURES_PATH, RAW_DATA_PATH)

    if X_pred.empty:
        st.info("📅 No hay partidos programados detectados o faltan datos históricos.")
        st.write("El scraper actualizará el calendario automáticamente el próximo Martes/Viernes.")
        return

    # Realizar Predicciones en Lote
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- INTERFAZ DE QUINIELA ---
    st.subheader(f"Jornada Actual ({len(df_info)} partidos)")

    for i, row in df_info.iterrows():
        home = row['home_team']
        away = row['away_team']
        pred = predictions[i] # 0, 1, 2
        prob = probs[i] # [P_Home, P_Draw, P_Away]
        
        # Formatear
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        
        # Color badge
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
                <span style="font-size:0.8em; color:#ccc;">(Confianza: {confidence:.1f}%)</span>
            </div>
             <div style="display:flex; margin-top:10px; height:6px; border-radius:3px; overflow:hidden;">
                <div style="width:{prob[0]*100}%; background-color:#4CAF50;" title="Local: {prob[0]*100:.1f}%"></div>
                <div style="width:{prob[1]*100}%; background-color:#FFC107;" title="Empate: {prob[1]*100:.1f}%"></div>
                <div style="width:{prob[2]*100}%; background-color:#F44336;" title="Visitante: {prob[2]*100:.1f}%"></div>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:0.7em; color:#888; margin-top:2px;">
                <span>1: {prob[0]*100:.0f}%</span>
                <span>X: {prob[1]*100:.0f}%</span>
                <span>2: {prob[2]*100:.0f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()