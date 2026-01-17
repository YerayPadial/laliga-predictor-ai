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
    """Configuración 'Stealth' reforzada para evitar bloqueos en el Calendario."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new") # Modo headless moderno (más indetectable)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    # User Agent de navegador real actualizado
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    # Truco adicional: Eliminar propiedad webdriver del navegador
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def clean_team_name(text: str) -> str:
    """Elimina residuos numéricos al final del nombre."""
    if not text: return ""
    import re
    # Eliminar patrones de números al final (ej: "Real Oviedo 2")
    text = re.sub(r'\s\d+$', '', text) 
    return text.strip()

def safe_extract_text(row, selectors: List[str]) -> Optional[str]:
    """
    Intenta extraer texto de una lista de selectores.
    Prueba uno a uno hasta encontrar texto válido.
    """
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

def handle_cookies(driver):
    """Intenta cerrar el banner de cookies agresivamente."""
    try:
        # Espera breve para ver si sale el popup
        WebDriverWait(driver, 4).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        ).click()
        logger.info("🍪 Cookies aceptadas.")
        time.sleep(1) # Dejar que la página respire tras el click
    except:
        logger.info("ℹ️ No se detectó banner de cookies o ya estaba cerrado.")

def scrape_data(driver: webdriver.Chrome, url: str, is_history: bool) -> pd.DataFrame:
    logger.info(f"Iniciando Scraping ({'HISTORIAL' if is_history else 'CALENDARIO'}): {url}")
    data = []
    
    try:
        driver.get(url)
        handle_cookies(driver)
        
        wait = WebDriverWait(driver, 20) # Aumentamos tiempo de espera a 20s
        
        # ESTRATEGIA DE ESPERA DINÁMICA
        # En lugar de esperar un contenedor específico, esperamos a que haya AL MENOS un partido o el footer
        try:
            wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "div[class*='event__match']") or d.find_elements(By.CLASS_NAME, "footer"))
        except:
            logger.warning("⚠️ Timeout inicial. Intentando recarga de página...")
            driver.refresh()
            time.sleep(5)
            handle_cookies(driver)

        # Pausa de seguridad para carga de scripts
        time.sleep(3) 

        # Buscar filas de partidos
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        if not match_rows:
            # Fallback: Intentar selector alternativo por si cambió la clase
            match_rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'event__match')]")

        logger.info(f"Detectados {len(match_rows)} partidos.")

        # Selectores
        home_sels = [".event__participant--home", ".event__homeParticipant", ".wcl-participant_..."] 
        away_sels = [".event__participant--away", ".event__awayParticipant", ".wcl-participant_..."]
        
        # Solo historial
        score_home_sels = [".event__score--home", ".event__part--home"]
        score_away_sels = [".event__score--away", ".event__part--away"]
        
        # Solo calendario
        time_sels = [".event__time"]

        for row in match_rows:
            try:
                home = safe_extract_text(row, home_sels)
                away = safe_extract_text(row, away_sels)
                
                if not home or not away: continue

                match_info = {"home_team": home, "away_team": away}

                if is_history:
                    s_home = safe_extract_text(row, score_home_sels)
                    s_away = safe_extract_text(row, score_away_sels)
                    
                    if s_home and s_away and s_home.isdigit() and s_away.isdigit():
                        match_info["date"] = datetime.now().strftime("%Y-%m-%d")
                        match_info["home_score"] = int(s_home)
                        match_info["away_score"] = int(s_away)
                        data.append(match_info)
                else:
                    # Calendario
                    m_time = safe_extract_text(row, time_sels) 
                    match_info["date_str"] = m_time if m_time else datetime.now().strftime("%d.%m. 00:00")
                    data.append(match_info)

            except Exception:
                continue

    except Exception as e:
        logger.error(f"❌ Error durante el scraping: {e}")
    
    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    try:
        # 1. Historial
        df_hist = scrape_data(driver, "https://www.flashscore.es/futbol/espana/laliga/resultados/", is_history=True)
        if not df_hist.empty:
            path_hist = os.path.join(DATA_DIR, "laliga_results_raw.csv")
            df_hist.to_csv(path_hist, index=False)
            logger.info(f"💾 Guardado Historial: {len(df_hist)} registros.")

        # 2. Calendario (CRÍTICO: Aquí fallaba antes)
        df_future = scrape_data(driver, "https://www.flashscore.es/futbol/espana/laliga/calendario/", is_history=False)
        
        path_fix = os.path.join(DATA_DIR, "laliga_fixtures.csv")
        if not df_future.empty:
            df_future.to_csv(path_fix, index=False)
            logger.info(f"💾 Guardado Calendario: {len(df_future)} partidos.")
        else:
            logger.warning("⚠️ Calendario vacío. Creando archivo vacío para evitar error 403 en Streamlit.")
            # Crear archivo con cabeceras aunque esté vacío para que app.py no falle
            pd.DataFrame(columns=["home_team", "away_team", "date_str"]).to_csv(path_fix, index=False)
            
    finally:
        driver.quit()
        logger.info("Navegador cerrado.")

if __name__ == "__main__":
    main()