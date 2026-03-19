"""
FastAPI app loader.

## Traceability
Infrastructure.
"""

from fastapi import FastAPI

from .config import configs
from .database import DatabaseConnection

TITLE = configs.SERVICE_NAME
DESCRIPTION = "Sync service for superconductivity papers ingestion and processing"
VERSION = configs.SERVICE_VERSION

app = FastAPI(
    title=TITLE,
    description=DESCRIPTION,
    version=VERSION,
    debug=configs.MODE_DEBUG,
)

db_connect = DatabaseConnection()
