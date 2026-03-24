"""
Main — точка входа приложения.

## Бизнес-контекст
Запускает FastAPI сервер с настроенным приложением.
"""

import logging

from api import app
from core.config import configs
import uvicorn


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, configs.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=configs.LOG_LEVEL.lower())
