import logging
import sys

from dotenv import load_dotenv

from .bot import build_application
from .config import ConfigError, load, load_env
from .store import Store


def main():
    logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    load_dotenv()
    try:
        env = load_env()
        cfg = load(env.config_path)
    except ConfigError as exc:
        sys.exit(f"configuration error: {exc}")
    build_application(cfg, env, Store(env.database_path)).run_polling()


if __name__ == "__main__":
    main()
