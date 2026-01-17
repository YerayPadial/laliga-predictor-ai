import os
import time
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, List

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    # User Agent rotatorio simple para evitar bloqueos
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=chrome_options)

def clean_team_name(text: str) -> str:
    """Elimina residuos numéricos al final del nombre."""
    if not text: return ""
    import re
    # Elimina ' 2', ' 19', etc. al final del string
    text = re.sub(r'\s\d+$', '', text) 
    return text.strip()

def safe_extract_text(row, selectors: List[str]) -> Optional[str]:
    """Intenta extraer texto de una lista de selectores."""
    for selector in selectors:
        try:
            elements = row.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                text = elements[0].text.strip()
                if text:
                    return clean_team_name(text)
        except:
            continue
    return None

def scrape_data(driver: webdriver.Chrome, url: str, is_history: bool) -> pd.DataFrame:
    """
    Función maestra para scrapear Resultados o Calendario.
    """
    logger.info(f"Iniciando Scraping ({'HISTORIAL' if is_history else 'CALENDARIO'}): {url}")
    data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 15)
        
        # 1. Esperar a que cargue la estructura base
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".leagues--static, .sportName")))
        time.sleep(3) # Pausa de cortesía para carga de JS

        # 2. Localizar filas de partidos
        # Flashscore usa 'event__match' tanto para pasados como futuros
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        if not match_rows:
            logger.warning("No se encontraron filas con selectores estándar. Intentando recarga profunda...")
            # Fallback: A veces el calendario está vacío si es fin de temporada o cambio de jornada
            return pd.DataFrame()

        logger.info(f"Detectados {len(match_rows)} partidos en pantalla.")

        # 3. Definir Selectores
        home_sels = [".event__participant--home", ".event__homeParticipant", ".wcl-participant_..."] 
        away_sels = [".event__participant--away", ".event__awayParticipant", ".wcl-participant_..."]
        
        # Solo historial
        score_home_sels = [".event__score--home", ".event__part--home"]
        score_away_sels = [".event__score--away", ".event__part--away"]
        
        # Solo calendario
        time_sels = [".event__time"]

        success_count = 0
        
        for row in match_rows:
            try:
                # Extracción Básica (Nombres)
                home = safe_extract_text(row, home_sels)
                away = safe_extract_text(row, away_sels)
                
                if not home or not away: 
                    continue # Saltamos filas vacías o de separadores

                match_info = {
                    "home_team": home,
                    "away_team": away,
                }

                if is_history:
                    # Lógica HISTORIAL: Necesitamos goles
                    s_home = safe_extract_text(row, score_home_sels)
                    s_away = safe_extract_text(row, score_away_sels)
                    
                    if s_home and s_away and s_home.isdigit() and s_away.isdigit():
                        match_info["date"] = datetime.now().strftime("%Y-%m-%d") 
                        match_info["home_score"] = int(s_home)
                        match_info["away_score"] = int(s_away)
                        data.append(match_info)
                        success_count += 1
                else:
                    # Lógica CALENDARIO: Necesitamos hora (opcional)
                    # A veces no hay hora exacta ("Aplazado"), no fallamos por eso
                    match_time = safe_extract_text(row, time_sels) 
                    match_info["date_str"] = match_time if match_time else "Pendiente"
                    
                    # Guardamos el partido para la quiniela
                    data.append(match_info)
                    success_count += 1

            except Exception:
                # Si falla una fila, continuamos con la siguiente
                continue

        logger.info(f"✅ Extracción completada. {success_count} partidos válidos.")

    except Exception as e:
        logger.error(f"❌ Error CRÍTICO en scraping: {e}")
        # No relanzamos la excepción para permitir que el resto del pipeline siga

    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    
    # URLs Oficiales
    URL_HISTORY = "https://www.flashscore.es/futbol/espana/laliga/resultados/"
    URL_FIXTURES = "https://www.flashscore.es/futbol/espana/laliga/calendario/"
    
    try:
        # 1. Ejecutar Scraping de Historial
        df_hist = scrape_data(driver, URL_HISTORY, is_history=True)
        if not df_hist.empty:
            path = os.path.join(DATA_DIR, "laliga_results_raw.csv")
            df_hist.to_csv(path, index=False)
            logger.info(f"💾 Guardado Historial: {path}")

        # 2. Ejecutar Scraping de Calendario (Quiniela)
        df_future = scrape_data(driver, URL_FIXTURES, is_history=False)
        if not df_future.empty:
            path = os.path.join(DATA_DIR, "laliga_fixtures.csv")
            df_future.to_csv(path, index=False)
            logger.info(f"💾 Guardado Calendario: {path}")
        else:
            logger.warning("⚠️ El Calendario devolvió 0 partidos. ¿Es fin de jornada?")

    finally:
        driver.quit()
        logger.info("Navegador cerrado.")

if __name__ == "__main__":
    main()