import os
import json
from . import ui

CONFIG_FILE = os.path.expanduser("~/.dockmate_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        ui.error(f"Failed to save config: {e}")

def get_api_key():
    config = load_config()
    api_key = config.get("cohere_api_key")
    if not api_key:
        api_key = ui.ask("Please enter your Cohere API Key to enable the AI engine")
        if api_key:
            config["cohere_api_key"] = api_key
            save_config(config)
            ui.success("API Key securely saved.")
    return api_key

def has_api_key():
    config = load_config()
    return bool(config.get("cohere_api_key"))

def set_api_key(api_key):
    config = load_config()
    config["cohere_api_key"] = api_key
    save_config(config)

def remove_api_key():
    config = load_config()
    if "cohere_api_key" in config:
        del config["cohere_api_key"]
        save_config(config)
