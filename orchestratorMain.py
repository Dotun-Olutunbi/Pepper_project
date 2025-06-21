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
    user_transcriptions = []
    conversation_history = []
    max_wait_time = 15  # seconds to wait for user voice input
    wait_start_time = None
    prompted = False

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
    
    # print("Authentication successful. Starting transcription. \n(Say 'quit', 'exit', or 'stop' to end conversation)")
    
    while True:
        # print("Hi, say something...")
        # Initialising total and transcription time calculation
        total_time = total_start_time = time.time()
        if wait_start_time is None:
            wait_start_time = time.time()

        transcriber_start_time = time.time() #To calculate transcription time lag
        phrase = transcriber.get_transcription()#.strip()
        transcriber_end_time = time.time()
        if phrase.lower() in ["quit", "exit", "stop"]:
            print("Stopping transcription and exiting.")
            break
        if phrase:
            user_transcriptions.append(phrase)
            full_transcription = " ".join(user_transcriptions)
            wait_start_time = None  # Reset wait time after receiving input
            prompted = False
            # if full_transcription:
            #     # Storing the transcription in history, so that it can be used as a reference
            #     conversation_history.append(f"You said: {full_transcription}\n")
        else:
            # This is when the transcription should be sent to bot
            print("Silence.... Ending conversation")
            full_transcription = " ".join(user_transcriptions)
            if not full_transcription.strip():
                if not prompted:
                    print("I didn't hear you say a word. Waiting for you... but also counting down to end conversation.")
                    prompted = True
                if time.time() - wait_start_time > max_wait_time:
                    print(f"No input detected for more than {max_wait_time}s. Ending conversation.")
                    break
                continue
            if full_transcription.strip():
                conversation_history.append(f"You said: {full_transcription}\n")
            # Print the full transcription and send it to the chatbo
                print(f"You said: {full_transcription}", end='', flush=True)
                #Chatbot timing
                chatbot_start_time = time.time()
                response = chatbot.get_response(full_transcription)
                print(f"AI: {response}", end='', flush=True)
                conversation_history.append(f"AI: {response}\n")
                user_transcriptions.clear()  # Clear transcriptions after sending to chatbot

                chatbot_end_time = time.time()
                print(f"[Transcription Lag: {transcriber_end_time - transcriber_start_time:.2f} seconds]")
                print(f"[Chatbot Lag: {chatbot_end_time - chatbot_start_time:.2f} seconds]")
                print(f"[Total Lag: {time.time() - total_start_time:.2f} seconds]")
                continue
            else:
                print("Silence detected. Waiting for you to say something...")
    print("\nFull Conversation: ")
    for entry in conversation_history:
        print(entry)

if __name__ == "__main__":
    main()
