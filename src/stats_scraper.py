import pandas as pd
import logging
import os
import requests
import io
import numpy as np
from datetime import datetime

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# URL Temporadas (Actual y Pasada)
# Football-Data.co.uk es la fuente más fiable y rápida
FD_URLS = [
    "https://www.football-data.co.uk/mmz4281/2526/SP1.csv", # 25/26
    "https://www.football-data.co.uk/mmz4281/2425/SP1.csv", # 24/25
    "https://www.football-data.co.uk/mmz4281/2324/SP1.csv", # 23/24
    "https://www.football-data.co.uk/mmz4281/2223/SP1.csv", # 22/23
]

# Mapeo de Nombres (Para estandarizar con tu sistema)
NAME_MAPPING = {
    # Actuales 2025/26
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
    "Rayo Vallecano": "Rayo Vallecano", "Rayo": "Rayo Vallecano", "Vallecano": "Rayo Vallecano",
    
    # Históricos (Últimos 10 años) - IMPORTANTE AÑADIR ESTOS
    "Cadiz": "Cadiz",
    "Granada": "Granada",
    "Almeria": "Almeria",
    "Elche": "Elche",
    "Levante": "Levante",
    "Eibar": "Eibar",
    "Huesca": "Huesca",
    "Sp Gijon": "Sporting Gijon", "Sporting de Gijón": "Sporting Gijon",
    "La Coruna": "Deportivo La Coruna", "Deportivo": "Deportivo La Coruna",
    "Malaga": "Malaga",
    "Oviedo": "Real Oviedo",
    "Santander": "Racing Santander",
    "Zaragoza": "Real Zaragoza",
    "Tenerife": "Tenerife",
    "Cordoba": "Cordoba"
}

def fetch_technical_stats():
    """Descarga, une y limpia datos de Football-Data."""
    logger.info("📥 Descargando datos técnicos de Football-Data...")
    all_dfs = []
    
    for url in FD_URLS:
        try:
            # User-Agent para evitar bloqueos básicos (aunque FD es muy permisivo)
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # Decodificar y leer CSV
                df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
                
                # Filtrar filas vacías (partidos no jugados no tienen goles FTHG)
                if 'FTHG' in df.columns:
                    df = df[df['FTHG'].notna()]
                    logger.info(f"   ✅ Descargado: {url.split('/')[-2]} ({len(df)} partidos)")
                    all_dfs.append(df)
            else:
                logger.warning(f"   ⚠️ Fallo descarga ({response.status_code}): {url}")
                
        except Exception as e:
            logger.error(f"   ❌ Error con {url}: {e}")

    if not all_dfs:
        logger.error("❌ No se pudo descargar ningún dato.")
        return pd.DataFrame()

    # Unir todos los dataframes
    df_final = pd.concat(all_dfs, ignore_index=True)
    
    # Seleccionar columnas clave
    # FTHG/AG: Goles, HS/AS: Tiros, HST/AST: Tiros Puerta, HC/AC: Córners, HY/AY: Amarillas
    cols_needed = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 
                   'HS', 'AS', 'HST', 'AST', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR']
    
    # Filtrar solo las columnas que existen
    cols_present = [c for c in cols_needed if c in df_final.columns]
    df_final = df_final[cols_present].copy()
    
    # Normalizar Fechas
    df_final['Date'] = pd.to_datetime(df_final['Date'], dayfirst=True, errors='coerce')
    
    # Normalizar Nombres de Equipos
    df_final['HomeTeam'] = df_final['HomeTeam'].map(NAME_MAPPING).fillna(df_final['HomeTeam'])
    df_final['AwayTeam'] = df_final['AwayTeam'].map(NAME_MAPPING).fillna(df_final['AwayTeam'])
    
    # Renombrar columnas al estándar de tu proyecto (snake_case)
    df_final.rename(columns={
        'Date': 'date',
        'HomeTeam': 'home_team', 'AwayTeam': 'away_team',
        'FTHG': 'home_score', 'FTAG': 'away_score',
        'HS': 'home_shots', 'AS': 'away_shots',
        'HST': 'home_shots_on_target', 'AST': 'away_shots_on_target',
        'HC': 'home_corners', 'AC': 'away_corners',
        'HY': 'home_yellow', 'AY': 'away_yellow',
        'HR': 'home_red', 'AR': 'away_red'
    }, inplace=True)
    
    # Eliminar filas con fechas inválidas o equipos nulos
    df_final.dropna(subset=['date', 'home_team', 'away_team'], inplace=True)
    
    # Ordenar cronológicamente
    df_final.sort_values('date', inplace=True)
    
    return df_final

def main():
    df = fetch_technical_stats()
    
    if not df.empty:
        # Guardar CSV
        output_path = os.path.join(DATA_DIR, "laliga_advanced_stats.csv")
        df.to_csv(output_path, index=False)
        
        logger.info(f"✅ BASE DE DATOS FINAL CREADA: {len(df)} partidos.")
        logger.info(f"💾 Guardado en: {output_path}")
        logger.info("Métricas disponibles: Goles, Tiros, Tiros a Puerta, Córners, Tarjetas.")
    else:
        logger.error("❌ El proceso falló. No se generó el archivo.")

if __name__ == "__main__":
    main()