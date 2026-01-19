import pandas as pd
import numpy as np
from datetime import timedelta, datetime
import os
from typing import Dict, List, Tuple

# --- 1. CONFIGURACIÓN Y MAPEO ---

# Diccionario maestro de normalización
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

def normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de los equipos."""
    df['home_team'] = df['home_team'].replace(TEAM_MAPPING).str.strip()
    df['away_team'] = df['away_team'].replace(TEAM_MAPPING).str.strip()
    return df

# --- 2. LÓGICA DE ESTADÍSTICAS (CORE - NO TOCAR) ---

def get_team_stats_history(df: pd.DataFrame) -> pd.DataFrame:
    home_matches = df[['date', 'home_team', 'home_score', 'away_score', 'winner']].copy()
    home_matches.columns = ['date', 'team', 'goals_for', 'goals_against', 'winner_ref']
    home_matches['is_home'] = 1
    
    away_matches = df[['date', 'away_team', 'home_score', 'away_score', 'winner']].copy()
    away_matches.columns = ['date', 'team', 'goals_against', 'goals_for', 'winner_ref']
    away_matches['is_home'] = 0
    
    team_stats = pd.concat([home_matches, away_matches]).sort_values(['team', 'date'])
    
    conditions = [
        (team_stats['is_home'] == 1) & (team_stats['winner_ref'] == 'Home'),
        (team_stats['is_home'] == 0) & (team_stats['winner_ref'] == 'Away'),
        (team_stats['winner_ref'] == 'Draw')
    ]
    team_stats['points'] = np.select(conditions, [3, 3, 1], default=0)
    
    team_stats['last_5_points'] = team_stats.groupby('team')['points'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    ).fillna(0)
    
    team_stats['date'] = pd.to_datetime(team_stats['date'])
    team_stats['prev_date'] = team_stats.groupby('team')['date'].shift(1)
    team_stats['rest_days'] = (team_stats['date'] - team_stats['prev_date']).dt.days
    team_stats['rest_days'] = team_stats['rest_days'].fillna(7)
    
    return team_stats

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

def prepare_data(raw_csv_path: str = "data/laliga_results_raw.csv") -> pd.DataFrame:
    try:
        if not os.path.exists(raw_csv_path): return pd.DataFrame()
        df = pd.read_csv(raw_csv_path)
        
        df['home_team'] = df['home_team'].str.strip()
        df['away_team'] = df['away_team'].str.strip()
        df.drop_duplicates(subset=['date', 'home_team', 'away_team'], keep='last', inplace=True)
        
        df['date'] = pd.to_datetime(df['date'])
        df = normalize_names(df)
        
        conditions = [(df['home_score'] > df['away_score']), (df['home_score'] == df['away_score']), (df['home_score'] < df['away_score'])]
        df['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        df['TARGET'] = np.select(conditions, [0, 1, 2], default=1)
        
        team_stats = get_team_stats_history(df)
        
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], left_on=['date', 'home_team'], right_on=['date', 'team'], how='left').rename(columns={'last_5_points': 'last_5_home_points', 'rest_days': 'rest_days_home'}).drop(columns=['team'])
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], left_on=['date', 'away_team'], right_on=['date', 'team'], how='left').rename(columns={'last_5_points': 'last_5_away_points', 'rest_days': 'rest_days_away'}).drop(columns=['team'])
        
        df['h2h_home_wins'] = df.apply(lambda x: calculate_h2h(x, df), axis=1)
        df.dropna(subset=['last_5_home_points', 'last_5_away_points'], inplace=True)
        
        return df[['date', 'home_team', 'away_team', 'last_5_home_points', 'last_5_away_points', 'rest_days_home', 'rest_days_away', 'h2h_home_wins', 'TARGET']]
    except: return pd.DataFrame()

# --- 4. PREPARACIÓN QUINIELA (API INTEGRATION) ---

def prepare_upcoming_matches(fixtures_path: str, training_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Lee el CSV generado por la API (que ya tiene matchday y fechas limpias)."""
    try:
        if not os.path.exists(fixtures_path): return pd.DataFrame(), pd.DataFrame()
        
        # Leemos el CSV de la API (ya viene limpio gracias a api_client.py)
        df_fix = pd.read_csv(fixtures_path) 
        if df_fix.empty: return pd.DataFrame(), pd.DataFrame()

        # Ordenamos por Jornada y luego Fecha
        if 'matchday' in df_fix.columns:
            df_fix = df_fix.sort_values(['matchday', 'date_str'])
        
        # Historial para stats
        if not os.path.exists(training_path): return pd.DataFrame(), df_fix
        df_hist = pd.read_csv(training_path)
        df_hist = normalize_names(df_hist)
        df_hist['date'] = pd.to_datetime(df_hist['date'])
        
        conditions = [(df_hist['home_score'] > df_hist['away_score']), (df_hist['home_score'] == df_hist['away_score']), (df_hist['home_score'] < df_hist['away_score'])]
        df_hist['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        
        stats = get_team_stats_history(df_hist)
        latest_stats = stats.sort_values('date').groupby('team').tail(1).set_index('team')
        
        data_for_pred = []
        valid_fixtures = []

        for _, row in df_fix.iterrows():
            ht, at = row['home_team'], row['away_team']
            
            # Cruzamos datos solo si tenemos historial
            if ht in latest_stats.index and at in latest_stats.index:
                data_for_pred.append({
                    'last_5_home_points': latest_stats.loc[ht, 'last_5_points'],
                    'last_5_away_points': latest_stats.loc[at, 'last_5_points'],
                    'rest_days_home': 7,
                    'rest_days_away': 7,
                    'h2h_home_wins': 0
                })
                valid_fixtures.append(row)
        
        return pd.DataFrame(data_for_pred), pd.DataFrame(valid_fixtures)
    except Exception as e:
        print(f"Error fixtures: {e}")
        return pd.DataFrame(), pd.DataFrame()

if __name__ == "__main__":
    prepare_data()