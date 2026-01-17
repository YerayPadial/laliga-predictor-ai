import os
import time
import logging
import pandas as pd
from datetime import datetime
from typing import Optional

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
    """Configuración Ultra-Stealth."""
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
    if not text: return ""
    import re
    text = re.sub(r'\s\d+$', '', text) # Quitar números finales
    text = text.replace("SAD", "").strip()
    return text

# --- FUENTE 1: FLASHSCORE ---
def scrape_flashscore(driver, url, is_history) -> pd.DataFrame:
    logger.info(f"Trying Flashscore: {url}")
    data = []
    try:
        driver.get(url)
        # Intentar cerrar cookies rápido
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))).click()
        except: pass

        wait = WebDriverWait(driver, 10)
        # Esperamos filas O mensaje de error
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "div[class*='event__match']") or d.find_elements(By.CLASS_NAME, "footer"))
        
        match_rows = driver.find_elements(By.CSS_SELECTOR, "div[class*='event__match']")
        
        # Si es calendario y no hay filas, asumimos fallo
        if not match_rows and not is_history: return pd.DataFrame()

        for row in match_rows:
            try:
                text = row.text.split('\n')
                if is_history:
                    # Formato Historial: [Estado, Local, Goles, Visitante]
                    # Buscamos la línea con el guión de resultado (ej: "2-1")
                    res_idx = next((i for i, x in enumerate(text) if '-' in x and x[0].isdigit()), -1)
                    if res_idx > 0:
                        data.append({
                            "date": datetime.now().strftime("%Y-%m-%d"),
                            "home_team": clean_team_name(text[res_idx-1]),
                            "away_team": clean_team_name(text[res_idx+1]),
                            "home_score": int(text[res_idx].split('-')[0]),
                            "away_score": int(text[res_idx].split('-')[1])
                        })
                else:
                    # Formato Calendario: [Hora, Local, Visitante] o [Local, Visitante, Hora]
                    if len(text) >= 3:
                        # Asumimos que si hay hora ("14:00"), es el primer elemento o el último
                        data.append({
                            "date_str": text[0] if ':' in text[0] or '.' in text[0] else "Upcoming",
                            "home_team": clean_team_name(text[1]),
                            "away_team": clean_team_name(text[2])
                        })
            except: continue
    except Exception as e:
        logger.warning(f"Flashscore error: {e}")
        return pd.DataFrame()
        
    return pd.DataFrame(data)

# --- FUENTE 2: AS.COM (Backup Robusto) ---
def scrape_backup_as(driver) -> pd.DataFrame:
    """
    Scrapea la JORNADA ACTUAL de AS.com.
    Selector: Busca cualquier 'tr' que tenga nombres de equipos.
    """
    logger.info("🛡️ Activando PLAN B: AS.com (Jornada Actual)...")
    # URL directa a la jornada en curso (más fiable que calendario completo)
    url = "https://resultados.as.com/resultados/futbol/primera/jornada/"
    data = []
    
    try:
        driver.get(url)
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Buscamos filas en la tabla de resultados
        rows = soup.find_all('tr')
        
        for row in rows:
            try:
                # Buscamos celdas que contengan nombres de equipos (clase suele contener 'nombre-equipo')
                teams = row.select('.nombre-equipo')
                
                if len(teams) >= 2:
                    home = clean_team_name(teams[0].get_text(strip=True))
                    away = clean_team_name(teams[1].get_text(strip=True))
                    
                    # Intentamos buscar fecha/hora
                    date_elem = row.select_one('.fecha-evento, .resultado')
                    date_str = date_elem.get_text(strip=True) if date_elem else "Pendiente"
                    
                    data.append({
                        "home_team": home,
                        "away_team": away,
                        "date_str": date_str
                    })
            except: continue
            
    except Exception as e:
        logger.error(f"Error Plan B: {e}")
        
    return pd.DataFrame(data)

# --- RED DE SEGURIDAD (Dummy Data) ---
def create_emergency_fixture():
    """Crea un CSV válido pero 'falso' para que la App no explote."""
    logger.warning("🚨 Activando RED DE SEGURIDAD (Datos Dummy).")
    return pd.DataFrame([{
        "home_team": "Sistema AI",
        "away_team": "Mantenimiento",
        "date_str": datetime.now().strftime("%d.%m. 12:00")
    }])

def main():
    driver = get_headless_driver()
    try:
        # 1. HISTORIAL (Flashscore)
        # Si falla el historial no es crítico, usamos lo que haya o vacío
        df_hist = scrape_flashscore(driver, "https://www.flashscore.es/futbol/espana/laliga/resultados/", True)
        if not df_hist.empty:
            df_hist.to_csv(os.path.join(DATA_DIR, "laliga_results_raw.csv"), index=False)
            logger.info(f"💾 Historial: {len(df_hist)} registros.")

        # 2. CALENDARIO (Crítico para UX)
        df_future = scrape_flashscore(driver, "https://www.flashscore.es/futbol/espana/laliga/calendario/", False)
        
        # Si Flashscore falla, probar AS
        if df_future.empty:
            df_future = scrape_backup_as(driver)
            
        # Si AS también falla, crear Dummy
        if df_future.empty:
            df_future = create_emergency_fixture()
            
        # GUARDAR SIEMPRE
        df_future.to_csv(os.path.join(DATA_DIR, "laliga_fixtures.csv"), index=False)
        logger.info(f"💾 Calendario final guardado: {len(df_future)} partidos.")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()