import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

# --- CONFIGURACIÓN DE NOMBRES ---
TEAM_MAPPING = {
    "Ath Bilbao": "Athletic Bilbao", "Athletic Club": "Athletic Bilbao",
    "Ath Madrid": "Atletico Madrid", "Atlético de Madrid": "Atletico Madrid",
    "Espanol": "Espanyol", "RCD Espanyol": "Espanyol",
    "Celta": "Celta de Vigo", "Celta Vigo": "Celta de Vigo",
    "Betis": "Real Betis", "Real Betis Balompie": "Real Betis",
    "Sociedad": "Real Sociedad", "Real Sociedad de Futbol": "Real Sociedad",
    "Real Madrid": "Real Madrid",
    "Barcelona": "Barcelona", "FC Barcelona": "Barcelona",
    "Girona": "Girona", "Girona FC": "Girona",
    "Valencia": "Valencia", "Valencia CF": "Valencia",
    "Mallorca": "Mallorca", "RCD Mallorca": "Mallorca",
    "Osasuna": "Osasuna", "CA Osasuna": "Osasuna",
    "Sevilla": "Sevilla", "Sevilla FC": "Sevilla",
    "Villarreal": "Villarreal", "Villarreal CF": "Villarreal",
    "Alaves": "Alaves", "Deportivo Alavés": "Alaves",
    "Las Palmas": "Las Palmas", "UD Las Palmas": "Las Palmas",
    "Leganes": "Leganes", "CD Leganés": "Leganes",
    "Valladolid": "Real Valladolid", "Real Valladolid CF": "Real Valladolid",
    "Getafe": "Getafe", "Getafe CF": "Getafe",
    "Rayo Vallecano": "Rayo Vallecano", "Rayo": "Rayo Vallecano",
    "Oviedo": "Real Oviedo", "Levante": "Levante", "Elche": "Elche"
}

def normalize_names(df: pd.DataFrame) -> pd.DataFrame:
    if 'home_team' in df.columns:
        df['home_team'] = df['home_team'].replace(TEAM_MAPPING).str.strip()
    if 'away_team' in df.columns:
        df['away_team'] = df['away_team'].replace(TEAM_MAPPING).str.strip()
    return df

# --- CÁLCULO DE DÍAS DE DESCANSO ---
def calculate_rest_days(df):
    """Calcula los días de descanso desde el último partido para cada equipo."""
    # Creamos una lista vertical de todos los partidos jugados por cualquier equipo
    home = df[['date', 'home_team']].rename(columns={'home_team': 'team'})
    away = df[['date', 'away_team']].rename(columns={'away_team': 'team'})
    all_matches = pd.concat([home, away]).sort_values(['team', 'date'])
    
    # Calculamos la diferencia de días con el partido anterior
    all_matches['prev_date'] = all_matches.groupby('team')['date'].shift(1)
    all_matches['rest_days'] = (all_matches['date'] - all_matches['prev_date']).dt.days
    
    # Rellenamos los huecos (primer partido de liga) con 7 días (descanso estándar)
    all_matches['rest_days'] = all_matches['rest_days'].fillna(7)
    
    # Limitamos a 14 días para que un parón de selecciones no distorsione el dato
    all_matches['rest_days'] = np.clip(all_matches['rest_days'], 2, 14)
    
    return all_matches[['date', 'team', 'rest_days']]

# --- CÁLCULO DE H2H (ENFRENTAMIENTOS DIRECTOS) ---
def get_h2h_balance(row, df_history):
    """Calcula cuántos puntos suele sacar el LOCAL contra este VISITANTE históricamente."""
    # Filtramos partidos pasados entre estos dos equipos
    mask = (
        (df_history['date'] < row['date']) & 
        (
            ((df_history['home_team'] == row['home_team']) & (df_history['away_team'] == row['away_team'])) |
            ((df_history['home_team'] == row['away_team']) & (df_history['away_team'] == row['home_team']))
        )
    )
    past_games = df_history[mask]
    
    if past_games.empty:
        return 1.5 # Valor neutro (ni gana ni pierde mucho)
    
    # Calculamos puntos obtenidos por el equipo que hoy es LOCAL
    points = 0
    for _, m in past_games.iterrows():
        # Si jugó como local
        if m['home_team'] == row['home_team']:
            if m['home_score'] > m['away_score']: points += 3
            elif m['home_score'] == m['away_score']: points += 1
        # Si jugó como visitante
        else:
            if m['away_score'] > m['home_score']: points += 3
            elif m['away_score'] == m['home_score']: points += 1
            
    return points / len(past_games) # Promedio de puntos H2H

# --- MÉTRICAS DE RENDIMIENTO (ROLLING STATS) ---
def calculate_rolling_stats(df, window=5):
    # Selección de columnas 
    cols_home = ['date', 'home_team', 'home_score', 'away_score', 'home_shots', 'home_shots_on_target', 'home_corners']
    home_stats = df[cols_home].copy()
    home_stats.columns = ['date', 'team', 'goals_for', 'goals_against', 'shots', 'shots_ot', 'corners']
    
    cols_away = ['date', 'away_team', 'away_score', 'home_score', 'away_shots', 'away_shots_on_target', 'away_corners']
    away_stats = df[cols_away].copy()
    away_stats.columns = ['date', 'team', 'goals_for', 'goals_against', 'shots', 'shots_ot', 'corners']
    
    stats_df = pd.concat([home_stats, away_stats]).sort_values(['team', 'date'])
    
    # Calcular Tiros FUERA (Total - A Puerta)
    # A veces la estadística falla y dice que hay más a puerta que totales, protegemos con clip(0)
    stats_df['shots_off'] = (stats_df['shots'] - stats_df['shots_ot']).clip(lower=0)
    
    # Puntos del partido
    stats_df['points'] = np.where(stats_df['goals_for'] > stats_df['goals_against'], 3,
                                  np.where(stats_df['goals_for'] == stats_df['goals_against'], 1, 0))
    
    # --- FÓRMULA DE ATAQUE EXPERTA ---
    # Goles: 3.0 | Tiros a Puerta: 1.0 | Tiros Fuera: 0.5 | Córners: 0.7
    stats_df['attack_power'] = (
        (stats_df['goals_for'] * 3.0) + 
        (stats_df['shots_ot'] * 1.0) + 
        (stats_df['shots_off'] * 0.5) + 
        (stats_df['corners'] * 0.7)
    )
    
    # Medias Móviles (EMA) - Usamos solo lo necesario para el modelo
    cols = ['points', 'goals_for', 'goals_against', 'attack_power']
    for col in cols:
        stats_df[f'avg_{col}'] = stats_df.groupby('team')[col].transform(
            lambda x: x.shift(1).ewm(span=window, min_periods=1).mean()
        ).fillna(0)
    
    # Racha de forma
    stats_df['form_streak'] = stats_df.groupby('team')['points'].transform(
        lambda x: x.shift(1).rolling(window=3, min_periods=1).sum()
    ).fillna(0)
    
    return stats_df[['date', 'team', 'avg_points', 'avg_goals_for', 'avg_goals_against', 'avg_attack_power', 'form_streak']]

def prepare_data(input_path="data/laliga_advanced_stats.csv", train_mode=True):
    if not os.path.exists(input_path):
        print("❌ Error: Falta el archivo de datos.")
        return pd.DataFrame()

    df = pd.read_csv(input_path)
    df = normalize_names(df)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date')
    
    # 1. Calcular Estadísticas Rodantes (Forma, Ataque)
    stats = calculate_rolling_stats(df, window=5)
    
    # 2. Calcular Días de Descanso
    rest_stats = calculate_rest_days(df)
    
    # 3. Fusionar Local
    df = df.merge(stats, left_on=['date', 'home_team'], right_on=['date', 'team'], how='left').drop(columns=['team'])
    df = df.rename(columns={c: f'home_{c}' for c in stats.columns if c not in ['date', 'team']})
    df = df.merge(rest_stats, left_on=['date', 'home_team'], right_on=['date', 'team'], how='left').drop(columns=['team'])
    df = df.rename(columns={'rest_days': 'home_rest_days'})
    
    # 4. Fusionar Visitante
    df = df.merge(stats, left_on=['date', 'away_team'], right_on=['date', 'team'], how='left').drop(columns=['team'])
    df = df.rename(columns={c: f'away_{c}' for c in stats.columns if c not in ['date', 'team']})
    df = df.merge(rest_stats, left_on=['date', 'away_team'], right_on=['date', 'team'], how='left').drop(columns=['team'])
    df = df.rename(columns={'rest_days': 'away_rest_days'})
    
    # 5. Calcular H2H (Histórico Directo)
    if train_mode:
        print("⏳ Calculando H2H (Paternidad)...")
        # Usamos una lambda optimizada
        df['h2h_balance'] = df.apply(lambda x: get_h2h_balance(x, df), axis=1)
    else:
        df['h2h_balance'] = 1.5 # Valor neutro por defecto si no hay histórico cargado
        
    # 6. Diferenciales (Inputs finales para la IA)
    df['diff_points'] = df['home_avg_points'] - df['away_avg_points']
    df['diff_attack'] = df['home_avg_attack_power'] - df['away_avg_attack_power']
    df['diff_rest'] = df['home_rest_days'] - df['away_rest_days'] # Positivo = Local más descansado
    
    # 7. Target
    conditions = [
        (df['home_score'] > df['away_score']),
        (df['home_score'] == df['away_score']),
        (df['home_score'] < df['away_score'])
    ]
    df['TARGET'] = np.select(conditions, [0, 1, 2], default=1)
    
    # Limpieza final
    df = df.dropna()
    if train_mode:
        df = df[df['home_avg_points'] != 0] # Quitar primeras jornadas sin datos
        
    # Selección de Features
    features = [
        'date', 'home_team', 'away_team',
        'home_avg_points', 'away_avg_points',
        'home_avg_attack_power', 'away_avg_attack_power',
        'home_form_streak', 'away_form_streak',
        'home_rest_days', 'away_rest_days',
        'h2h_balance',
        'diff_points', 'diff_attack', 'diff_rest',
        'TARGET'
    ]
    
    final_df = df[features].copy()
    
    if train_mode:
        print(f"✅ Datos Expertos: {len(final_df)} filas.")
        print(final_df[['home_team', 'away_team', 'h2h_balance', 'home_rest_days', 'diff_rest']].head())
        
    return final_df

def prepare_upcoming_matches(fixtures_input, history_path="data/laliga_advanced_stats.csv"):
    """
    Prepara los partidos de la próxima jornada (fixtures) pegándoles 
    las estadísticas históricas (history) para que la IA pueda predecir.
    Acepta tanto una ruta de archivo (str) como un DataFrame ya cargado.
    """
    # 1. Validar Historial (Siempre es una ruta)
    if not os.path.exists(history_path):
        return pd.DataFrame(), pd.DataFrame()
    
    # 2. Gestionar el input de Fixtures (Puede ser ruta o DataFrame)
    if isinstance(fixtures_input, str):
        # Si es texto (ruta), verificamos que exista y cargamos
        if not os.path.exists(fixtures_input):
            return pd.DataFrame(), pd.DataFrame()
        fixtures_df = pd.read_csv(fixtures_input)
    elif isinstance(fixtures_input, pd.DataFrame):
        # Si ya es un DataFrame, lo usamos directamente
        fixtures_df = fixtures_input.copy()
    else:
        # Si no es ni lo uno ni lo otro, error
        return pd.DataFrame(), pd.DataFrame()

    # 3. Cargar Histórico (La "Enciclopedia")
    history = pd.read_csv(history_path)
    history = normalize_names(history)
    history['date'] = pd.to_datetime(history['date'])
    
    # Calcular stats actuales hasta el día de hoy
    stats = calculate_rolling_stats(history)
    
    # Nos quedamos con la ÚLTIMA fila de stats de cada equipo
    latest_stats = stats.sort_values('date').groupby('team').tail(1).set_index('team')
    
    # Normalizar nombres del calendario
    fixtures_df = normalize_names(fixtures_df)
    
    predict_data = []
    
    # 4. Cruzar datos: Para cada partido futuro, buscamos cómo vienen los equipos
    for idx, row in fixtures_df.iterrows():
        home = row['home_team']
        away = row['away_team']
        
        # Si un equipo es nuevo y no tiene historia, no podemos predecir
        if home not in latest_stats.index or away not in latest_stats.index:
            # Añadimos fila vacía para mantener el índice alineado
            predict_data.append({}) 
            continue
            
        h_stats = latest_stats.loc[home]
        a_stats = latest_stats.loc[away]
        
        # Simular H2H
        dummy_row = {'date': datetime.now(), 'home_team': home, 'away_team': away}
        h2h = get_h2h_balance(dummy_row, history)
        
        # Construir la fila exacta que necesita la IA
        match_features = {
            'home_avg_points': h_stats['avg_points'],
            'away_avg_points': a_stats['avg_points'],
            'home_avg_attack_power': h_stats['avg_attack_power'], 
            'away_avg_attack_power': a_stats['avg_attack_power'], 
            'home_form_streak': h_stats['form_streak'],
            'away_form_streak': a_stats['form_streak'],
            'home_rest_days': 7,
            'away_rest_days': 7,
            'h2h_balance': h2h,
            'diff_points': h_stats['avg_points'] - a_stats['avg_points'],
            'diff_attack': h_stats['avg_attack_power'] - a_stats['avg_attack_power'],
            'diff_rest': 0
        }
        predict_data.append(match_features)
        
    # Crear DataFrame y limpiar filas vacías si hubo equipos desconocidos
    X_pred = pd.DataFrame(predict_data)
    
    # Devolvemos X_pred (para la IA) y fixtures_df (para mostrar en pantalla)
    # Es vital que tengan el mismo número de filas, por eso rellenamos con {} arriba
    if not X_pred.empty:
        valid_indices = X_pred.dropna().index
        return X_pred.loc[valid_indices], fixtures_df.loc[valid_indices]
    
    return pd.DataFrame(), pd.DataFrame()

if __name__ == "__main__":
    # Solo para probar que no explota
    df = prepare_data(train_mode=True)
    if not df.empty:
        print(f"✅ Feature Engineering OK. Filas: {len(df)}")
        print(df.head())