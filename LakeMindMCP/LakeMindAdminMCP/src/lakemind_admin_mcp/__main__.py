"""Entry point."""
from __future__ import annotations
import uvicorn
from .config import load_config
from .server import create_server

def main() -> None:
    config = load_config()
    app = create_server(config)
    uvicorn.run(app, host=config.server.host, port=config.server.port)

if __name__ == "__main__":
    main()
