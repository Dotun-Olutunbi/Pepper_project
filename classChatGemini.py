import os
import google.generativeai as genai

class GeminiChatbot:
    """A chatbot class that uses the Google Gemini API for conversational responses."""
    # --- Corrected __init__ method ---
    def __init__(self, system_instruction_path="system_instruction_for_gemini.txt"):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.model = None
        self.history = []  # We will manage the conversation history manually.
        self.system_instruction = None

        try:
            with open(system_instruction_path, "r") as f:
                self.system_instruction = f.read()
            print("System instruction loaded successfully.")
        except FileNotFoundError:
            print(f"WARNING: System instruction file not found at '{system_instruction_path}'.")
            return
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro-latest')

            # Prime the history list with the system instruction
            self.history = [
                {
                    "role": "user",
                    "parts": [self.system_instruction]
                },
                {
                    "role": "model",
                    "parts": ["Understood. I am Pepper, a friendly robot storyteller. I am ready to begin the experiment and will follow all instructions provided."]
                }
            ]
            print("Gemini chatbot initialized successfully with system persona.")
        else:
            print("ERROR: GOOGLE_API_KEY environment variable not found.")

    # --- Corrected get_response method ---
    def get_response(self, user_prompt: str) -> str:
        if not self.model:
            return "Chatbot is not initialized. Please check your API key or system instruction file."

        try:
            # Add the new user message to our history list
            self.history.append({"role": "user", "parts": [user_prompt]})
            
            # Send the entire, updated history to the model
            response = self.model.generate_content(self.history)
            
            # Add the model's response to the history to maintain context
            if response.candidates and response.candidates[0].content:
                self.history.append(response.candidates[0].content)
                return response.text
            else:
                self.history.pop() # Remove the user's prompt if no valid response
                return "I'm sorry, I could not generate a response for that."

        except Exception as e:
            self.history.pop() # Remove the user's prompt on error
            print(f"An error occurred while getting response from Gemini: {e}")
            return "I'm sorry, I encountered an error. Please try again."
            
    def authenticate(self) -> bool:
        """
        Checks if the chatbot was successfully authenticated with an API key.
        """
        # The chatbot is "authenticated" if the chat session was created.
        return self.model is not None

        
def main():
    """
    This function creates an instance of the GeminiChatbot and simulates a
    conversation in the terminal - just like emoex.
    """
    print("Initializing Gemini Chatbot for terminal simulation...")
    chatbot = GeminiChatbot()

    # Check if the chatbot was initialized correctly
    if not chatbot.authenticate():
        print("Exiting simulation due to authentication failure.")
        return

    print("\nChat session started. Type 'quit', 'exit', or 'stop' to end the conversation.")
    print("-" * 20)

    while True:
        try:
            # Get user input from the terminal
            user_input = input("You: ")

            # Check for exit commands
            if user_input.lower() in ["quit", "exit", "stop"]:
                print("Ending chat session. Goodbye!")
                break
            
            # Get the chatbot's response
            response = chatbot.get_response(user_input)
            
            # Print the chatbot's response
            print(f"Gemini: {response}")

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully
            print("\nEnding chat session. Goodbye!")
            break
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            break

if __name__ == "__main__":
    # This block ensures that the main() function is called only when
    # the script is executed directly from the terminal.
    main()
