# Este archivo se encarga de conectarse a una fuente oficial (API) para saber qué partidos se van a jugar
import requests
import pandas as pd
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# esta es mi api key para la api de football-data.org
API_KEY = "0f3d6700ed56499eaa6f67d1250a6901"
BASE_URL = "https://api.football-data.org/v4/competitions/PD/matches"

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Mapeo de nombre de equipos de la api a los nombres usados por el modelo
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

# Función principal para obtener el calendario completo de La Liga
def fetch_fixtures():
    headers = {'X-Auth-Token': API_KEY}
    # pido todo el calendario de la temporada, todas las jornadas
    
    try:
        logger.info("Descargando calendario COMPLETO de la temporada...")
       # me conecto a la api y obtengo los datos
        response = requests.get(BASE_URL, headers=headers)
        # verifico el estado de la respuesta
        response.raise_for_status()
        data = response.json()
        matches = []
        
        # recorro cada partido obtenido
        for match in data.get('matches', []):
            try:
                matchday = match['matchday']
                utc_date = match['utcDate']
                status = match['status'] # SCHEDULED, FINISHED, etc.
                
                # Corrección Hora Madrid
                ts = pd.Timestamp(utc_date)
                ts_madrid = ts.tz_convert('Europe/Madrid')
                date_str = ts_madrid.strftime("%d/%m %H:%M")
                
                # equipos y lugar del partido
                home_api = match['homeTeam']['name']
                away_api = match['awayTeam']['name']
                
                home = API_TO_MODEL_MAPPING.get(home_api, home_api)
                away = API_TO_MODEL_MAPPING.get(away_api, away_api)
                
                # Resultados de los partidos ya jugados
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                
                # manejo los nulos
                if score_home is None: score_home = ""
                if score_away is None: score_away = ""
                
                # el resultado solo si el partido ya se jugo
                result_str = f"{score_home}-{score_away}" if status == 'FINISHED' else "-"

                # guardo toda la info del partido
                matches.append({
                    "matchday": matchday,
                    "utc_date": utc_date, # Vital para ordenar por fechas
                    "date_str": date_str,
                    "status": status,
                    "home_team": home,
                    "away_team": away,
                    "real_result": result_str
                })
            except Exception as e:
                continue
        # creo el dataframe con todos los partidos        
        df = pd.DataFrame(matches)
        
        # guardo el calendario completo en un csv
        output_path = os.path.join(DATA_DIR, "laliga_fixtures.csv")
        if not df.empty:
            # Ordenamos por Jornada y fecha
            df = df.sort_values(by=['matchday', 'utc_date'])
            df.to_csv(output_path, index=False)
            logger.info(f"Temporada completa guardada: {len(df)} partidos (Jornadas 1-38).")
        else:
            logger.warning("La API devolvió 0 partidos.")
            
    except Exception as e:
        logger.error(f"Error en API: {e}")

if __name__ == "__main__":
    fetch_fixtures()