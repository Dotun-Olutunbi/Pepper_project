"""Main orchestrator script for voice-driven AI chat.

This script connects the Transcriber (speech-to-text) and Chatbot (AI response) classes.
It listens for spoken input from the user, transcribes it to text, sends the text to the chatbot,
and prints the AI's response in the terminal. The conversation continues until the user says
'quit', 'exit', or 'stop'.

Workflow:
    1. Initialize Transcriber and Chatbot.
    2. Authenticate the chatbot user.
    3. Enter a loop:
        a. Listen for a spoken phrase.
        b. Transcribe and print the phrase.
        c. Send the phrase to the chatbot and print the AI's response.
        d. Exit on 'quit', 'exit', or 'stop'.

Dependencies:
    - classTranscriber.py: Provides the Transcriber class for speech recognition.
    - chat_master/src/classChatbot.py: Provides the Chatbot class for AI interaction."""

import time
from classTranscriber import Transcriber
from chat_master.src.classChatbot import Chatbot

def main():
    # Initialize the transcriber
    transcriber = Transcriber(
        model="small",
        energy_threshold=1000,
        record_timeout=2,
        phrase_timeout=3,
        default_microphone="HDA Intel PCH: ALC3266 Analog (hw:0,0)"
    )
    
    chatbot = Chatbot()

    if not chatbot.authenticate():
        print("Authentication failed. Exiting.")
        return
    
    print("Authentication successful. Starting transcription. \n(Say 'quit', 'exit', or 'stop' to end conversation)")
    while True:
        # print("Hi, say something...")
        # Initialising total and transcription time calculation
        total_time = total_start_time = time.time()

        transcriber_start_time = time.time()
        phrase = transcriber.get_transcription().strip()
        transcriber_end_time = time.time()
        if phrase.lower() in ["quit", "exit", "stop"]:
            print("Stopping transcription and exiting.")
            break
        if not phrase:
            print("Didn't catch that. Please try again.")
            continue

        print(f"You said: {phrase}")
        #Chatbot timing
        chatbot_start_time = time.time()
        response = chatbot.get_response(phrase)
        print(f"AI: {response}", end='', flush=True)
        print()

        chatbot_end_time = time.time()
        print(f"[Transcription Lag: {transcriber_end_time - transcriber_start_time:.2f} seconds]")
        print(f"[Chatbot Lag: {chatbot_end_time - chatbot_start_time:.2f} seconds]")
        print(f"[Total Lag: {time.time() - total_start_time:.2f} seconds]")

if __name__ == "__main__":
    main()
