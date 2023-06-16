import os
import sys
import time
from loguru import logger


IN_CONTAINER = os.getenv("IN_CONTAINER", False)
if not IN_CONTAINER:
    from dotenv import load_dotenv
    load_dotenv()

class Env:
    IN_CONTAINER = IN_CONTAINER
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    VERIFY_SSL_CERTS = False if os.getenv("VERIFY_SSL_CERTS", "false").lower() == "false" else True

    IMAGE_DIR = os.path.join(os.getcwd(), "images") if not IN_CONTAINER else "/images"
    CONFIG_DIR = os.path.join(os.getcwd(), "config") if not IN_CONTAINER else "/config"

    DRY_RUN = False if os.getenv("DRY_RUN", "false").lower() == "false" else True
    MEURAL_USERNAME = os.getenv("MEURAL_USERNAME", None)
    MEURAL_PASSWORD = os.getenv("MEURAL_PASSWORD", None)
    UPDATE_FREQUENCY_MINS = os.getenv("UPDATE_FREQUENCY_MINS", None)

    DELETE_FROM_ICLOUD_PLAYLIST_NAME = "Delete From iCloud"

    @classmethod
    def validate_environment(cls):
        # First check directories
        directories = [cls.IMAGE_DIR, cls.CONFIG_DIR]
        for directory in directories:
            if not os.path.isdir(directory):
                raise ValueError(f"{directory} directory was not found")

        # Second check env vars
        env_vars = [cls.MEURAL_USERNAME, cls.MEURAL_PASSWORD, cls.UPDATE_FREQUENCY_MINS]
        for env_var in env_vars:
            if env_var is None:
                name_as_str = f'{env_var=}'.split('=')[0]
                raise ValueError(f"{name_as_str} Environment variable not set")
        logger.debug("Environment is valid")

# Set up loguru
try:
    logger.remove(0)
except ValueError:
    pass

loguru_format = str(
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | <level>{message}</level>",
)

logger.add(sys.stderr, level=Env.LOG_LEVEL, format=loguru_format, colorize=True)

def halt_with_error(error_msg):
    logger.error(error_msg)
    logger.info("MeuralCanvas-iCloudSync has been halted. Restart the container to resume.")
    while True:
        time.sleep(60)