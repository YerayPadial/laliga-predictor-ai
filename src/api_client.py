import requests
import pandas as pd
import logging
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# TU TOKEN PERSONAL (Lo extraje de tu mensaje anterior)
API_KEY = "0f3d6700ed56499eaa6f67d1250a6901"
BASE_URL = "https://api.football-data.org/v4/competitions/PD/matches" # PD = Primera Division

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Mapeo de nombres API -> Nombres Modelo
API_MAPPING = {
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
    "CD Leganés": "Leganes"
}

def fetch_fixtures():
    headers = {'X-Auth-Token': API_KEY}
    params = {'status': 'SCHEDULED'} # Solo partidos pendientes
    
    try:
        response = requests.get(BASE_URL, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        matches = []
        
        for match in data.get('matches', []):
            try:
                # Extraemos datos limpios
                matchday = match['matchday']
                utc_date = match['utcDate'] # Ej: 2026-01-20T19:00:00Z
                
                # Normalizamos nombres inmediatamente
                home_raw = match['homeTeam']['name']
                away_raw = match['awayTeam']['name']
                
                home = API_MAPPING.get(home_raw, home_raw) # Si no está en mapa, usa el original
                away = API_MAPPING.get(away_raw, away_raw)
                
                # Formatear fecha
                dt = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                date_str = dt.strftime("%Y-%m-%d %H:%M")
                
                matches.append({
                    "matchday": matchday,
                    "date_str": date_str,
                    "home_team": home,
                    "away_team": away
                })
            except Exception as e:
                logger.warning(f"Error procesando un partido: {e}")
                continue
                
        df = pd.DataFrame(matches)
        
        if not df.empty:
            output_path = os.path.join(DATA_DIR, "laliga_fixtures.csv")
            df.to_csv(output_path, index=False)
            logger.info(f"✅ API Éxito: {len(df)} partidos pendientes descargados.")
            logger.info(f"Jornadas detectadas: {df['matchday'].unique()}")
        else:
            logger.warning("⚠️ La API devolvió 0 partidos pendientes (¿Final de temporada?).")
            
    except Exception as e:
        logger.error(f"❌ Error conectando con API: {e}")

if __name__ == "__main__":
    fetch_fixtures()