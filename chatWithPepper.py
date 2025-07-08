import time
import qi
import argparse
from datetime import datetime
from classTranscriber import Transcriber
from chat_master.src.classChatbot import Chatbot
# from classChatGemini import GeminiChatbot as Chatbot

def show_on_tablet(session, tts):
    # A experimental run - URL on Pepper’s internal webserver
    app_id = "my_fisherman_story_app"
    image_file = "The_fisherman_and_the_cat_1n2.jpg"  # Change to your image file
    picture_url = f"http://198.18.0.1/apps/{app_id}/{image_file}"
    try:
        tablet_service = session.service("ALTabletService")
        # tts.say("This is a short story in pictures. Take a look at the first couple of scenes. What do you see?")
        tablet_service.showImage(picture_url)  # Assuming a local web server is running
    except Exception as e:
        print("Could not connect to ALTabletService. Tablet features may not be available.")
        print(f"Error: {e}")

def run_stage_a_robotic(session, tts, transcriber, chatbot, picture_urls):
    """
    Stage A: For each picture, this stage prompts the child, waits up to 30 s for a response,
    retry up to 3 times, and advance on ##SATISFACTORY RESPONSE## or ##NOT INTERESTED##.
    This method processes only one phrase per attempt (one-shot transcription per turn) - quite robotic
    Here it is assumed that each phrase represents a complete response
    ...expecting fast, short, complete answers per attempt—fitting for experiments with kids responding to specific questions after prompts
    """
    tablet = session.service("ALTabletService")

    for picture_number, picture_url in enumerate(picture_urls, start=1):
        # 1) EXP-EVENT & AI-CONTEXT/INSTRUCTION for this picture
        exp_event      = f"showing picture {picture_number}"
        ai_context     = exp_event
        ai_instruction = (
            "You will now be shown a short story in pictures. "
            f"So, let's take a look at picture {picture_number}. Can you tell me about it?"
        )
        print(f"[{exp_event}]")
        tts.say(ai_instruction)

        # 2) method shows the image
        tablet.showImage(picture_url)

        # 3) Waits for up to 30s, loops (retrying) up to 3 times
        attempts = 0
        while attempts < 3:
            start_time = time.time()
            child_phrase = ""

            # Waits up to 30 seconds for transcription
            while time.time() - start_time < 30:
                child_phrase = transcriber.get_transcription().strip()
                if child_phrase:
                    break

            if not child_phrase:
                # Timeout branch
                ai_context     = "30 seconds have passed without a child response"
                ai_instruction = "I didn't hear anything. Can you tell me what you see?"
                print(f"[Timeout on picture {picture_number}, retrying]")
                tts.say(ai_instruction)
                attempts += 1
                continue

            # Early exit if the child wants to stop
            if child_phrase.lower() in ("quit", "exit", "stop"):
                tts.say("Okay, we’ll stop here. Goodbye!")
                return False

            # 4) Send transcript to chatbot with structured tags
            prompt = (
                f"EXP-EVENT: {exp_event}\n"
                f"AI-CONTEXT: {ai_context}\n"
                f"AI-INSTRUCTION: {ai_instruction}\n"
                f"CHILD-TRANSCRIPT: {child_phrase}"
            )
            response = chatbot.get_response(prompt)
            print(f"Child said: {child_phrase}")
            print(f"AI   says: {response}")
            tts.say(response)

            # 5) Check for termination tags
            if "##SATISFACTORY RESPONSE##" in response \
            or "##NOT INTERESTED##" in response:
                break

            attempts += 1

        # 6) Clear the tablet before next picture
        tablet.hideImage()

    # Finished all pictures
    return True


def main0():
    # This is the default main function that connects to Pepper and starts the chatbot interaction.
    """Accumulates multiple short phrases before sending them to the chatbot,
    Allows the user to pause mid-sentence, to self-correct, or to think
    Better suited for free cnversation style interaction with the robot
    Uses silence timeout (max_wait_time) to decide when the full message is ready for chatbot processing."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
    parser.add_argument("--port", type=int, default=9559,
                        help="Naoqi port number")

    args = parser.parse_args()

    conversation_history = []
    wait_start_time = None
    prompted = False
    user_transcriptions = []
    max_wait_time = 2 #seconds to wait for user input before ending conversation
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
    tts.setLanguage("English")  # Setting language to English
    tts.setVolume(0.5)  # Setting volume, max is 1.0
    # tts.setParameter("speed", 100)  # Set speech speed
    # tts.setParameter("pitch", 100)  # Set pitch to normal

    show_on_tablet(session, tts)  # Show the story on Pepper's tablet
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
        print("Authentication failed. Pepper isn't going to talk.")
        return
    # tts.say("If you don't like to talk now, \nJust say 'quit' or 'stop' to end our conversation)")
    print("Authentication successful. Starting transcription. \n(Say 'quit', 'exit', or 'stop' to end conversation)")
    greeting = chatbotAlive.get_response("greet")
    print(f"AI: {greeting}")
    # Commented out to reduce distrations/noise in the lab
    # tts.say(greeting)
    time.sleep(1)  # A pause to let the greetings complete before starting the loop
    time_before_transcription = time.time()  # To calculate transcription lag
    while True:
        # Initialising total and transcription time calculation
        total_time = time.time()
        if wait_start_time is None:
            wait_start_time = time.time()

        transcriber_start_time = time.time() #To calculate transcription time lag
        phrase = transcriber.get_transcription()#.strip()
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
            # This is when the transcription is be sent to bot
            full_transcription = " ".join(user_transcriptions)
            if not full_transcription.strip():
                # Initialise wait_start_time if not already set
                if wait_start_time is None:
                    wait_start_time = time.time()
                if not prompted:
                    #Print the prompt only once during the wait/silence period, for user awareness
                    print("I didn't hear you say a word. Waiting for you... but also counting down to end conversation.")
                    tts.say("I didn't hear you say a word. Waiting for you... but also counting down to end conversation.")
                    prompted = True
                if time.time() - wait_start_time > max_wait_time:
                    print(f'No input detected for more than {max_wait_time}s. Ending conversation.')
                    break
                continue
            if full_transcription.strip():
                conversation_history.append(f"You said: {full_transcription}\n")
            # Print the full transcription and send it to the chatbo
                print(f"You said: {full_transcription}", end='', flush=True)
                #Chatbot timing
                chatbot_start_time = transcriber_end_time = time.time()
                response = chatbotAlive.get_response(full_transcription)
                print(f"AI: {response}", end='', flush=True)
                tts.say(response)
                conversation_history.append(f"AI: {response}\n")
                print()
                print(4*"------")
                user_transcriptions.clear()  # Clear transcriptions after sending to chatbot

                chatbot_end_time = time.time()
                print(f"[Transcription Lag: {transcriber_end_time - time_before_transcription:.2f} seconds]")
                print(f"[Chatbot Lag: {chatbot_end_time - chatbot_start_time:.2f} seconds]")
                print(f"[Total Lag: {time.time() - time_before_transcription:.2f} seconds]")
                continue
            else:
                print("Silence detected. Waiting for you to say something...")
                tts.say("Please talk to me. I am waiting...")
    print(4*"=======")
    print("Full Conversation: ")
    for entry in conversation_history:
        print(entry)

def log_interaction(exp_event, ai_context, ai_instruction, child_transcript, ai_response):
    """
    This formats a complete log entry and appends it to the global conversation_history.
    """
    log_entry = (
        f"--- INTERACTION TURN ---\n"
        f"EXP-EVENT: {exp_event}\n"
        f"AI-CONTEXT: {ai_context}\n"
        f"AI-INSTRUCTION: {ai_instruction}\n"
        f"CHILD-TRANSCRIPT: {child_transcript}\n"
        f"AI_RESPONSE: {ai_response}\n"
        f"------------------------\n\n"
    )
    # This structured log entry is appended to the conversation history list.
    conversation_history.append(log_entry)

def main():
    #This is the main function for the experiment with Pepper, where it shows a story in pictures and interacts with the child.
    #This is still a work in progress, but it should be functional.
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
    parser.add_argument("--port", type=int, default=9559,
                        help="Naoqi port number")

    args = parser.parse_args()
    # --- NEW: Generate a unique session ID and filename at the start ---
    session_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"chat_history_{session_timestamp}.txt"

    global conversation_history 
    conversation_history = []
    app_id = "my_fisherman_story_app"
    image_file1 = "The_fisherman_and_the_cat_1n2.jpg" 
    # List your picture URLs (hosted in your html/ folder):
    app_id = "my_fisherman_story_app"
    image_file1 = "The_fisherman_and_the_cat_1n2.jpg"  # Change to your image file

    pics = [
    f"http://198.18.0.1/apps/{app_id}/{image_file1}",
    f"http://198.18.0.1/apps/{app_id}/The_fisherman_and_the_cat_3n4.jpg",
    f"http://198.18.0.1/apps/{app_id}/The_fisherman_and_the_cat_5n6.jpg",
    ]

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
    tts.setVolume(0.7)  # Set volume to 50%
    # tts.setParameter("speed", 100)  # Set speech speed to 100%
    
    transcriber = Transcriber(
        model="small",
        energy_threshold=1000,
        record_timeout=2,
        phrase_timeout=3,
        default_microphone="HDA Intel PCH: ALC3266 Analog (hw:0,0)"
    )

    chatbotAlive = Chatbot()

    if not chatbotAlive.authenticate():
        print("Authentication failed. Pepper isn't going to talk.")
        return
    # tts.say("If you don't like to talk now, \nJust say 'quit' or 'stop' to end our conversation)")
    print("Authentication successful. Starting transcription. \n(Say 'quit', 'exit', or 'stop' to end conversation)")
    greeting = chatbotAlive.get_response("greet")
    print(f"AI: {greeting}")
    conversation_history.append(f"AI: {greeting}\n")
    tts.say(greeting)
    transcriber.reset()
    time.sleep(1)  # A brief pause to let the greetings complete before starting the loop


    # Run Stage A
    try:
        if run_stage_a(session, tts, transcriber, chatbotAlive, pics):
        # All pictures assumed shown (or child finished early) → Stage B…
        # Transitioning to “creating a story” here
            stage_b_prompt = "Fantastic! Can you invent your own continuation of the story."
            tts.say(stage_b_prompt)
            transcriber.reset()
            conversation_history.append(f"AI: {stage_b_prompt}\n")
        else:
        # Child asked to stop
            return
    finally:
        print("\n" + 4*"=======")
        print("Full Conversation History (Console):")
        for entry in conversation_history:
            print(entry, end='')
        # --- Saves the history to the unique file ---
        save_history_to_file(conversation_history, log_filename)


def run_stage_a(session, tts, transcriber, chatbot, picture_urls):
    print("Running Stage A: Showing pictures and collecting responses...")
    tablet = session.service("ALTabletService")

    for picture_number, picture_url in enumerate(picture_urls, start=1):
        exp_event = f"showing picture {picture_number}"
        print(f"Picture url: {picture_url}")
        ai_context = exp_event
        ai_instruction = (
            f"You will now be shown a short story in pictures. "
            f"So, let's take a look at picture {picture_number}. Can you tell me about it?"
        )
        tts.say(ai_instruction)
        transcriber.reset()
        print(f"picture {picture_number} of {len(picture_urls)}: {picture_url}")
        tablet.showImage(picture_url)
        attempts = 0
        while attempts < 3:
            user_transcriptions = []
            wait_start_time = time.time()
            prompted = False
            max_wait_time = 5  # seconds of total silence allowed per speech attempt. If time of silence exceeds this, the transcription is considered finished.

            print("Listening for the child's response...")
            while True:
                phrase = transcriber.get_transcription().strip()
                if phrase.lower() in ["quit", "exit", "stop"]:
                    tts.say("Okay, we’ll stop here. Goodbye!")
                    transcriber.reset()
                    return False

                if phrase:
                    user_transcriptions.append(phrase)
                    wait_start_time = time.time()  # reset timer after hearing something
                    prompted = False
                    print(f"Captured: {phrase}")

                else:
                    if not prompted:
                        print("Waiting... (child may still be speaking)")
                        prompted = True

                    if time.time() - wait_start_time > max_wait_time:
                        break  # silence for too long → finish transcription for this attempt

            # Processes the accumulated transcription:
            full_transcription = " ".join(user_transcriptions)
            if not full_transcription:
                tts.say("I didn’t hear anything clear. Can you try again?")
                transcriber.reset()
                attempts += 1
                continue

            if full_transcription.strip():
                conversation_history.append(f"You said: {full_transcription}\n")
            print(f"You said: {full_transcription}") # This provides feedback to the console.

            prompt = (
                f"EXP-EVENT: {exp_event}\n"
                f"AI-CONTEXT: {ai_context}\n"
                f"AI-INSTRUCTION: {ai_instruction}\n"
                f"CHILD-TRANSCRIPT: {full_transcription}"
            )

            try:
                response = chatbot.get_response(prompt)
                print(f"AI said: {response}") # Prints the AI's response to the console.
                log_interaction(
                        exp_event=exp_event,
                        ai_context=ai_context,
                        ai_instruction=ai_instruction,
                        child_transcript=full_transcription,
                        ai_response=response
                    )
                conversation_history.append(f"AI: {response}\n")
                tts.say(response)
                transcriber.reset()
                user_transcriptions.clear()  # Clear transcriptions after sending to chatbot
            except Exception as e:
                print(f"Error during chatbot response: {e}")
                tts.say("I had trouble understanding that. I think I have a headache. Ouch!")
                transcriber.reset()
                attempts += 1
                continue
            

            if "##SATISFACTORY RESPONSE##" in response or "##NOT INTERESTED##" in response:
                break  # move on to next picture

            attempts += 1

        tablet.hideImage()
    return True

# --- FUNCTION TO SAVE THE CHAT HISTORY ---
def save_history_to_file(history, filename):
    """
    Saves the conversation history list to a text file.

    Args:
        history (list): A list of strings, where each string is a line of dialogue.
        filename (str): The name of the file to save the history to.
    """
    try:
        with open(filename, 'w') as f:
            for entry in history:
                f.write(entry)
        print(f"Conversation history successfully saved to: {filename}")
    except Exception as e:
        print(f"An error occurred while saving the history file: {e}")

if __name__ == "__main__":
    main()