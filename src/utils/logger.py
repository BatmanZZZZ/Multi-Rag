import logging
from logging.handlers import RotatingFileHandler
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

log_file_path = 'simpla_queries.log'
handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
handler.setFormatter(formatter)

logger.addHandler(handler)