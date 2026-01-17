import os
import time
import logging
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuración de Logging para ver qué pasa en GitHub Actions
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Directorio de datos
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    """
    Configura e inicia un navegador Chrome en modo Headless optimizado para CI/CD.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # CRÍTICO: Sin UI
    chrome_options.add_argument("--no-sandbox") # CRÍTICO: Para Docker/Linux
    chrome_options.add_argument("--disable-dev-shm-usage") # CRÍTICO: Memoria compartida
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # User Agent para no parecer un bot básico
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    return driver

def scrape_historical_results(driver: webdriver.Chrome, url: str) -> pd.DataFrame:
    """
     Extrae resultados con mejor manejo de errores.
    """
    logger.info(f"Iniciando scraping de resultados: {url}")
    data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        # Esperar a que cargue algo reconocible
        wait.until(EC.presence_of_element_located((By.ID, "live-table")))
        
        # Encontrar filas de partidos
        match_rows = driver.find_elements(By.CSS_SELECTOR, ".event__match")
        logger.info(f"Encontrados {len(match_rows)} partidos potenciales. Procesando...")

        success_count = 0
        error_count = 0

        for row in match_rows:
            try:
                # Intentamos extraer texto general primero para depuración
                row_text = row.text
                
                # Búsqueda de equipos (Selectores actualizados a lo más común en Flashscore)
                # Nota: A veces usan classes como "event__participant--home" y otras veces "event__participant--away"
                home_team = row.find_element(By.CSS_SELECTOR, ".event__participant--home").text
                away_team = row.find_element(By.CSS_SELECTOR, ".event__participant--away").text
                
                # Scores - IMPORTANTE: Solo extraemos si hay goles (partido terminado)
                # Si el partido no tiene goles, find_element fallará o devolverá vacío.
                score_home_element = row.find_elements(By.CSS_SELECTOR, ".event__score--home")
                score_away_element = row.find_elements(By.CSS_SELECTOR, ".event__score--away")
                
                if score_home_element and score_away_element:
                    score_home = score_home_element[0].text
                    score_away = score_away_element[0].text
                    
                    if score_home.isdigit() and score_away.isdigit():
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"), 
                            "home_team": home_team,
                            "away_team": away_team,
                            "home_score": int(score_home),
                            "away_score": int(score_away)
                        })
                        success_count += 1
                else:
                    # Es un partido futuro o sin goles, lo ignoramos sin error
                    continue

            except Exception as row_e:
                # Si falla, imprimimos la primera vez para entender por qué
                if error_count < 3: 
                    logger.warning(f"Fallo al leer fila: {row_e}")
                error_count += 1
                continue

        logger.info(f"Procesamiento finalizado. Éxitos: {success_count}, Fallos/Futuros: {error_count}")

    except TimeoutException:
        logger.error("Timeout: La página tardó demasiado y no se encontraron elementos.")
    except Exception as e:
        logger.error(f"Error fatal general: {e}")

    df = pd.DataFrame(data)
    return df

def scrape_standings(driver: webdriver.Chrome, url: str) -> pd.DataFrame:
    """
    Extrae la tabla de clasificación actual.
    """
    logger.info(f"Iniciando scraping de clasificación: {url}")
    data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 10)
        # Esperar tabla
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ui-table__row")))
        
        rows = driver.find_elements(By.CLASS_NAME, "ui-table__row")
        
        for row in rows:
            try:
                team_name = row.find_element(By.CLASS_NAME, "table__participant").text
                points = row.find_element(By.CSS_SELECTOR, ".table__cell--value").text # Ajustar selector
                
                data.append({
                    "team": team_name,
                    "points": int(points)
                })
            except:
                continue
                
    except Exception as e:
        logger.error(f"Error en clasificación: {e}")
        
    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    
    # URLs objetivo (Ejemplos basados en tu estrategia)
    URL_RESULTS = "https://www.flashscore.es/futbol/espana/laliga/resultados/"
    # URL_STANDINGS = "https://www.flashscore.es/futbol/espana/laliga/clasificacion/"
    
    try:
        # 1. Extraer Resultados
        df_results = scrape_historical_results(driver, URL_RESULTS)
        if not df_results.empty:
            path = os.path.join(DATA_DIR, "laliga_results_raw.csv")
            df_results.to_csv(path, index=False)
            logger.info(f"Guardado: {path}")
        else:
            logger.warning("No se extrajeron datos de resultados.")

        # 2. Extraer Clasificación (Opcional por ahora)
        # df_standings = scrape_standings(driver, URL_STANDINGS)
        # ... guardar ...

    finally:
        driver.quit()
        logger.info("Driver cerrado.")

if __name__ == "__main__":
    main()