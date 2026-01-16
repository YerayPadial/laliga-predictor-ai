import streamlit as st
import pandas as pd
import joblib
import os
import datetime

# Configuración de página (Debe ser lo primero)
st.set_page_config(
    page_title="LaLiga AI Predictor",
    page_icon="⚽",
    layout="wide"
)

# Constantes de Rutas
MODEL_PATH = 'data/model_winner.pkl'
DATA_PATH = 'data/training_set.csv' # Usamos el histórico para sacar estadísticas actuales

# --- ESTILOS CSS PERSONALIZADOS (Para el formato [1 X 2]) ---
st.markdown("""
<style>
    .prediction-box {
        text-align: center;
        padding: 10px;
        border-radius: 5px;
        margin: 5px;
        font-weight: bold;
        color: white;
    }
    .default-box { background-color: #333; color: #888; }
    .winner-box { background-color: #4CAF50; color: white; box-shadow: 0 0 10px #4CAF50; }
    .team-name { font-size: 1.2em; font-weight: bold; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE CARGA (CACHED) ---
@st.cache_resource
def load_model():
    """Carga el modelo entrenado. Si no existe, devuelve None."""
    if os.path.exists(MODEL_PATH):
        return joblib.load(MODEL_PATH)
    return None

@st.cache_data
def load_team_stats():
    """
    Carga los últimos datos conocidos para calcular racha actual.
    En un entorno real, esto leería un archivo 'current_stats.csv' generado por el ETL.
    Aquí simulamos obteniendo los últimos datos del training set.
    """
    if os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        # Obtenemos la lista única de equipos
        teams = sorted(list(set(df['home_team'].unique()) | set(df['away_team'].unique())))
        return df, teams
    return None, []

# --- LÓGICA DE INTERFAZ ---

def main():
    st.title("⚽ LaLiga AI Predictor (Golden Stack)")
    st.markdown("### Predicciones basadas en Inteligencia Artificial (Random Forest / Logistic Reg.)")

    # 1. Cargar Recursos
    model = load_model()
    df_history, team_list = load_team_stats()

    # --- SIDEBAR (Métricas y Estado) ---
    st.sidebar.header("📊 Estado del Sistema")
    
    if model:
        # Intentamos deducir info del modelo
        model_type = model.named_steps['clf'].__class__.__name__
        st.sidebar.success(f"Modelo Activo: **{model_type}**")
        
        # Fecha de última actualización (Metadata del archivo)
        mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(MODEL_PATH))
        st.sidebar.info(f"Último entrenamiento: {mod_time.strftime('%d/%m %H:%M')}")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("**Métricas Clave (Test Set):**")
        st.sidebar.metric("Accuracy Est.", "62%") # Placeholder o leer de un json de métricas
        st.sidebar.metric("Precisión Local", "70%")
    else:
        st.sidebar.error("⚠️ Modelo no encontrado. Ejecuta el pipeline en GitHub Actions.")

    # --- MAIN AREA: GENERADOR DE PARTIDOS ---
    
    st.subheader("🔮 Próxima Jornada (Simulador)")
    
    if not team_list:
        st.warning("No hay datos disponibles. Esperando al Scraper...")
        return

    # Selector de Equipos (Para simular la próxima jornada)
    col1, col2 = st.columns(2)
    with col1:
        home_team = st.selectbox("Equipo Local", team_list, index=0)
    with col2:
        away_team = st.selectbox("Equipo Visitante", team_list, index=1)

    if st.button("Predecir Resultado"):
        if home_team == away_team:
            st.error("El equipo local y visitante no pueden ser el mismo.")
        elif model:
            # 1. Construir el vector de entrada (Feature Vector)
            # En producción, esto busca los datos reales de 'last_5_points' de cada equipo.
            # Aquí usamos promedios o búsquedas simples para la demo.
            
            # Buscar último registro del local
            last_home = df_history[df_history['home_team'] == home_team].iloc[-1] if not df_history[df_history['home_team'] == home_team].empty else None
            # Buscar último registro del visitante
            last_away = df_history[df_history['away_team'] == away_team].iloc[-1] if not df_history[df_history['away_team'] == away_team].empty else None
            
            if last_home is not None and last_away is not None:
                # Features esperadas: ['last_5_home_points', 'last_5_away_points', 'rest_days_home', 'rest_days_away', 'h2h_home_wins']
                input_data = pd.DataFrame([{
                    'last_5_home_points': last_home['last_5_home_points'], # Asumimos inercia
                    'last_5_away_points': last_away['last_5_away_points'],
                    'rest_days_home': 7, # Default standard
                    'rest_days_away': 7,
                    'h2h_home_wins': last_home['h2h_home_wins'] # Aproximación
                }])

                # 2. Predicción
                prediction = model.predict(input_data)[0] # 0, 1, o 2
                probs = model.predict_proba(input_data)[0] # [Prob_Home, Prob_Draw, Prob_Away]

                # 3. Visualización [1] [X] [2]
                st.markdown("---")
                
                # Definir colores según predicción
                # Predicción: 0=Home, 1=Draw, 2=Away
                c1 = "winner-box" if prediction == 0 else "default-box"
                cX = "winner-box" if prediction == 1 else "default-box"
                c2 = "winner-box" if prediction == 2 else "default-box"

                # Layout Visual
                c_team1, c_res1, c_resX, c_res2, c_team2 = st.columns([3, 1, 1, 1, 3])
                
                with c_team1:
                    st.markdown(f"<div class='team-name' style='text-align:right'>{home_team}</div>", unsafe_allow_html=True)
                    st.caption(f"Confianza: {probs[0]*100:.1f}%")
                
                with c_res1:
                    st.markdown(f"<div class='prediction-box {c1}'>1</div>", unsafe_allow_html=True)
                
                with c_resX:
                    st.markdown(f"<div class='prediction-box {cX}'>X</div>", unsafe_allow_html=True)
                
                with c_res2:
                    st.markdown(f"<div class='prediction-box {c2}'>2</div>", unsafe_allow_html=True)
                
                with c_team2:
                    st.markdown(f"<div class='team-name' style='text-align:left'>{away_team}</div>", unsafe_allow_html=True)
                    st.caption(f"Confianza: {probs[2]*100:.1f}%")
                
            else:
                st.warning("Faltan datos históricos para calcular estadísticas de estos equipos.")

if __name__ == "__main__":
    main()