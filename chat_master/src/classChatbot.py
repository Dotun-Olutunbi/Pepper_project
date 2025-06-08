import getpass
from .config_handler import load_config
from .auth_handler import login
from .emoex_client import stream_chat_response

class Chatbot:
    """A class to handle the chatbot functionality for EmoEx AI Terminal Chat."""
    def __init__(self, 
                 FIREBASE_API_KEY="FIREBASE_API_KEY", 
                 EMOEX_PRODUCT_ID="EMOEX_PRODUCT_ID", 
                 EMOEX_EMAIL="EMOEX_EMAIL", EMOEX_PASSWORD="EMOEX_PASSWORD"):
        self.config = load_config()
        self.firebase_api_key = self.config.get(FIREBASE_API_KEY)
        self.product_id = self.config.get(EMOEX_PRODUCT_ID)
        self.default_email = self.config.get(EMOEX_EMAIL)
        self.default_password = self.config.get(EMOEX_PASSWORD)
        self.id_token = None

    def authenticate(self):
        if not self.firebase_api_key or not self.product_id:
            print("Critical configuration (FIREBASE_API_KEY or EMOEX_PRODUCT_ID) missing.")
            print("Please check your .env file.")
            return False
        
        # Get credentials
        print("Welcome to EmoEx (modified) AI Terminal Chat!")
        if self.default_email:
            email = self.default_email
            print(f"Using email from .env: {email}")
        else:
            email = input("Enter your EmoEx email: ")

        if self.default_password:
            password = self.default_password
            print("Using password from .env (not recommended for security reasons).")
        else:
            password = getpass.getpass("Enter your EmoEx password: ")

        print("\nAuthenticating...")
        self.id_token = login(email, password, self.firebase_api_key)
        if not self.id_token:
            print("Login failed. Please check your credentials and API key setup.")
            return
        print("Authentication successful. Let's chat now...")
        print("You may type 'quit', 'exit', or 'bye' to end this session.\n")
        return True
    
    def get_response(self, user_input):
        """Getting a response from the EmoEx AI based on user input."""
        if not self.id_token:
            raise RuntimeError("You need to authenticate first.")
        response = ""
        for chunk in stream_chat_response(
            self.id_token,
            self.product_id,
            user_input):
            print(chunk, end='', flush=True)
            response += chunk
        print() # For a new line after each chunk
        return response.strip()
    
    def chat_loop(self):
        """Main chat loop to interact with the user."""
        while True:
            try:
                user_input = input("You: ")
                if user_input.lower() in ["quit", "exit", "bye"]:
                    print("Stopping conversation. Bye!")
                    break
                if not user_input.strip():
                    print("Please say something meaningful.")
                    continue
                print(f"AI: ", end='', flush=True)
                # Get response from the EmoEx AI
                response = self.get_response(user_input)

            #     print("AI: ", end='', flush=True)
            # has_streamed_content = False
            # for chunk in stream_chat_response(id_token, product_id, user_input):
            #     print(chunk, end='', flush=True)
            #     if chunk.strip(): # Check if the chunk contains actual content
            #         has_streamed_content = True

            except KeyboardInterrupt:
                print("\nYou interrupted with your keyboard. Goodbye!")
                break
            except Exception as e:
                print(f"An error occurred: {e}")
                continue


            
                
if __name__ == "__main__":
    chatbot = Chatbot()
    if chatbot.authenticate():
        chatbot.chat_loop()
    else:
        print("Authentication failed. Exiting the chatbot.")

        
