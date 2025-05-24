import os
import logging

import json
import requests

STUDY_CONFIG = os.getenv("STUDY_CONFIG", "stage-program")
CONFIG_CACHE_PATH = "/tmp/study_config.json"

dynamic_config = None


def get_dynamic_config():
    global dynamic_config
    if dynamic_config is not None:
        logging.debug(
            "Returning cached dynamic config for %s at version %s"
            % (STUDY_CONFIG, dynamic_config["version"])
        )
        return dynamic_config

    # Try reading from local cache
    if os.path.exists(CONFIG_CACHE_PATH):
        try:
            with open(CONFIG_CACHE_PATH, "r") as f:
                dynamic_config = json.load(f)
                logging.debug(
                    "Loaded config from local cache at %s with version %s"
                    % (CONFIG_CACHE_PATH, dynamic_config.get("version", "unknown"))
                )
                return dynamic_config
        except Exception as e:
            logging.warning(f"Failed to read config from local cache: {e}")

    # If not cached locally, download from GitHub
    download_url = f"https://raw.githubusercontent.com/fourstep-dev/fourstep-configs/main/configs/test.{STUDY_CONFIG}.fourstep.json"
    logging.debug("No local config found, downloading from %s" % download_url)
    try:
        r = requests.get(download_url)
        if r.status_code == 200:
            dynamic_config = r.json()

            # Ensure the parent directory exists before writing
            os.makedirs(os.path.dirname(CONFIG_CACHE_PATH), exist_ok=True)
            with open(CONFIG_CACHE_PATH, "w") as f:
                json.dump(dynamic_config, f)
            logging.debug(
                f"Successfully downloaded and cached config with version {dynamic_config['version']}"
            )
            return dynamic_config
        else:
            logging.warning(f"Unable to download config: HTTP {r.status_code}")
            return {}
    except Exception as e:
        logging.error(f"Error while downloading config: {e}")
        return {}
