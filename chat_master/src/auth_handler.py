# src/auth_handler.py
import requests

FIREBASE_AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"

def login(email, password, firebase_api_key):
    """
    Authenticates the user with Firebase and retrieves an idToken.

    Args:
        email (str): The user's email address.
        password (str): The user's password.
        firebase_api_key (str): The Firebase API key for the EmoEx project.

    Returns:
        str: The idToken if authentication is successful, None otherwise.
    """
    if not firebase_api_key:
        print("Error: Firebase API Key is missing. Cannot authenticate.")
        return None

    payload = {
        "email": email,
        "password": password,
        "returnSecureToken": True
    }
    params = {
        "key": firebase_api_key
    }

    try:
        response = requests.post(FIREBASE_AUTH_URL, params=params, data=payload)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        
        response_data = response.json()
        id_token = response_data.get("idToken")
        
        if id_token:
            return id_token
        else:
            print("Authentication failed: idToken not found in response.")
            print(f"Response: {response_data}")
            return None

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error during authentication: {http_err}")
        try:
            error_details = http_err.response.json()
            print(f"Error details: {error_details.get('error', {}).get('message', 'No specific message')}")
        except ValueError: # If response is not JSON
            print(f"Raw error response: {http_err.response.text}")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"Request error during authentication: {req_err}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred during authentication: {e}")
        return None

if __name__ == '__main__':
    # For testing purposes - requires a .env file with FIREBASE_API_KEY
    # and valid credentials.
    from config_handler import load_config
    config = load_config()
    
    if config.get("FIREBASE_API_KEY"):
        test_email = input("Enter your EmoEx email for testing: ")
        import getpass
        test_password = getpass.getpass("Enter your EmoEx password for testing: ")
        
        print("\nAttempting to authenticate...")
        token = login(test_email, test_password, config["FIREBASE_API_KEY"])
        
        if token:
            print("\nAuthentication Successful!")
            print(f"ID Token (first 30 chars): {token[:30]}...")
        else:
            print("\nAuthentication Failed.")
    else:
        print("FIREBASE_API_KEY not found in config. Cannot run auth test.")
