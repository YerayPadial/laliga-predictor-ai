import pandas as pd
import numpy as np
from datetime import timedelta
import os
from typing import Dict, List, Tuple

# [cite_start]Definición de Mapeo para normalizar nombres (Según tu estrategia) [cite: 1]
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
    "Real Madrid 2": "Real Madrid",
    "R. Madrid": "Real Madrid",
    "Real Oviedo 2": "Real Oviedo",
    "Girona FC": "Girona",
    "Getafe 2": "Getafe",
    # Añadir más según se detecten en el scraper
}

def normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de los equipos usando el diccionario maestro."""
    df['home_team'] = df['home_team'].replace(TEAM_MAPPING).str.strip()
    df['away_team'] = df['away_team'].replace(TEAM_MAPPING).str.strip()
    return df

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
    conditions = [
        (team_stats['is_home'] == 1) & (team_stats['winner_ref'] == 'Home'),
        (team_stats['is_home'] == 0) & (team_stats['winner_ref'] == 'Away'),
        (team_stats['winner_ref'] == 'Draw')
    ]
    team_stats['points'] = np.select(conditions, [3, 3, 1], default=0)
    
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
    Función MAESTRA (Versión 2.0 - Anti-Duplicados).
    """
    try:
        df = pd.read_csv(raw_csv_path)
        
        # --- LIMPIEZA CRÍTICA ---
        # 1. Eliminar espacios en blanco invisibles
        df['home_team'] = df['home_team'].str.strip()
        df['away_team'] = df['away_team'].str.strip()
        
        # 2. Eliminar duplicados EXACTOS (Mismo partido scrapeado N veces)
        # Nos quedamos con el último registro encontrado (keep='last')
        before = len(df)
        df.drop_duplicates(subset=['date', 'home_team', 'away_team'], keep='last', inplace=True)
        print(f"Limpieza: Se eliminaron {before - len(df)} filas duplicadas.")
        # ------------------------

        df['date'] = pd.to_datetime(df['date'])
        
        # 0. Normalización
        df = normalize_names(df)
        
        # 1. Definir Target
        conditions = [
            (df['home_score'] > df['away_score']),
            (df['home_score'] == df['away_score']),
            (df['home_score'] < df['away_score'])
        ]
        
        # TYPE SAFETY: Definimos defaults explícitos para evitar errores de NumPy
        df['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        df['TARGET'] = np.select(conditions, [0, 1, 2], default=1)
        
        # 2. Calcular Features (Rachas)
        team_stats = get_team_stats_history(df)
        
        # 3. Mapear de vuelta (Joins)
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], 
                      left_on=['date', 'home_team'], 
                      right_on=['date', 'team'], 
                      how='left').rename(columns={
                          'last_5_points': 'last_5_home_points', 
                          'rest_days': 'rest_days_home'
                      }).drop(columns=['team'])
                      
        df = df.merge(team_stats[['date', 'team', 'last_5_points', 'rest_days']], 
                      left_on=['date', 'away_team'], 
                      right_on=['date', 'team'], 
                      how='left').rename(columns={
                          'last_5_points': 'last_5_away_points', 
                          'rest_days': 'rest_days_away'
                      }).drop(columns=['team'])
        
        # 4. H2H (Mantenemos tu lógica avanzada para el entrenamiento)
        df['h2h_home_wins'] = df.apply(lambda x: calculate_h2h(x, df), axis=1)

        # 5. Drop NaNs
        df.dropna(subset=['last_5_home_points', 'last_5_away_points'], inplace=True)
        
        # Selección final
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

def prepare_upcoming_matches(fixtures_path: str, training_path: str) -> pd.DataFrame:
    """
    Prepara la Quiniela cruzando el calendario con los datos históricos.
    Calcula las estadísticas más recientes conocidas para proyectar el futuro.
    """
    try:
        # 1. Cargar Calendario (Fixtures)
        if not os.path.exists(fixtures_path):
            print("No se encontró archivo de fixtures.") 
            return pd.DataFrame(), pd.DataFrame()
            
        df_fix = pd.read_csv(fixtures_path)
        df_fix = normalize_names(df_fix)
        # Limpieza de duplicados en el calendario también
        df_fix = df_fix.drop_duplicates(subset=['home_team', 'away_team']) 

        # 2. Cargar Historial (RAW Data) para sacar stats actuales
        if not os.path.exists(training_path): 
            return pd.DataFrame(), df_fix # Devuelve solo info básica si no hay historia
            
        df_hist = pd.read_csv(training_path)
        df_hist = normalize_names(df_hist)
        df_hist['date'] = pd.to_datetime(df_hist['date'])
        
        # Calcular Target en el histórico para poder usar get_team_stats_history
        conditions = [
            (df_hist['home_score'] > df_hist['away_score']),
            (df_hist['home_score'] == df_hist['away_score']),
            (df_hist['home_score'] < df_hist['away_score'])
        ]
        df_hist['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        
        # Calcular últimas estadísticas conocidas
        stats = get_team_stats_history(df_hist)
        # Nos quedamos con la ÚLTIMA fila de cada equipo (su estado actual)
        latest_stats = stats.sort_values('date').groupby('team').tail(1).set_index('team')
        
        # 3. Cruzar datos
        data_for_pred = []
        valid_fixtures = []

        for _, row in df_fix.iterrows():
            ht, at = row['home_team'], row['away_team']
            
            # Si tenemos datos históricos de ambos equipos
            if ht in latest_stats.index and at in latest_stats.index:
                row_data = {
                    'last_5_home_points': latest_stats.loc[ht, 'last_5_points'],
                    'last_5_away_points': latest_stats.loc[at, 'last_5_points'],
                    'rest_days_home': 7, # Default para futuro
                    'rest_days_away': 7,
                    'h2h_home_wins': 0 # Simplificación para predicción rápida (se podría mejorar cruzando historia)
                }
                data_for_pred.append(row_data)
                valid_fixtures.append(row)
        
        # Devolver DF con features para el modelo y DF con info del partido para visualizar
        return pd.DataFrame(data_for_pred), pd.DataFrame(valid_fixtures)

    except Exception as e:
        print(f"Error preparing fixtures: {e}")
        return pd.DataFrame(), pd.DataFrame()

if __name__ == "__main__":
    # Prueba rápida local
    df_clean = prepare_data()
    if not df_clean.empty:
        print(df_clean.head())
        df_clean.to_csv("data/training_set.csv", index=False)