import os
import sys
from loguru import logger

IN_CONTAINER = os.getenv("IN_CONTAINER", False)
if not IN_CONTAINER:
    from dotenv import load_dotenv
    load_dotenv()

class Env:
    IN_CONTAINER = IN_CONTAINER
    LOG_LEVEL = os.getenv("MEURAL_USERNAME", "LOG_LEVEL")

    IMAGE_DIR = os.path.join(os.getcwd(), "images") if not IN_CONTAINER else "/images"
    CONFIG_DIR = os.path.join(os.getcwd(), "config") if not IN_CONTAINER else "/config"

    MEURAL_USERNAME = os.getenv("MEURAL_USERNAME", None)
    MEURAL_PASSWORD = os.getenv("MEURAL_PASSWORD", None)
    UPDATE_FREQUENCY_MINS = os.getenv("UPDATE_FREQUENCY_MINS", None)

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
logger.add(sys.stderr, level=Env.LOG_LEVEL, colorize=True)