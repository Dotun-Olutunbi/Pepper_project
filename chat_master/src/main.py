# src/main.py
import getpass
import sys
from config_handler import load_config
from auth_handler import login
from emoex_client import stream_chat_response

def main():
    """
    Main function to run the EmoEx AI Terminal Chat application.
    """
    print("Welcome to EmoEx AI Terminal Chat!")

    # Load configuration
    config = load_config()
    firebase_api_key = config.get("FIREBASE_API_KEY")
    product_id = config.get("EMOEX_PRODUCT_ID")
    default_email = config.get("EMOEX_EMAIL") # Can be None
    default_password = config.get("EMOEX_PASSWORD") # Can be None

    if not firebase_api_key or not product_id:
        print("Critical configuration (FIREBASE_API_KEY or EMOEX_PRODUCT_ID) missing.")
        print("Please check your .env file.")
        return

    # Get credentials
    if default_email:
        email = default_email
        print(f"Using email from .env: {email}")
    else:
        email = input("Enter your EmoEx email: ")

    if default_password:
        password = default_password
        print("Using password from .env (not recommended for security reasons).")
    else:
        password = getpass.getpass("Enter your EmoEx password: ")


    # Authenticate
    print("\nAuthenticating...")
    id_token = login(email, password, firebase_api_key)

    if not id_token:
        print("Login failed. Please check your credentials and API key setup.")
        return

    print("Authentication successful. You can start chatting now.")
    print("Type 'quit', 'exit', or 'bye' to end the session.\n")

    # Chat loop
    while True:
        try:
            print("You: ", end='', flush=True)
            user_input = input()
            # checks for empty input or just whitespace - for debugging purposes
            # print(f"[DEBUG] Received from captor: {user_input}", flush=True)
            if user_input.lower() in ["quit", "exit", "bye"]:
                print("Exiting chat. Goodbye!")
                break

            if not user_input.strip():
                continue

            print("AI: ", end='', flush=True)
            has_streamed_content = False
            for chunk in stream_chat_response(id_token, product_id, user_input):
                print(chunk, end='', flush=True)
                if chunk.strip(): # Check if the chunk contains actual content
                    has_streamed_content = True
            
            # Ensure a newline after the AI's full response or if no content was streamed but processing occurred.
            print() # Moves to the next line for the user's prompt.
            if not has_streamed_content:
                # This case might happen if only control events were received or an error occurred
                # that was yielded as a printable message but didn't set has_streamed_content.
                # The newline above should handle most cases.
                # If an error message was yielded and printed, it's already handled.
                pass


        except KeyboardInterrupt:
            print("\nExiting chat due to KeyboardInterrupt. Goodbye!")
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred in the chat loop: {e}")
            # Optionally, decide if the loop should continue or break
            # break

if __name__ == "__main__":
    # Create __init__.py in src if it doesn't exist, for package imports
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    init_file = os.path.join(current_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            pass # Create an empty __init__.py
            
    main()
