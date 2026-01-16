# Esto permite que desde app.py puedas hacer:
# from src import prepare_data, train_and_evaluate

from .feature_eng import prepare_data
from .models import train_and_evaluate
from .scraper import get_headless_driver

# Versionado del paquete interno
__version__ = '1.0.0'