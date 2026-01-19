import requests
import pandas as pd
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# TU API KEY
API_KEY = "0f3d6700ed56499eaa6f67d1250a6901"
BASE_URL = "https://api.football-data.org/v4/competitions/PD/matches"

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Mapeo
API_TO_MODEL_MAPPING = {
    "Athletic Club": "Athletic Bilbao",
    "Club Atlético de Madrid": "Atletico Madrid",
    "CA Osasuna": "Osasuna",
    "FC Barcelona": "Barcelona",
    "Getafe CF": "Getafe",
    "Girona FC": "Girona",
    "Rayo Vallecano de Madrid": "Rayo Vallecano",
    "RC Celta de Vigo": "Celta de Vigo",
    "RCD Espanyol de Barcelona": "Espanyol",
    "RCD Mallorca": "Mallorca",
    "Real Betis Balompié": "Real Betis",
    "Real Madrid CF": "Real Madrid",
    "Real Sociedad de Fútbol": "Real Sociedad",
    "Real Valladolid CF": "Real Valladolid",
    "Sevilla FC": "Sevilla",
    "Valencia CF": "Valencia",
    "Villarreal CF": "Villarreal",
    "Deportivo Alavés": "Alaves",
    "UD Las Palmas": "Las Palmas",
    "CD Leganés": "Leganes",
    "Elche CF": "Elche",
    "Levante UD": "Levante",
    "Real Oviedo": "Real Oviedo",
}

def get_current_matchday():
    """Consulta a la API cuál es la jornada actual oficial."""
    headers = {'X-Auth-Token': API_KEY}
    try:
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['currentSeason']['currentMatchday']
    except Exception as e:
        logger.error(f"Error obteniendo jornada actual: {e}")
        return None

def fetch_fixtures():
    headers = {'X-Auth-Token': API_KEY}
    
    # 1. Obtener jornada actual
    current_matchday = get_current_matchday()
    if not current_matchday:
        logger.error("No se pudo determinar la jornada. Abortando.")
        return

    logger.info(f"📍 Jornada Actual Oficial: {current_matchday}")

    # 2. Descargar Jornada Actual y la Siguiente
    # Queremos ver la jornada actual ENTERA (incluyendo terminados) y la siguiente.
    matchdays_to_fetch = [current_matchday, current_matchday + 1]
    
    all_matches = []

    for md in matchdays_to_fetch:
        try:
            # Endpoint para partidos filtrados por jornada
            url = f"{BASE_URL}/matches?matchday={md}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            for match in data.get('matches', []):
                utc_date = match['utcDate']
                status = match['status'] # SCHEDULED, TIMED, IN_PLAY, PAUSED, FINISHED
                
                # Corrección Hora Madrid
                ts = pd.Timestamp(utc_date)
                ts_madrid = ts.tz_convert('Europe/Madrid')
                date_str = ts_madrid.strftime("%d/%m %H:%M")
                
                home_api = match['homeTeam']['name']
                away_api = match['awayTeam']['name']
                
                home = API_TO_MODEL_MAPPING.get(home_api, home_api)
                away = API_TO_MODEL_MAPPING.get(away_api, away_api)
                
                # Guardamos resultado real si existe (para mostrar en frontend)
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                
                result_str = f"{score_home}-{score_away}" if status == 'FINISHED' else "-"

                all_matches.append({
                    "matchday": md,
                    "utc_date": utc_date,
                    "date_str": date_str,
                    "status": status,
                    "home_team": home,
                    "away_team": away,
                    "real_result": result_str
                })
                
        except Exception as e:
            logger.error(f"Error descargando jornada {md}: {e}")
            continue

    df = pd.DataFrame(all_matches)
    
    output_path = os.path.join(DATA_DIR, "laliga_fixtures.csv")
    if not df.empty:
        df = df.sort_values(by=['matchday', 'utc_date'])
        df.to_csv(output_path, index=False)
        logger.info(f"✅ Calendario actualizado: {len(df)} partidos (Jornadas {matchdays_to_fetch}).")
    else:
        logger.warning("⚠️ La API no devolvió partidos.")
        # Crear estructura vacía para evitar error en app
        pd.DataFrame(columns=['matchday', 'utc_date', 'date_str', 'status', 'home_team', 'away_team', 'real_result']).to_csv(output_path, index=False)

if __name__ == "__main__":
    fetch_fixtures()