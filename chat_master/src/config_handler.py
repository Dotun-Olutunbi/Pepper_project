# src/config_handler.py
import os
from dotenv import load_dotenv

def load_config():
    """
    Loads configuration from the .env file.

    Returns:
        dict: A dictionary containing configuration values.
              Keys: "FIREBASE_API_KEY", "EMOEX_PRODUCT_ID", "EMOEX_EMAIL" (optional)
    """
    # Get the directory of the current script (src/)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the parent directory (project root)
    project_root = os.path.dirname(current_dir)
    # Construct the path to the .env file
    dotenv_path = os.path.join(project_root, '.env')

    if not os.path.exists(dotenv_path):
        print(f"Warning: .env file not found at {dotenv_path}")
        print("Please create it.")
        # Return default/empty values or raise an error, depending on desired behavior
        return {
            "FIREBASE_API_KEY": None,
            "EMOEX_PRODUCT_ID": None,
            "EMOEX_EMAIL": None,
            "EMOEX_PASSWORD": None,
        }

    load_dotenv(dotenv_path=dotenv_path)

    config = {
        "FIREBASE_API_KEY": os.getenv("FIREBASE_API_KEY"),
        "EMOEX_PRODUCT_ID": os.getenv("EMOEX_PRODUCT_ID"),
        "EMOEX_EMAIL": os.getenv("EMOEX_EMAIL"), # This can be None if not set
        "EMOEX_PASSWORD": os.getenv("EMOEX_PASSWORD") # This can be None if not set
    }

    # Validate required configurations
    if not config["FIREBASE_API_KEY"]:
        print("Error: FIREBASE_API_KEY not found in .env file.")
        # exit(1) # Or raise an exception
    if not config["EMOEX_PRODUCT_ID"]:
        print("Error: EMOEX_PRODUCT_ID not found in .env file.")
        # exit(1) # Or raise an exception
        
    return config

if __name__ == '__main__':
    # For testing purposes
    config = load_config()
    print("Loaded Configuration:")
    for key, value in config.items():
        print(f"{key}: {value}")
