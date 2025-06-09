import time
import qi
import argparse
from classTranscriber import Transcriber
from chat_master.src.classChatbot import Chatbot

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
    parser.add_argument("--port", type=int, default=9559,
                        help="Naoqi port number")

    args = parser.parse_args()
    #Connection to Pepper's NAOqi session
    try:
        print(f"Connecting to Pepper at {args.ip}:{args.port}...")
        session = qi.Session()
        session.connect(args.ip + ":" + str(args.port))
        print("Connected to Pepper's NAOqi session.")
    except Exception as e:
        print(f"Could not connect to Pepper at {args.ip}:{args.port}. Please check the IP and port.")
        return
    print("Connected to Pepper successfully.")

    # Initialize Pepper's TextToSpeech service
    tts = session.service("ALTextToSpeech")
    tts.setLanguage("English")  # Set language to English
    tts.setVolume(0.5)  # Set volume to 50%
    # tts.setParameter("speed", 100)  # Set speech speed to 100%
    # tts.setParameter("pitch", 100)  # Set pitch to normal
    # tts.say("Hello, I am Pepper. Can you tell me what you see in the image shown on my tablet?")

    # Initialize Pepper's Tablet service
    def show_on_tablet():
        try:
            tablet_service = session.service("ALTabletService")
            tablet_service.showWebview("http://localhost:8000")  # Assuming a local web server is running
        except Exception as e:
            print("Could not connect to ALTabletService. Tablet features may not be available.")
            print(f"Error: {e}")

    try:
        tablet_service = session.service("ALTabletService")
        tts.say("It's a short story. Take a look at the first scene. What do you see?")
        tablet_service.showImage(f"http://198.18.0.1/home/nao/pictures/The Fisherman and The Cat _Scene1n2.jpg")  # Assuming a local web server is running
    except Exception as e:
        print("Could not connect to ALTabletService. Tablet features may not be available.")
        print(f"Error: {e}")

    # Initialize the transcriber
    transcriber = Transcriber(
        model="small",
        energy_threshold=1000,
        record_timeout=2,
        phrase_timeout=3,
        default_microphone="HDA Intel PCH: ALC3266 Analog (hw:0,0)"
    )

    chatbotAlive = Chatbot()

    if not chatbotAlive.authenticate():
        print("Authentication failed. Exiting.")
        return
    # tts.say("If you don't like to talk now, \nJust say 'quit' or 'stop' to end our conversation)")

    time.sleep(2)  # Give some time for the user to prepare
    while True:
        phrase = transcriber.get_transcription().strip()
        if phrase.lower() in ["quit", "exit", "stop"]:
            print("Stopping transcription and exiting.")
            print("Goodbye!")
            tts.say("Goodbye!")
            break
        if not phrase:
            print("Didn't catch that. Please try again.")
            tts.say("I didn't catch that. Please try again.")
            continue

        print(f"You said: {phrase}")
        response = chatbotAlive.get_response(phrase)
        print(f"AI: {response}", end='', flush=True)
        tts.say(response)

if __name__ == "__main__":
    main()