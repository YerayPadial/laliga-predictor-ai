import streamlit as st
import pandas as pd
import joblib
import os
from src.feature_eng import prepare_upcoming_matches

# Configuración Inicial
st.set_page_config(page_title="La Quiniela AI", page_icon="⚽", layout="centered")

# --- ESTILOS CSS (DISEÑO) ---
st.markdown("""
<style>
    /* Estilo de la Tarjeta */
    .match-card {
        background-color: #262730;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 16px;
        border: 1px solid #444;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    
    /* Fila de Equipos */
    .team-row { 
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        margin-bottom: 15px; 
        font-size: 1.1em;
    }
    .vs { 
        font-weight: bold; 
        color: #888; 
        padding: 0 15px; 
        font-size: 0.9em;
    }
    
    /* Badges de Predicción (1 X 2) */
    .pred-badge {
        font-weight: bold; 
        padding: 6px 14px; 
        border-radius: 6px; 
        color: white; 
        text-align: center; 
        min-width: 45px; 
        display: inline-block;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .pred-1 { background-color: #4CAF50; border: 1px solid #43A047; } /* Verde */
    .pred-X { background-color: #FFC107; color: black !important; border: 1px solid #FFB300; } /* Amarillo */
    .pred-2 { background-color: #F44336; border: 1px solid #E53935; } /* Rojo */
    
    /* Barra de Probabilidad */
    .prob-container { 
        display: flex; 
        margin-top: 15px; 
        height: 10px; 
        border-radius: 5px; 
        overflow: hidden; 
        width: 100%; 
        background-color: #444;
    }
    .prob-segment { height: 100%; transition: width 0.5s ease-in-out; }
    
    /* Etiquetas de Porcentaje */
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

# Tamaño de Jornada
MATCHES_PER_ROUND = 10 

def load_model():
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

def main():
    st.title("⚽ La Quiniela IA")
    
    model = load_model()
    if not model:
        st.error("⚠️ Modelo no encontrado. Esperando re-entrenamiento.")
        return

    # 1. Cargar Datos
    X_pred, df_info = prepare_upcoming_matches(FIXTURES_PATH, RAW_DATA_PATH)

    if X_pred.empty:
        st.info("📅 Calendario actualizado. No hay partidos pendientes descargados.")
        return

    # 2. Resetear índices (Vital para evitar errores)
    df_info = df_info.reset_index(drop=True)
    
    # 3. Predecir
    predictions = model.predict(X_pred)
    probs = model.predict_proba(X_pred)

    # --- LÓGICA DE NAVEGACIÓN (JORNADAS) ---
    if 'matchday' in df_info.columns:
        # Convertimos a int para ordenar numéricamente bien (1, 2, 10 en vez de 1, 10, 2)
        df_info['matchday'] = df_info['matchday'].astype(int)
        available_matchdays = sorted(df_info['matchday'].unique())
    else:
        available_matchdays = [1]

    if 'current_md_index' not in st.session_state:
        st.session_state.current_md_index = 0
    
    # Asegurar rango válido
    md_idx = max(0, min(st.session_state.current_md_index, len(available_matchdays) - 1))
    current_matchday = available_matchdays[md_idx]
    
    # Filtrar partidos de ESTA jornada
    matches_mask = df_info['matchday'] == current_matchday
    current_matches = df_info[matches_mask]

    # --- BOTONERA DE NAVEGACIÓN ---
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

    # --- RENDERIZADO DE TARJETAS ---
    if current_matches.empty:
        st.info("No hay partidos programados para esta jornada.")
    
    for local_idx, row in current_matches.iterrows():
        # Usamos el índice global (local_idx) para buscar la predicción correspondiente
        pred = predictions[local_idx]
        prob = probs[local_idx] # Array [Prob_Local, Prob_Empate, Prob_Visitante]
        
        # Cálculos visuales
        p1 = prob[0] * 100
        pX = prob[1] * 100
        p2 = prob[2] * 100
        
        winner_code = "1" if pred == 0 else ("X" if pred == 1 else "2")
        confidence = max(prob) * 100
        color_class = f"pred-{winner_code}"
        
        # TARJETA HTML COMPLETA
        # El parámetro unsafe_allow_html=True es lo que hace que se vea bonito y no como texto
        st.markdown(f"""
        <div class="match-card">
            <div style="text-align:center; color:#aaa; font-size:0.85em; margin-bottom:12px; font-family:monospace;">
                📅 {row['date_str']}
            </div>
            
            <div class="team-row">
                <div style="flex:1; text-align:right; font-weight:bold; font-size:1.2em;">{row['home_team']}</div>
                <div class="vs">vs</div>
                <div style="flex:1; text-align:left; font-weight:bold; font-size:1.2em;">{row['away_team']}</div>
            </div>
            
            <div style="display:flex; justify-content:center; align-items:center; gap:12px; margin-bottom:12px;">
                <span style="font-size:0.9em; color:#ddd;">Predicción:</span>
                <div class="pred-badge {color_class}">{winner_code}</div>
                <span style="font-size:0.85em; color:#aaa;">(Confianza: {confidence:.0f}%)</span>
            </div>
            
            <div class="prob-container">
                <div class="prob-segment" style="width:{p1}%; background-color:#4CAF50;" title="Victoria Local: {p1:.1f}%"></div>
                <div class="prob-segment" style="width:{pX}%; background-color:#FFC107;" title="Empate: {pX:.1f}%"></div>
                <div class="prob-segment" style="width:{p2}%; background-color:#F44336;" title="Victoria Visitante: {p2:.1f}%"></div>
            </div>
            
            <div class="prob-labels">
                <span style="color:#4CAF50;">1: {p1:.0f}%</span>
                <span style="color:#FFC107;">X: {pX:.0f}%</span>
                <span style="color:#F44336;">2: {p2:.0f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()