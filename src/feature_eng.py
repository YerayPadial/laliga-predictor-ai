import pandas as pd
import numpy as np
from datetime import timedelta
from typing import Dict, List, Tuple

# Definición de Mapeo para normalizar nombres (Según tu estrategia) [cite: 1]
TEAM_MAPPING = {
    "Athletic Club": "Athletic Bilbao",
    "Athletic": "Athletic Bilbao",
    "Atlético de Madrid": "Atletico Madrid",
    "Atl. Madrid": "Atletico Madrid",
    "R. Betis": "Real Betis",
    "Real Sociedad": "Real Sociedad",
    "R. Sociedad": "Real Sociedad",
    "FC Barcelona": "Barcelona",
    "Barca": "Barcelona",
    "Real Madrid": "Real Madrid",
    "R. Madrid": "Real Madrid",
    # Añadir más según se detecten en el scraper
}

def normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de los equipos usando el diccionario maestro."""
    df['home_team'] = df['home_team'].replace(TEAM_MAPPING)
    df['away_team'] = df['away_team'].replace(TEAM_MAPPING)
    return df

def calculate_points(row, team_column):
    """Auxiliar: Calcula puntos obtenidos en un partido (3, 1, 0)."""
    if row['winner'] == 'Draw':
        return 1
    if row['winner'] == 'Home' and row['home_team'] == row[team_column]:
        return 3
    if row['winner'] == 'Away' and row['away_team'] == row[team_column]:
        return 3
    return 0

def get_team_stats_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Desglosa el DataFrame de partidos en una línea de tiempo por equipo
    para calcular rachas y fatiga.
    """
    # Crear dos entradas por partido: una desde la perspectiva local, otra visitante
    home_matches = df[['date', 'home_team', 'home_score', 'away_score', 'winner']].copy()
    home_matches.columns = ['date', 'team', 'goals_for', 'goals_against', 'winner_ref']
    home_matches['is_home'] = 1
    
    away_matches = df[['date', 'away_team', 'home_score', 'away_score', 'winner']].copy()
    away_matches.columns = ['date', 'team', 'goals_against', 'goals_for', 'winner_ref'] # Note goals reversed
    away_matches['is_home'] = 0
    
    team_stats = pd.concat([home_matches, away_matches]).sort_values(['team', 'date'])
    
    # Calcular puntos por partido
    # Lógica simplificada para vectorización
    conditions = [
        (team_stats['is_home'] == 1) & (team_stats['winner_ref'] == 'Home'),
        (team_stats['is_home'] == 0) & (team_stats['winner_ref'] == 'Away'),
        (team_stats['winner_ref'] == 'Draw')
    ]
    choices = [3, 3, 1]
    team_stats['points'] = np.select(conditions, choices, default=0)
    
    # --- INGENIERÍA DE CARACTERÍSTICAS ---
    
    # 1. Racha de puntos (Últimos 5 partidos) 
    # Shift(1) es VITAL: No podemos usar los puntos del partido de HOY para predecir HOY.
    team_stats['last_5_points'] = team_stats.groupby('team')['points'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    ).fillna(0)
    
    # 2. Días de descanso (Fatiga) 
    team_stats['date'] = pd.to_datetime(team_stats['date'])
    team_stats['prev_date'] = team_stats.groupby('team')['date'].shift(1)
    team_stats['rest_days'] = (team_stats['date'] - team_stats['prev_date']).dt.days
    team_stats['rest_days'] = team_stats['rest_days'].fillna(7) # Default 7 días si es primer partido
    
    return team_stats

def calculate_h2h(row, df_history):
    """
    Calcula victorias directas del equipo local sobre el visitante 
    en los últimos 3 años ANTES de la fecha actual.
    """
    date_limit = row['date'] - timedelta(days=3*365)
    
    # Filtrar historia previa
    past_matches = df_history[
        (df_history['date'] < row['date']) & 
        (df_history['date'] >= date_limit) &
        (df_history['home_team'] == row['home_team']) & 
        (df_history['away_team'] == row['away_team'])
    ]
    
    if past_matches.empty:
        return 0
        
    # Contar cuántas veces ganó el local
    home_wins = past_matches[past_matches['winner'] == 'Home'].shape[0]
    return home_wins

def prepare_data(raw_csv_path: str = "data/laliga_results_raw.csv") -> pd.DataFrame:
    """
    Función MAESTRA.
    Lee CSV crudo -> Limpia -> Genera Features -> Devuelve DF listo para ML.
    """
    try:
        df = pd.read_csv(raw_csv_path)
        df['date'] = pd.to_datetime(df['date'])
        
        # 0. Normalización
        df = normalize_names(df)
        
        # 1. Definir Target (Variable Objetivo)
        # 0: Local Gana, 1: Empate, 2: Visitante Gana
        conditions = [
            (df['home_score'] > df['away_score']),
            (df['home_score'] == df['away_score']),
            (df['home_score'] < df['away_score'])
        ]
        
        # --- CORRECCIÓN AQUÍ ---
        # Añadimos default='Draw' para que NumPy sepa que todo son Strings
        df['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        
        # Añadimos default=1 para que NumPy sepa que todo son Enteros
        df['TARGET'] = np.select(conditions, [0, 1, 2], default=1)
        # -----------------------
        
        # 2. Calcular Features de Racha y Fatiga (Team-Centric)
        team_stats = get_team_stats_history(df)
        
        # 3. Mapear de vuelta al DataFrame de Partidos (Match-Centric)
        # Join para Home Team
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], 
                      left_on=['date', 'home_team'], 
                      right_on=['date', 'team'], 
                      how='left').rename(columns={
                          'last_5_points': 'last_5_home_points', 
                          'rest_days': 'rest_days_home'
                      }).drop(columns=['team'])
                      
        # Join para Away Team
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], 
                      left_on=['date', 'away_team'], 
                      right_on=['date', 'team'], 
                      how='left').rename(columns={
                          'last_5_points': 'last_5_away_points', 
                          'rest_days': 'rest_days_away'
                      }).drop(columns=['team'])
        
        # 4. Calcular H2H (Loop optimizado o Apply)
        df['h2h_home_wins'] = df.apply(lambda x: calculate_h2h(x, df), axis=1)

        # 5. Limpieza Final (Handling NaNs)
        df.dropna(subset=['last_5_home_points', 'last_5_away_points'], inplace=True)
        
        # Selección de columnas finales según Schema
        final_cols = [
            'date', 'home_team', 'away_team', 
            'last_5_home_points', 'last_5_away_points',
            'rest_days_home', 'rest_days_away',
            'h2h_home_wins',
            'TARGET'
        ]
        
        print(f"Data Engineering Completado. Dataset shape: {df[final_cols].shape}")
        return df[final_cols]

    except FileNotFoundError:
        print("Error: No se encontró el archivo de datos crudos.")
        return pd.DataFrame()
    
if __name__ == "__main__":
    # Prueba rápida
    df_clean = prepare_data()
    print(df_clean.head())
    # Guardar para inspección
    if not df_clean.empty:
        df_clean.to_csv("data/training_set.csv", index=False)