import os
import time
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Configuración de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    """Configura Chrome Headless con opciones anti-detección básicas."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080") # Importante para forzar versión desktop
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def safe_extract_text(row, selectors: List[str]) -> Optional[str]:
    """Intenta extraer texto probando una lista de selectores CSS en orden."""
    for selector in selectors:
        try:
            elements = row.find_elements(By.CSS_SELECTOR, selector)
            if elements and elements[0].text.strip():
                return elements[0].text.strip()
        except:
            continue
    return None

def scrape_historical_results(driver: webdriver.Chrome, url: str) -> pd.DataFrame:
    logger.info(f"Iniciando scraping de resultados: {url}")
    data = []
    
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 20)
        
        # Esperamos a que cargue el contenedor principal
        # Flashscore usa IDs dinámicos, buscamos clases generales de contenedores deportivos
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".sportName, .leagues--static")))
        
        # Damos un respiro para ejecución de JS
        time.sleep(3) 

        # Estrategia de búsqueda de filas: Buscamos clases que contengan 'event__match'
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        if not match_rows:
            logger.warning("No se encontraron filas con el selector estándar. Intentando fallback...")
            match_rows = driver.find_elements(By.XPATH, "//div[contains(@class, 'event__match')]")

        logger.info(f"Encontrados {len(match_rows)} partidos potenciales. Procesando...")

        success_count = 0
        error_count = 0
        
        # Selectores de fallback (Desktop vs Mobile vs Old versions)
        home_selectors = [".event__participant--home", ".event__homeParticipant", ".wcl-participant_..."] 
        away_selectors = [".event__participant--away", ".event__awayParticipant", ".wcl-participant_..."]
        score_home_selectors = [".event__score--home", ".event__part--home"]
        score_away_selectors = [".event__score--away", ".event__part--away"]

        for i, row in enumerate(match_rows):
            try:
                # Extracción con fallback
                home_team = safe_extract_text(row, home_selectors)
                away_team = safe_extract_text(row, away_selectors)
                score_home = safe_extract_text(row, score_home_selectors)
                score_away = safe_extract_text(row, score_away_selectors)
                
                # Validación estricta
                if home_team and away_team and score_home and score_away:
                    if score_home.isdigit() and score_away.isdigit():
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"), # Placeholder
                            "home_team": home_team,
                            "away_team": away_team,
                            "home_score": int(score_home),
                            "away_score": int(score_away)
                        })
                        success_count += 1
                else:
                    # Si falla, imprimimos el HTML de la PRIMERA fila fallida para depurar
                    if error_count == 0:
                        logger.warning(f"DEBUG HTML Fila Fallida: {row.get_attribute('outerHTML')[:500]}...")
                    error_count += 1
                    
            except Exception as e:
                error_count += 1
                continue

        logger.info(f"Procesamiento finalizado. Éxitos: {success_count}, Fallos/Futuros: {error_count}")

    except Exception as e:
        logger.error(f"Error fatal en scraping: {e}")
        # Captura de pantalla en caso de error fatal (opcional si se configura artefactos)
        # driver.save_screenshot("debug_error.png")

    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    
    # URL directa a RESULTADOS (No calendario, RESULTADOS)
    URL_RESULTS = "https://www.flashscore.es/futbol/espana/laliga/resultados/"
    
    try:
        df_results = scrape_historical_results(driver, URL_RESULTS)
        
        if not df_results.empty:
            path = os.path.join(DATA_DIR, "laliga_results_raw.csv")
            df_results.to_csv(path, index=False)
            logger.info(f"✅ ÉXITO: Datos guardados en {path} ({len(df_results)} registros)")
        else:
            logger.error("❌ ERROR: El DataFrame está vacío. Revisa los logs de DEBUG HTML arriba.")
            # Crear archivo vacío para no romper el pipeline, pero avisando
            # Opcional: raise Exception("Scraping fallido") para detener GitHub Actions
            
    finally:
        driver.quit()
        logger.info("Driver cerrado.")

if __name__ == "__main__":
    main()