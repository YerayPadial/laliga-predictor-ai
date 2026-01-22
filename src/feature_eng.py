import pandas as pd
import numpy as np
from datetime import timedelta, datetime
import os
from typing import Dict, List, Tuple

# --- 1. CONFIGURACIÓN Y MAPEO ---

# mapeo de nombres para asegurar que coincidan con los recopilados y usados para el entrenamiento (consistencia)
TEAM_MAPPING = {
    "Athletic Club": "Athletic Bilbao", "Athletic": "Athletic Bilbao",
    "Atlético de Madrid": "Atletico Madrid", "Atl. Madrid": "Atletico Madrid",
    "R. Betis": "Real Betis",
    "Real Sociedad": "Real Sociedad", "R. Sociedad": "Real Sociedad",
    "FC Barcelona": "Barcelona", "Barca": "Barcelona",
    "Real Madrid": "Real Madrid",
    "Real Oviedo 2": "Real Oviedo", "Oviedo": "Real Oviedo",
    "Girona FC": "Girona", "Girona": "Girona",
    "Getafe 2": "Getafe",
    "Celta": "Celta de Vigo", "RC Celta": "Celta de Vigo",
    "Alavés": "Alaves", "D. Alavés": "Alaves", 
    "Leganés": "Leganes", "CD Leganés": "Leganes",
    "Valladolid": "Real Valladolid", "R. Valladolid": "Real Valladolid",
    "Sevilla": "Sevilla", "Sevilla FC": "Sevilla",
    "Valencia": "Valencia", "Valencia CF": "Valencia",
    "Villarreal": "Villarreal", "Villarreal CF": "Villarreal",
    "Mallorca": "Mallorca", "RCD Mallorca": "Mallorca",
    "Osasuna": "Osasuna", "CA Osasuna": "Osasuna",
    "Las Palmas": "Las Palmas", "UD Las Palmas": "Las Palmas",
    "Rayo": "Rayo Vallecano", "Rayo Vallecano": "Rayo Vallecano",
    "Espanyol": "Espanyol", "RCD Espanyol": "Espanyol",
    "Elche CF": "Elche",
    "Levante UD": "Levante",
}

# asegura que los nombres esten normalizados sin espacios extra u otros caracteres
def normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de los equipos."""
    df['home_team'] = df['home_team'].replace(TEAM_MAPPING).str.strip()
    df['away_team'] = df['away_team'].replace(TEAM_MAPPING).str.strip()
    return df

# --- 2. LÓGICA DE ESTADÍSTICAS  ---

# obtiene estadisticas historicas por equipo
# calcula puntos en ultimos 5 partidos y dias de descanso
def get_team_stats_history(df: pd.DataFrame) -> pd.DataFrame:
    home_matches = df[['date', 'home_team', 'home_score', 'away_score', 'winner']].copy()
    home_matches.columns = ['date', 'team', 'goals_for', 'goals_against', 'winner_ref']
    home_matches['is_home'] = 1
    
    away_matches = df[['date', 'away_team', 'home_score', 'away_score', 'winner']].copy()
    away_matches.columns = ['date', 'team', 'goals_against', 'goals_for', 'winner_ref']
    away_matches['is_home'] = 0
    
    # combino ambos dataframes para tener todos los partidos por equipo
    team_stats = pd.concat([home_matches, away_matches]).sort_values(['team', 'date'])
    
    # calculo puntos segun resultados
    conditions = [
        (team_stats['is_home'] == 1) & (team_stats['winner_ref'] == 'Home'),
        (team_stats['is_home'] == 0) & (team_stats['winner_ref'] == 'Away'),
        (team_stats['winner_ref'] == 'Draw')
    ]
    team_stats['points'] = np.select(conditions, [3, 3, 1], default=0) # 3 pts win, 1 pt draw, 0 pts loss
    
    # calculo puntos de los ultimo 5 partidos con shift para no incluir el partido actual
    team_stats['last_5_points'] = team_stats.groupby('team')['points'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    ).fillna(0)
    
    # calculo partidos de descanso entre partidos
    team_stats['date'] = pd.to_datetime(team_stats['date'])
    team_stats['prev_date'] = team_stats.groupby('team')['date'].shift(1)
    team_stats['rest_days'] = (team_stats['date'] - team_stats['prev_date']).dt.days
    team_stats['rest_days'] = team_stats['rest_days'].fillna(7)
    
    return team_stats

# calculo victorias del local contra ese equipo directamente en los ultimos 3 años
def calculate_h2h(row, df_history):
    try:
        date_limit = row['date'] - timedelta(days=3*365)
        past_matches = df_history[
            (df_history['date'] < row['date']) & 
            (df_history['date'] >= date_limit) &
            (df_history['home_team'] == row['home_team']) & 
            (df_history['away_team'] == row['away_team'])
        ]
        if past_matches.empty: return 0
        return past_matches[past_matches['winner'] == 'Home'].shape[0]
    except: return 0

# --- 3. ENTRENAMIENTO ---

# f. que prepara los datos para el entrenamiento del modelo
def prepare_data(raw_csv_path: str = "data/laliga_results_raw.csv") -> pd.DataFrame:
    try:
        if not os.path.exists(raw_csv_path): return pd.DataFrame() # si no existe el archivo, retorno vacio
        df = pd.read_csv(raw_csv_path)
        
        # limpio espacios extra y duplicados
        df['home_team'] = df['home_team'].str.strip() 
        df['away_team'] = df['away_team'].str.strip()
        df.drop_duplicates(subset=['date', 'home_team', 'away_team'], keep='last', inplace=True)
        
        df['date'] = pd.to_datetime(df['date']) # aseguro formato de fecha
        df = normalize_names(df)
        
        # defino el ganador y la variable objetivo que es 0: Home, 1: Draw, 2: Away
        conditions = [(df['home_score'] > df['away_score']), (df['home_score'] == df['away_score']), (df['home_score'] < df['away_score'])]
        df['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        df['TARGET'] = np.select(conditions, [0, 1, 2], default=1)
        
        # obtengo el historico de estadisticas por equipo
        team_stats = get_team_stats_history(df)
        
        # uno las estadisticas de ambos equipos al dataframe principal
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], left_on=['date', 'home_team'], right_on=['date', 'team'], how='left').rename(columns={'last_5_points': 'last_5_home_points', 'rest_days': 'rest_days_home'}).drop(columns=['team'])
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], left_on=['date', 'away_team'], right_on=['date', 'team'], how='left').rename(columns={'last_5_points': 'last_5_away_points', 'rest_days': 'rest_days_away'}).drop(columns=['team'])
        
        # calculo enfrentamientos directos
        df['h2h_home_wins'] = df.apply(lambda x: calculate_h2h(x, df), axis=1)
        df.dropna(subset=['last_5_home_points', 'last_5_away_points'], inplace=True) # elimino filas con datos faltantes
        
        return df[['date', 'home_team', 'away_team', 'last_5_home_points', 'last_5_away_points', 'rest_days_home', 'rest_days_away', 'h2h_home_wins', 'TARGET']]
    except: return pd.DataFrame()

# --- 4. PREPARACIÓN QUINIELA (API INTEGRATION) ---

# Prepara los datos para predecir. Toma el calendario futuro (del api_client) y le pega las estadísticas actuales de los equipos para que el modelo pueda opinar sobre esos partidos
def prepare_upcoming_matches(fixtures_path: str, training_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    try:
        if not os.path.exists(fixtures_path): return pd.DataFrame(), pd.DataFrame()
        
        df_fix = pd.read_csv(fixtures_path) 
        if df_fix.empty: return pd.DataFrame(), pd.DataFrame()

        # Ordenar por Jornada y Fecha ISO
        if 'utc_date' in df_fix.columns:
            df_fix = df_fix.sort_values(['matchday', 'utc_date'])
        
        # Historial de partidos jugados para obtener estadistcas
        if not os.path.exists(training_path): return pd.DataFrame(), df_fix
        df_hist = pd.read_csv(training_path)
        df_hist = normalize_names(df_hist)
        df_hist['date'] = pd.to_datetime(df_hist['date'])
        
        # defino el ganador de el historial
        conditions = [(df_hist['home_score'] > df_hist['away_score']), (df_hist['home_score'] == df_hist['away_score']), (df_hist['home_score'] < df_hist['away_score'])]
        df_hist['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
    
        stats = get_team_stats_history(df_hist)
        latest_stats = stats.sort_values('date').groupby('team').tail(1).set_index('team') # ultimas stats de cada team
        
        data_for_pred = []
        valid_fixtures = []

        # recorro cada partido del calendario futuro y le pego las stats actuales
        for _, row in df_fix.iterrows():
            ht, at = row['home_team'], row['away_team']
            if ht in latest_stats.index and at in latest_stats.index:
                data_for_pred.append({
                    'last_5_home_points': latest_stats.loc[ht, 'last_5_points'],
                    'last_5_away_points': latest_stats.loc[at, 'last_5_points'],
                    'rest_days_home': 7,
                    'rest_days_away': 7,
                    'h2h_home_wins': 0
                })
                valid_fixtures.append(row) # guardo solo los partidos que tienen stats disponibles
        
        return pd.DataFrame(data_for_pred), pd.DataFrame(valid_fixtures)
    except Exception as e:
        print(f"Error fixtures: {e}")
        return pd.DataFrame(), pd.DataFrame()

if __name__ == "__main__":
    prepare_data()