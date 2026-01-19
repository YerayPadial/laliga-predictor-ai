import requests
import pandas as pd
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# TU API KEY
API_KEY = "0f3d6700ed56499eaa6f67d1250a6901"
# URL Base de la competición (LaLiga Primera División)
BASE_URL_COMPETITION = "https://api.football-data.org/v4/competitions/PD"
# URL Base de partidos
BASE_URL_MATCHES = "https://api.football-data.org/v4/competitions/PD/matches"

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
    """
    Determina la jornada actual de forma robusta.
    Estrategia 1: Preguntar a la competición.
    Estrategia 2: Preguntar al primer partido pendiente.
    """
    headers = {'X-Auth-Token': API_KEY}
    
    # --- ESTRATEGIA 1: Vía Directa ---
    try:
        response = requests.get(BASE_URL_COMPETITION, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Verificamos que existan las claves antes de acceder
            if 'currentSeason' in data and data['currentSeason'] and 'currentMatchday' in data['currentSeason']:
                return data['currentSeason']['currentMatchday']
    except Exception as e:
        logger.warning(f"Estrategia 1 falló: {e}")

    # --- ESTRATEGIA 2: Vía 'Próximo Partido' (Fallback) ---
    logger.info("Activando Estrategia 2 para detectar jornada...")
    try:
        # Pedimos solo 1 partido que esté programado (SCHEDULED)
        params = {'status': 'SCHEDULED', 'limit': 1}
        response = requests.get(BASE_URL_MATCHES, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        
        matches = data.get('matches', [])
        if matches:
            # Si hay partidos futuros, la jornada actual es la de ese partido
            found_matchday = matches[0]['matchday']
            logger.info(f"Jornada detectada por próximo partido: {found_matchday}")
            return found_matchday
    except Exception as e:
        logger.error(f"Estrategia 2 falló: {e}")

    # Si todo falla, devolvemos None (el script principal manejará el error)
    return None

def fetch_fixtures():
    headers = {'X-Auth-Token': API_KEY}
    
    # 1. Obtener jornada actual (Con sistema anti-fallos)
    current_matchday = get_current_matchday()
    
    if not current_matchday:
        logger.error("❌ CRÍTICO: No se pudo determinar la jornada. Usando modo de emergencia.")
        # Creamos archivo vacío para no romper la web y salimos
        pd.DataFrame(columns=['matchday', 'utc_date', 'date_str', 'status', 'home_team', 'away_team', 'real_result']).to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)
        return

    logger.info(f"📍 Jornada Oficial Detectada: {current_matchday}")

    # 2. Descargar Jornada Actual y la Siguiente
    matchdays_to_fetch = [current_matchday, current_matchday + 1]
    all_matches = []

    for md in matchdays_to_fetch:
        try:
            url = f"{BASE_URL_MATCHES}?matchday={md}"
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            for match in data.get('matches', []):
                utc_date = match['utcDate']
                status = match['status']
                
                # Corrección Hora Madrid
                ts = pd.Timestamp(utc_date)
                ts_madrid = ts.tz_convert('Europe/Madrid')
                date_str = ts_madrid.strftime("%d/%m %H:%M")
                
                home_api = match['homeTeam']['name']
                away_api = match['awayTeam']['name']
                
                home = API_TO_MODEL_MAPPING.get(home_api, home_api)
                away = API_TO_MODEL_MAPPING.get(away_api, away_api)
                
                score_home = match['score']['fullTime']['home']
                score_away = match['score']['fullTime']['away']
                
                # Manejo seguro de None en el marcador
                if score_home is None: score_home = ""
                if score_away is None: score_away = ""
                
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
        # Ordenar por jornada y fecha
        df = df.sort_values(by=['matchday', 'utc_date'])
        df.to_csv(output_path, index=False)
        logger.info(f"✅ Calendario guardado: {len(df)} partidos.")
    else:
        logger.warning("⚠️ No se encontraron partidos.")
        pd.DataFrame(columns=['matchday', 'utc_date', 'date_str', 'status', 'home_team', 'away_team', 'real_result']).to_csv(output_path, index=False)

if __name__ == "__main__":
    fetch_fixtures()