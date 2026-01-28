# Esto permite que desde app.py poder hacer:
# from src import prepare_data, train_and_evaluate

from .feature_eng import prepare_data, prepare_upcoming_matches
from .models import train_and_evaluate
from .stats_scraper import fetch_technical_stats

__version__ = '2.0.0'