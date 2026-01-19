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

def fetch_fixtures():
    headers = {'X-Auth-Token': API_KEY}
    # No filtramos por status ni matchday. Pedimos TODO el calendario 2024/2025.
    
    try:
        logger.info("📡 Descargando calendario COMPLETO de la temporada...")
        response = requests.get(BASE_URL, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        matches = []
        
        for match in data.get('matches', []):
            try:
                matchday = match['matchday']
                utc_date = match['utcDate']
                status = match['status'] # SCHEDULED, FINISHED, IN_PLAY...
                
                # Corrección Hora Madrid
                ts = pd.Timestamp(utc_date)
                ts_madrid = ts.tz_convert('Europe/Madrid')
                date_str = ts_madrid.strftime("%d/%m %H:%M")
                
                home_api = match['homeTeam']['name']
                away_api = match['awayTeam']['name']
                
                home = API_TO_MODEL_MAPPING.get(home_api, home_api)
                away = API_TO_MODEL_MAPPING.get(away_api, away_api)
                
                # Resultados
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                
                if score_home is None: score_home = ""
                if score_away is None: score_away = ""
                
                result_str = f"{score_home}-{score_away}" if status == 'FINISHED' else "-"

                matches.append({
                    "matchday": matchday,
                    "utc_date": utc_date, # Vital para ordenar
                    "date_str": date_str,
                    "status": status,
                    "home_team": home,
                    "away_team": away,
                    "real_result": result_str
                })
            except Exception as e:
                continue
                
        df = pd.DataFrame(matches)
        
        output_path = os.path.join(DATA_DIR, "laliga_fixtures.csv")
        if not df.empty:
            # Ordenamos por Jornada y fecha
            df = df.sort_values(by=['matchday', 'utc_date'])
            df.to_csv(output_path, index=False)
            logger.info(f"✅ Temporada completa guardada: {len(df)} partidos (Jornadas 1-38).")
        else:
            logger.warning("⚠️ La API devolvió 0 partidos.")
            
    except Exception as e:
        logger.error(f"❌ Error en API: {e}")

if __name__ == "__main__":
    fetch_fixtures()