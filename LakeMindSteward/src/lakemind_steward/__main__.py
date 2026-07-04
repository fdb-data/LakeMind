"""Entry point."""
from __future__ import annotations
import uvicorn
from .config import load_config

def main() -> None:
    config = load_config()
    uvicorn.run("lakemind_steward.server:app", host=config.server.host, port=config.server.port)

if __name__ == "__main__":
    main()
