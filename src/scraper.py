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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    """Configuración 'Stealth' para evitar bloqueos."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    # Truco del Arquitecto: Ocultar que somos un bot de automatización
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=chrome_options)

def clean_team_name(text: str) -> str:
    if not text: return ""
    import re
    # Eliminar patrones de números al final (ej: "Real Oviedo 2")
    text = re.sub(r'\s\d+$', '', text)
    return text.strip()

def handle_cookies(driver):
    """Intenta cerrar el banner de cookies de Flashscore/Livesport."""
    try:
        # Buscamos botones típicos de 'Aceptar' o 'Rechazar'
        accept_btn = driver.find_elements(By.ID, "onetrust-accept-btn-handler")
        if accept_btn:
            accept_btn[0].click()
            time.sleep(1)
            logger.info("🍪 Cookies aceptadas.")
    except:
        pass

def scrape_data(driver: webdriver.Chrome, url: str, is_history: bool) -> pd.DataFrame:
    logger.info(f"Iniciando Scraping ({'HISTORIAL' if is_history else 'CALENDARIO'}): {url}")
    data = []
    
    try:
        driver.get(url)
        handle_cookies(driver) # Intentar quitar cookies
        
        wait = WebDriverWait(driver, 15)
        # Esperamos cualquier elemento de carga de contenido
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".sportName, .leagues--static")))
        except:
            logger.warning("Timeout esperando estructura base. Posible bloqueo o página vacía.")
            # Si falla, intentamos devolver lo que haya o lista vacía
            return pd.DataFrame()

        time.sleep(3) 

        # Selector Genérico
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        logger.info(f"Detectados {len(match_rows)} partidos.")

        # Selectores (Optimizados)
        home_sels = [".event__participant--home", ".event__homeParticipant"] 
        away_sels = [".event__participant--away", ".event__awayParticipant"]
        score_home_sels = [".event__score--home", ".event__part--home"]
        score_away_sels = [".event__score--away", ".event__part--away"]
        time_sels = [".event__time"]

        for row in match_rows:
            try:
                # Extraer texto de forma segura
                def get_text(sels):
                    for s in sels:
                        elems = row.find_elements(By.CSS_SELECTOR, s)
                        if elems and elems[0].text.strip():
                            return clean_team_name(elems[0].text.strip())
                    return None

                home = get_text(home_sels)
                away = get_text(away_sels)
                
                if not home or not away: continue

                match_info = {"home_team": home, "away_team": away}

                if is_history:
                    s_home = get_text(score_home_sels)
                    s_away = get_text(score_away_sels)
                    if s_home and s_away and s_home.isdigit() and s_away.isdigit():
                        match_info["date"] = datetime.now().strftime("%Y-%m-%d")
                        match_info["home_score"] = int(s_home)
                        match_info["away_score"] = int(s_away)
                        data.append(match_info)
                else:
                    # CALENDARIO: Importante extraer la fecha/hora
                    m_time = get_text(time_sels) # Ej: "17.01. 14:00"
                    match_info["date_str"] = m_time if m_time else datetime.now().strftime("%d.%m. 00:00")
                    data.append(match_info)

            except Exception:
                continue

    except Exception as e:
        logger.error(f"❌ Error CRÍTICO controlado: {e}")
    
    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    try:
        # Historial
        df_hist = scrape_data(driver, "https://www.flashscore.es/futbol/espana/laliga/resultados/", is_history=True)
        if not df_hist.empty:
            df_hist.to_csv(os.path.join(DATA_DIR, "laliga_results_raw.csv"), index=False)
            logger.info(f"💾 Guardado Historial: {len(df_hist)} registros.")

        # Calendario
        df_future = scrape_data(driver, "https://www.flashscore.es/futbol/espana/laliga/calendario/", is_history=False)
        if not df_future.empty:
            df_future.to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)
            logger.info(f"💾 Guardado Calendario: {len(df_future)} partidos.")
        else:
            logger.warning("⚠️ Calendario vacío (puede ser fin de temporada o error de carga).")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()