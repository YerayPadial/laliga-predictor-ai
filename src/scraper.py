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
from bs4 import BeautifulSoup 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def get_headless_driver() -> webdriver.Chrome:
    """Configuración Stealth Anti-Bloqueo."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled") 
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def clean_team_name(text: str) -> str:
    """Limpieza estándar de nombres."""
    if not text: return ""
    import re
    # Elimina números finales y textos extra
    text = re.sub(r'\s\d+$', '', text)
    text = text.replace("SAD", "").strip()
    return text

def scrape_backup_as(driver) -> pd.DataFrame:
    """
    PLAN B: Scraper de AS.com (Estructura estática y fiable).
    Se activa si Flashscore falla.
    """
    logger.info("🛡️ Activando PLAN B: Scraping de AS.com...")
    backup_url = "https://resultados.as.com/resultados/futbol/primera/calendario/"
    data = []
    
    try:
        driver.get(backup_url)
        time.sleep(2) # Espera breve para carga
        
        # Usamos BeautifulSoup para parsear la tabla estática (más rápido y robusto que Selenium)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Buscamos las filas de la tabla de calendario
        # AS usa tablas por jornada o una tabla grande. Buscamos filas genéricas de eventos.
        rows = soup.select('tr.row-evento, tr[itemtype="http://schema.org/SportsEvent"]')
        
        if not rows:
            # Selector alternativo para la tabla general
            rows = soup.select('.tabla-datos tbody tr')

        logger.info(f"AS.com: Encontradas {len(rows)} filas potenciales.")

        for row in rows:
            try:
                # Extracción segura usando selectores CSS de AS
                local = row.select_one('.local .nombre-equipo, .col-equipo-local .nombre-equipo')
                visitante = row.select_one('.visitante .nombre-equipo, .col-equipo-visitante .nombre-equipo')
                fecha = row.select_one('.fecha-evento, .col-fecha')
                
                if local and visitante:
                    t_local = clean_team_name(local.get_text(strip=True))
                    t_visit = clean_team_name(visitante.get_text(strip=True))
                    
                    # Fecha: AS suele poner "18/01 21:00" o "Sáb 18"
                    str_fecha = fecha.get_text(strip=True) if fecha else "Pendiente"
                    
                    data.append({
                        "home_team": t_local,
                        "away_team": t_visit,
                        "date_str": str_fecha # Guardamos formato original para parsearlo luego
                    })
            except:
                continue
                
    except Exception as e:
        logger.error(f"Error en Plan B (AS.com): {e}")
        
    return pd.DataFrame(data)

def scrape_flashscore(driver, url, is_history) -> pd.DataFrame:
    """Intento principal con Flashscore."""
    logger.info(f"Intentando Flashscore ({'Historial' if is_history else 'Calendario'})...")
    data = []
    try:
        driver.get(url)
        
        # Cookies
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except: pass

        wait = WebDriverWait(driver, 10)
        # Espera dinámica: O filas de partido O footer (si no hay partidos)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "div[class*='event__match']") or d.find_elements(By.CLASS_NAME, "footer"))
        
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        if not match_rows and not is_history:
            raise Exception("Calendario vacío en Flashscore") # Forzar salto al Plan B

        for row in match_rows:
            try:
                text = row.text.split('\n')
                # Lógica simplificada basada en posición de texto (más rápida)
                # Flashscore row text suele ser: "Time/Status", "Home", "Score", "Away"
                if is_history:
                    # Buscamos filas con marcador
                    if len(text) >= 4 and text[2].replace('-','').isdigit(): 
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "home_team": clean_team_name(text[1]),
                            "away_team": clean_team_name(text[3]),
                            "home_score": int(text[2].split('-')[0]),
                            "away_score": int(text[2].split('-')[1])
                        })
                else:
                    # Calendario: Buscamos filas sin marcador
                    if len(text) >= 3:
                        data.append({
                            "date_str": text[0], # Hora/Fecha
                            "home_team": clean_team_name(text[1]),
                            "away_team": clean_team_name(text[2])
                        })
            except: continue
            
    except Exception as e:
        logger.warning(f"Fallo parcial en Flashscore: {e}")
        if not is_history: return pd.DataFrame() # Devolver vacío para activar backup
        
    return pd.DataFrame(data)

def main():
    driver = get_headless_driver()
    try:
        # 1. HISTORIAL (Flashscore suele funcionar bien aquí)
        df_hist = scrape_flashscore(driver, "https://www.flashscore.es/futbol/espana/laliga/resultados/", True)
        if not df_hist.empty:
            df_hist.to_csv(os.path.join(DATA_DIR, "laliga_results_raw.csv"), index=False)
            logger.info(f"✅ Historial guardado: {len(df_hist)} partidos.")

        # 2. CALENDARIO (Aquí es donde falla, preparamos el Backup)
        df_future = scrape_flashscore(driver, "https://www.flashscore.es/futbol/espana/laliga/calendario/", False)
        
        if df_future.empty:
            logger.warning("⚠️ Flashscore falló en Calendario. Ejecutando PLAN B (AS.com)...")
            df_future = scrape_backup_as(driver)
        
        if not df_future.empty:
            df_future.to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)
            logger.info(f"✅ Calendario guardado: {len(df_future)} partidos.")
        else:
            # Archivo vacío de seguridad para no romper Streamlit
            logger.error("❌ Ambos scrapers fallaron. Creando archivo vacío de seguridad.")
            pd.DataFrame(columns=["home_team", "away_team", "date_str"]).to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()