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
        phrase = transcriber.get_transcription().strip()
        if phrase.lower() in ["quit", "exit", "stop"]:
            print("Stopping transcription and exiting.")
            break
        if not phrase:
            print("Didn't catch that. Please try again.")
            continue

        print(f"You said: {phrase}")
        response = chatbot.get_response(phrase)
        print(f"AI: {response}", end='', flush=True)
        print()

if __name__ == "__main__":
    main()
