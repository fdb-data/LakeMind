from __future__ import annotations

import uvicorn

from .app import create_app

app = create_app()


def main():
    from .config import load_config
    cfg = load_config()
    uvicorn.run(app, host=cfg.server.host, port=cfg.server.port)


if __name__ == "__main__":
    main()
