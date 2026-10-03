from __future__ import annotations

import logging

import uvicorn

from control_layer.infrastructure.settings import Settings
from control_layer.presentation.app import create_app

settings = Settings()
app = create_app(settings)


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=settings.port, log_level="info")


if __name__ == "__main__":
    run()
