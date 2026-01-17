import pandas as pd
import numpy as np
from datetime import timedelta, datetime
import os
from typing import Dict, List, Tuple

# --- 1. CONFIGURACIÓN Y MAPEO ---

# Diccionario maestro de normalización
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
    # Añadir más variaciones si aparecen en el futuro
}

def normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza los nombres de los equipos y elimina espacios invisibles."""
    df['home_team'] = df['home_team'].replace(TEAM_MAPPING).str.strip()
    df['away_team'] = df['away_team'].replace(TEAM_MAPPING).str.strip()
    return df

# --- 2. LÓGICA DE ESTADÍSTICAS (CORE) ---

def get_team_stats_history(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula rachas (últimos 5 partidos) y fatiga (días de descanso)
    basándose en el historial completo.
    """
    # Desglosar partidos en dos filas (Local y Visitante)
    home_matches = df[['date', 'home_team', 'home_score', 'away_score', 'winner']].copy()
    home_matches.columns = ['date', 'team', 'goals_for', 'goals_against', 'winner_ref']
    home_matches['is_home'] = 1
    
    away_matches = df[['date', 'away_team', 'home_score', 'away_score', 'winner']].copy()
    away_matches.columns = ['date', 'team', 'goals_against', 'goals_for', 'winner_ref']
    away_matches['is_home'] = 0
    
    team_stats = pd.concat([home_matches, away_matches]).sort_values(['team', 'date'])
    
    # Calcular puntos (3, 1, 0)
    conditions = [
        (team_stats['is_home'] == 1) & (team_stats['winner_ref'] == 'Home'),
        (team_stats['is_home'] == 0) & (team_stats['winner_ref'] == 'Away'),
        (team_stats['winner_ref'] == 'Draw')
    ]
    team_stats['points'] = np.select(conditions, [3, 3, 1], default=0)
    
    # A. Racha de puntos (Últimos 5 partidos ANTERIORES)
    team_stats['last_5_points'] = team_stats.groupby('team')['points'].transform(
        lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
    ).fillna(0)
    
    # B. Días de descanso (Fatiga)
    team_stats['date'] = pd.to_datetime(team_stats['date'])
    team_stats['prev_date'] = team_stats.groupby('team')['date'].shift(1)
    team_stats['rest_days'] = (team_stats['date'] - team_stats['prev_date']).dt.days
    team_stats['rest_days'] = team_stats['rest_days'].fillna(7) # Default 7 días
    
    return team_stats

def calculate_h2h(row, df_history):
    """
    Calcula cuántas veces el equipo LOCAL ganó a este VISITANTE 
    en los últimos 3 años (Historial directo).
    """
    try:
        date_limit = row['date'] - timedelta(days=3*365)
        
        # Filtrar enfrentamientos previos
        past_matches = df_history[
            (df_history['date'] < row['date']) & 
            (df_history['date'] >= date_limit) &
            (df_history['home_team'] == row['home_team']) & 
            (df_history['away_team'] == row['away_team'])
        ]
        
        if past_matches.empty:
            return 0
            
        # Contar victorias locales
        return past_matches[past_matches['winner'] == 'Home'].shape[0]
    except:
        return 0

# --- 3. PREPARACIÓN DE DATOS (ENTRENAMIENTO) ---

def prepare_data(raw_csv_path: str = "data/laliga_results_raw.csv") -> pd.DataFrame:
    """
    Función MAESTRA para Entrenamiento.
    Lee CSV -> Limpia -> Calcula H2H/Rachas -> Devuelve Dataset listo.
    """
    try:
        if not os.path.exists(raw_csv_path):
            print("Error: No se encontró el archivo de datos crudos.")
            return pd.DataFrame()

        df = pd.read_csv(raw_csv_path)
        
        # 1. Limpieza de duplicados y espacios
        df['home_team'] = df['home_team'].str.strip()
        df['away_team'] = df['away_team'].str.strip()
        df.drop_duplicates(subset=['date', 'home_team', 'away_team'], keep='last', inplace=True)
        
        df['date'] = pd.to_datetime(df['date'])
        df = normalize_names(df)
        
        # 2. Definir Target y Ganador
        conditions = [
            (df['home_score'] > df['away_score']),
            (df['home_score'] == df['away_score']),
            (df['home_score'] < df['away_score'])
        ]
        df['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        df['TARGET'] = np.select(conditions, [0, 1, 2], default=1)
        
        # 3. Calcular Features (Rachas)
        team_stats = get_team_stats_history(df)
        
        # 4. Mapear stats al dataframe principal (Merges)
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
        
        # 5. H2H (Cálculo real para entrenamiento)
        df['h2h_home_wins'] = df.apply(lambda x: calculate_h2h(x, df), axis=1)

        # 6. Limpieza final
        df.dropna(subset=['last_5_home_points', 'last_5_away_points'], inplace=True)
        
        final_cols = [
            'date', 'home_team', 'away_team', 
            'last_5_home_points', 'last_5_away_points',
            'rest_days_home', 'rest_days_away',
            'h2h_home_wins',
            'TARGET'
        ]
        
        print(f"Data Engineering Completado. Dataset shape: {df[final_cols].shape}")
        return df[final_cols]

    except Exception as e:
        print(f"Error en prepare_data: {e}")
        return pd.DataFrame()

# --- 4. PREPARACIÓN DE DATOS (QUINIELA / UX) ---

def parse_flashscore_date(date_str: str) -> datetime:
    """Convierte fechas tipo '17.01. 14:00' (Flashscore) a objetos datetime reales."""
    try:
        if not isinstance(date_str, str): return datetime.now()
        parts = date_str.split('.')
        day = int(parts[0])
        month = int(parts[1])
        current_year = datetime.now().year
        dt = datetime(current_year, month, day)
        if dt < datetime.now() - timedelta(days=90):
            dt = dt.replace(year=current_year + 1)
        return dt
    except:
        return datetime.now()

def prepare_upcoming_matches(fixtures_path: str, training_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Cruza el Calendario con el Historial para generar la Quiniela.
    Devuelve: (X_prediccion, Info_Partidos_con_Fechas)
    """
    try:
        # 1. Cargar Calendario
        if not os.path.exists(fixtures_path):
            print("No se encontró fixtures.csv")
            return pd.DataFrame(), pd.DataFrame()
            
        df_fix = pd.read_csv(fixtures_path)
        df_fix = normalize_names(df_fix)
        df_fix = df_fix.drop_duplicates(subset=['home_team', 'away_team'])
        df_fix['parsed_date'] = df_fix['date_str'].apply(parse_flashscore_date)

        # 2. Cargar Historial para obtener 'Estado de Forma' actual
        if not os.path.exists(training_path):
            return pd.DataFrame(), df_fix
            
        df_hist = pd.read_csv(training_path)
        df_hist = normalize_names(df_hist)
        df_hist['date'] = pd.to_datetime(df_hist['date'])
        
        # Recalcular ganadores para stats
        conditions = [
            (df_hist['home_score'] > df_hist['away_score']),
            (df_hist['home_score'] == df_hist['away_score']),
            (df_hist['home_score'] < df_hist['away_score'])
        ]
        df_hist['winner'] = np.select(conditions, ['Home', 'Draw', 'Away'], default='Draw')
        
        # Obtener últimas estadísticas conocidas
        stats = get_team_stats_history(df_hist)
        latest_stats = stats.sort_values('date').groupby('team').tail(1).set_index('team')
        
        # 3. Construir dataset de predicción
        data_for_pred = []
        valid_fixtures = []

        for _, row in df_fix.iterrows():
            ht, at = row['home_team'], row['away_team']
            
            if ht in latest_stats.index and at in latest_stats.index:
                row_data = {
                    'last_5_home_points': latest_stats.loc[ht, 'last_5_points'],
                    'last_5_away_points': latest_stats.loc[at, 'last_5_points'],
                    'rest_days_home': 7, # Asumimos descanso estándar para el futuro
                    'rest_days_away': 7,
                    'h2h_home_wins': 0 # Simplificación (cuesta mucho calcular h2h real en inferencia rápida)
                }
                data_for_pred.append(row_data)
                valid_fixtures.append(row)
        
        return pd.DataFrame(data_for_pred), pd.DataFrame(valid_fixtures)

    except Exception as e:
        print(f"Error preparing fixtures: {e}")
        return pd.DataFrame(), pd.DataFrame()

if __name__ == "__main__":
    # Test local
    print("Probando Feature Engineering...")
    df = prepare_data()
    if not df.empty:
        df.to_csv("data/training_set.csv", index=False)
        print("Training set generado.")