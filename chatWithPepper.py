import time
import qi
import argparse
import requests
import re
from datetime import datetime
from classTranscriber import Transcriber
from chat_master.src.classChatbot import Chatbot
from Pepper_actions import pepper_wave, record_video
# from classChatGemini import GeminiChatbot as Chatbot



def timestamped_entry(s):
    return f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {s}"

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

def navigation_command(phrase, total_pics):
    """Returns new index if navigation, otherwise None."""
    phrase = phrase.lower()
    # Back/previous
    if "back" in phrase or "previous" in phrase:
        return "BACK"
    # Find a number in the phrase (e.g., "picture 2", "go to 3")
    match = re.search(r"(\d+)", phrase)
    if match:
        num = int(match.group(1))
        if 1 <= num <= total_pics:
            return num - 1  # zero-indexed
    return None

def run_stage_a_robotic(session, tts, transcriber, chatbot, picture_urls):
    """
    Stage A: For each picture, this stage prompts the child, waits up to 30 s for a response,
    retry up to 3 times, and advance on ##SATISFACTORY RESPONSE## or ##NOT INTERESTED##.
    This method processes only one phrase per attempt (one-shot transcription per turn) - quite robotic
    Here it is assumed that each phrase represents a complete response
    ...expecting fast, short, complete answers per attempt—fitting for experiments with kids responding to specific questions after prompts
    """
    record_video(session, duration_sec=5)  # Optional: Record a video of the interaction
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
        time.sleep(1.5)  # A brief pause to let the prompt complete`
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
               # pepper_wave(session) #Optional: Pepper waves the child
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
            print(f"Pepper says: {response}")
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
    '''
    The max_wait_time specifies how long the system should wait during a silence period before concluding that the user is done speaking. 
    This helps the application decide when to finish accumulating input and send the captured transcription to the chatbot for processing. Without it, the transcriber could wait indefinitely during gaps in speech, delaying the conversation or causing unwanted behavior.'''
    max_wait_time = 10 #seconds to wait for user input before ending conversation
    #Connection to Pepper's Qi session
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
    tts.setVolume(0.8)  # Setting volume, max is 1.0
    # tts.setParameter("speed", 100)  # Set speech speed
    # tts.setParameter("pitch", 100)  # Set pitch to normal

    show_on_tablet(session, tts)  # Show the story on Pepper's tablet
    # Initialize the transcriber
    transcriber = Transcriber(
        model="small",
        energy_threshold=700,
        max_record_duration=2, #Setting the max duration allowed for the transcriber to capture audio during a recording session
        max_phrase_duration=3, #Sets how long a single spoken phrase can be before it's finalised and processed. Note any continuous speech longer than 3swill be cut off and processed as a full phrase.
        default_microphone="sysdefault" #HDA Intel PCH: ALC897 Analog (hw:0,0)"
    )

    chatbotAlive = Chatbot()

    if not chatbotAlive.authenticate():
        print("Authentication failed. Pepper isn't going to talk.")
        return
    # tts.say("If you don't like to talk now, \nJust say 'quit' or 'stop' to end our conversation)")
    print("Authentication successful. Starting transcription. \n(Say 'quit', 'exit', or 'stop' to end conversation)")
    
    # This is when the conversation starts
    conversation_start_time = datetime.now()

    #pepper_wave(session) #Optional: Pepper waves the child
    greeting = chatbotAlive.get_response("greet")
    print(f"Pepper: {greeting}")
    # Comment out to reduce distrations/noise in the lab
    tts.say(greeting)
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
                print(f"Pepper: {response}", end='', flush=True)
                tts.say(response)
                conversation_history.append(f"Pepper: {response}\n")
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
    conversation_history.append(timestamped_entry(log_entry))

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
    tts.setLanguage("English")  # Setting language to English
    tts.setVolume(0.8)  # Setting volume, max is 1.0

    transcriber = Transcriber(
        model="turbo",
        energy_threshold=600,
        max_record_duration=2,
        max_phrase_duration=3,
        default_microphone="HDA Intel PCH: ALC897 Analog (hw:0,0)" #HDA Intel PCH: ALC3266 Analog (hw:0,0)"
    )

    chatbotAlive = Chatbot()

    if not chatbotAlive.authenticate():
        print("Authentication failed. Pepper isn't going to talk.")
        return
    # tts.say("If you don't like to talk now, \nJust say 'quit' or 'stop' to end our conversation)")
    print("Authentication successful. Starting transcription. \n(Say 'quit', 'exit', or 'stop' to end conversation)")
    
    # This is when the conversation starts
    conversation_start_time = datetime.now()

    greeting = chatbotAlive.get_response("greet")
    #pepper_wave(session, args.ip, args.port) #Optional: Pepper waves the child
    print(f"Pepper: {greeting}")
    conversation_history.append(timestamped_entry(f"Pepper: {greeting}\n"))
    conversation_history.append(f"Pepper: {greeting}\n")
    tts.say(greeting)
    time.sleep(1.5)  # A brief pause to let the prompt complete`
    conversation_history.append(timestamped_entry(f"Pepper: {greeting}\n"))
    transcriber.reset()
    # Listen for readiness confirmation from child
    wait_start = time.time()
    max_wait = 20  # seconds
    confirmed = False

    while time.time() - wait_start < max_wait:
        phrase = transcriber.get_transcription().strip().lower()

        if phrase in ["yes", "yeah", "i'm ready", "ready", "sure", "okay"]:
            confirmed = True
            tts.say("Awesome! Let's begin.")
            conversation_history.append(timestamped_entry("Child: " + phrase + "\n"))
            break
        elif phrase in ["no", "not now", "i'm not ready", "maybe later"]:
            tts.say("That's okay. We can try again later. Bye!")
            return
        elif phrase:
            # Unexpected input
            conversation_history.append(timestamped_entry("Child: " + phrase + "\n"))
            tts.say("I'll take that as a yes. Let's get's started!")
            confirmed = True
            break
        else:
            tts.say("Take your time. I'm listening...")
            time.sleep(2)

    if not confirmed:
        tts.say("I didn’t hear anything. Maybe next time!")
        return


    # Run Stage A
    try:
        if run_stage_a(session, tts, transcriber, chatbotAlive, pics):
        # All pictures assumed shown (or child finished early) → Stage B…
        # Transitioning to “creating a story” here
            stage_b_prompt = "Fantastic! Can you invent your own continuation of the story."
            tts.say(stage_b_prompt)
            time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
            transcriber.reset()
            conversation_history.append(timestamped_entry(f"Pepper: {stage_b_prompt}\n"))
            log_interaction(
                exp_event="starting stage B",
                ai_context="child has finished describing pictures",
                ai_instruction=stage_b_prompt,
                child_transcript="",
                ai_response=stage_b_prompt
            )   

            # Start Stage B conversation loop
            run_stage_b(session, tts, transcriber, chatbotAlive)
        else:
        # Child asked to stop            print(f"Loading Whisper model: {model}")
            return
    finally:
        conversation_end_time = datetime.now()
        print("\n" + 4*"=======")
        print("Full Conversation History (Console):")
        for entry in conversation_history:
            print(entry, end='')
        # --- Saves the history to the unique file ---
        save_history_to_file(conversation_history, log_filename, start_time=conversation_start_time, end_time=conversation_end_time)

def enable_autonomous_mode(session, tts=None):
    """
    Enables Pepper's autonomous behaviors, including gaze tracking and basic awareness.
    Call this after connecting to the session.
    """
    try:
        autonomous_life = session.service("ALAutonomousLife")
        basic_awareness = session.service("ALBasicAwareness")

        # Enable general autonomous behaviors
        current_state = autonomous_life.getState()
        if current_state != "solitary":
            print(f"AutonomousLife current state: {current_state}. Switching to 'solitary' mode.")
            autonomous_life.setState("solitary")
        else:
            print("Pepper is already in 'solitary' autonomous mode.")

        # Enable basic awareness features
        basic_awareness.setEngagementMode("FullyEngaged")  # or "SemiEngaged"
        basic_awareness.setTrackingMode("Head")  # or "Body", but "Head" is gentler
        basic_awareness.startAwareness()

        print("Autonomous mode and gaze tracking enabled.")

        # Optional: Enable eye contact during speech
        if tts:
            tts.setParameter("enableEyeContact", True)
            print("Eye contact enabled for speech.")

    except Exception as e:
        print(f"[Autonomy Setup Error] {e}")

def set_leds_thinking(session):
    """
    Sets Pepper's face LEDs to blue to indicate 'thinking' or waiting.
    """
    try:
        leds = session.service("ALLeds")
        leds.fadeRGB("FaceLeds", 0x0000FF, 0.3)  # Blue
    except Exception as e:
        print(f"[LED Error] Failed to set thinking LEDs: {e}")

def set_leds_speaking(session):
    """
    Sets Pepper's face LEDs to green to indicate it is speaking or ready to respond.
    """
    try:
        leds = session.service("ALLeds")
        leds.fadeRGB("FaceLeds", 0x00FF00, 0.3)  # Green
    except Exception as e:
        print(f"[LED Error] Failed to set speaking LEDs: {e}")

def set_leds_idle(session):
    """
    Set Pepper's face LEDs to neutral white (default) after response.
    """
    try:
        leds = session.service("ALLeds")
        leds.fadeRGB("FaceLeds", 0xFFFFFF, 0.3)  # White
    except Exception as e:
        print(f"[LED Error] Failed to reset LEDs: {e}")


def run_stage_a(session, tts, transcriber, chatbot, picture_urls):
    print("Running Stage A: Showing pictures and collecting responses sequentially...")
    tablet = session.service("ALTabletService")
    max_picture_time = 180 #Average of 5 minutes per picture

    intro_instruction = "You will now be shown a short story in pictures."
    tts.say(intro_instruction)
    conversation_history.append(timestamped_entry(f"Pepper: {intro_instruction}\n"))

    for picture_number, picture_url in enumerate(picture_urls, start=1):
        exp_event = f"showing picture {picture_number}"
        print(f"Picture url: {picture_url}")
        ai_context = exp_event
        
        ai_instruction = f"This is picture {picture_number}. Can you tell me about it?"
        tts.say(ai_instruction)
        conversation_history.append(timestamped_entry(f"Pepper: {ai_instruction}\n"))

        time.sleep(1.5)  # A brief pause to let the prompt complete`
        transcriber.reset()
        print(f"picture {picture_number} of {len(picture_urls)}: {picture_url}")
        tablet.showImage(picture_url)

        # Time picture starts to be shown
        picture_start_time = time.time()

        # Show an HTML page instead of an image
        # This is optional, but it can be used to provide a more interactive experience.
        # render_interactive_page(session)

        attempts = 0
        while attempts < 3:
            # Waits for up to 30 seconds, loops (retrying) up to 3 times
            if time.time() - picture_start_time >= max_picture_time:
                print("Time limit reached for this picture. Moving on...")
                break

            user_transcriptions = []
            wait_start_time = time.time()
            prompted = False
            max_wait_time = 3  # seconds of total silence allowed per speech attempt. If time of silence exceeds this, the statement is considered complete.

            print("Listening for the child's response...")
            while True:
                phrase = transcriber.get_transcription().strip()
                if phrase.lower() in ["quit", "exit", "stop"]:
                    tts.say("Okay, we’ll stop here. Goodbye!")
                    pepper_wave(session) #Optional: Pepper waves the child
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
                time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
                transcriber.reset()
                attempts += 1
                continue

            if full_transcription.strip():
                # conversation_history.append(f"You said: {full_transcription}\n")
                conversation_history.append(timestamped_entry(f"You said: {full_transcription}\n"))

            print(f"You said: {full_transcription}") # This provides feedback to the console.

            prompt = (
                f"EXP-EVENT: {exp_event}\n"
                f"AI-CONTEXT: {ai_context}\n"
                f"AI-INSTRUCTION: {ai_instruction}\n"
                f"CHILD-TRANSCRIPT: {full_transcription}"
            )

            try:
                response = chatbot.get_response(prompt)
                print(f"Pepper said: {response}") # Prints the Pepper's response to the console.
                log_interaction(
                        exp_event=exp_event,
                        ai_context=ai_context,
                        ai_instruction=ai_instruction,
                        child_transcript=full_transcription,
                        ai_response=response
                    )
                conversation_history.append(timestamped_entry(f"Pepper: {response}\n"))
                # conversation_history.append(f"Pepper: {response}\n")
                tts.say(response.replace("##SATISFACTORY##", "").replace("##UNCLEAR##", "").replace("##NOT INTERESTED##", ""))
                time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
                transcriber.reset()
                user_transcriptions.clear()  # Clear transcriptions after sending to chatbot
            except Exception as e:
                print(f"Error during chatbot response: {e}")
                tts.say("I had trouble understanding that. I think I have a headache. Ouch!")
                time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
                transcriber.reset()
                attempts += 1
                continue
            

            if "##SATISFACTORY##" in response or "##NOT INTERESTED##" in response:
                break  # move on to next picture

            if "##SATISFACTORY##" in response and not phrase and time.time() - wait_start_time > 10:
                tts.say("That's okay. We can move to the next picture.")
                time.sleep(1)  # A brief pause to let the prompt complete before starting Stage B``

                break

            attempts += 1

        tablet.hideImage()
    return True

def run_stage_b(session, tts, transcriber, chatbot, max_stage_duration=300):
    """
    Stage B: Free storytelling with a 5-minute max session time.
    """
    tts.say("Great! Now you can invent your own continuation of the story. What happens next?")
    time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
    print("Story creation phase started.")
    stage_start_time = time.time()

    wait_start_time = stage_start_time
    while True:
        if time.time() - stage_start_time > max_stage_duration:
            tts.say("Thanks for your story! That’s the end of this activity.")
            break

        phrase = transcriber.get_transcription().strip()
        conversation_history.append(timestamped_entry(f"Child: {phrase}\n"))


        if phrase.lower() in ["quit", "exit", "stop"]:
            tts.say("Okay, story time is over. That was fun!")
            break

        if not phrase:
            if time.time() - wait_start_time > 45:
                tts.say("It seems you're done. Thank you for your story!")
                break
            continue

        wait_start_time = time.time()
        prompt = (
            f"AI-CONTEXT: The child is continuing the story.\n"
            f"AI-INSTRUCTION: Respond naturally to help continue their story.\n"
            f"CHILD-TRANSCRIPT: {phrase}"
        )

        set_leds_thinking(session) # Set LEDs to indicate thinking
        response = chatbot.get_response(prompt)
        set_leds_speaking(session)  # Set LEDs to indicate speaking
        tts.say(response)
        set_leds_idle(session)
        conversation_history.append(timestamped_entry(f"Pepper: {response}\n"))

        log_interaction(
            exp_event="stage B - storytelling",
            ai_context="child is inventing a continuation of the story",
            ai_instruction="Continue the story based on what the child says.",
            child_transcript=phrase,
            ai_response=response
        )


def run_stage_a_interactive_screen(session, tts, transcriber, chatbot, picture_urls):
    #This is run_stage_a version 2. In development, it is more interactive and allows for possible navigation between pictures.
    print("Running Stage A: Showing pictures and collecting responses...")

    tablet = session.service("ALTabletService")
    max_picture_time = 300
    total_pics = len(picture_urls)
    current_index = 0

    while 0 <= current_index < total_pics:
        picture_number = current_index + 1
        picture_url = picture_urls[current_index]
        exp_event = f"showing picture {picture_number}"
        print(f"Picture url: {picture_url}")

        ai_context = exp_event
        ai_instruction = (
            f"You will now be shown a short story in pictures. "
            f"So, let's take a look at picture {picture_number}. Can you tell me about it? "
            "If you want to see another picture, say 'back' to go to the previous one, or 'go to picture 2'."
        )

        tts.say(ai_instruction)
        time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
        transcriber.reset()
        print(f"picture {picture_number} of {total_pics}: {picture_url}")

        tablet.showImage(picture_url)
        picture_start_time = time.time()
        attempts = 0

        while attempts < 3:
            if time.time() - picture_start_time >= max_picture_time:
                print("Time limit reached for this picture. Moving on...")
                break

            user_transcriptions = []
            wait_start_time = time.time()
            prompted = False
            max_wait_time = 0

            print("Listening for the child's response...")
            while True:
                phrase = transcriber.get_transcription().strip()

                # Navigation logic
                nav_cmd = navigation_command(phrase, total_pics) if phrase else None

                if phrase.lower() in ["quit", "exit", "stop"]:
                    tts.say("Okay, we’ll stop here. Goodbye!")
                    pepper_wave(session)
                    transcriber.reset()
                    return False
                elif nav_cmd == "BACK":
                    if current_index == 0:
                        tts.say("You're already at the first picture.")
                        time.sleep(1.5)  # A brief pause to let the prompt complete before starting Stage B``
                    else:
                        tts.say(f"Going back to picture {current_index}.")
                        time.sleep(1.5)  # A brief pause to let the prompt complete`
                        current_index -= 1
                    tablet.hideImage()
                    break  # Restart main while loop
                elif isinstance(nav_cmd, int):
                    if nav_cmd == current_index:
                        tts.say(f"You're already viewing picture {nav_cmd + 1}.")
                        time.sleep(1.5)  # A brief pause to let the prompt complete`
                    else:
                        tts.say(f"Jumping to picture {nav_cmd + 1}.")
                        time.sleep(1.5)  # A brief pause to let the prompt complete`
                        current_index = nav_cmd
                    tablet.hideImage()
                    break  # Restart main while loop

                if phrase:
                    user_transcriptions.append(phrase)
                    wait_start_time = time.time()
                    prompted = False
                    print(f"Captured: {phrase}")
                else:
                    if not prompted:
                        print("Waiting... (child may still be speaking)")
                        prompted = True
                    if time.time() - wait_start_time > max_wait_time:
                        break  # Finish attempt

            # After navigation, return to display new or same image as needed:
            if nav_cmd:
                # Already handled navigation, so skip attempt logic
                break

            # ... (rest of processing logic remains unchanged)
            full_transcription = " ".join(user_transcriptions)

            if not full_transcription:
                tts.say("I didn’t hear anything clear. Can you try again?")
                transcriber.reset()
                attempts += 1
                continue

            if full_transcription.strip():
                conversation_history.append(timestamped_entry(f"You said: {full_transcription}\n"))
                print(f"You said: {full_transcription}")

                prompt = (
                    f"EXP-EVENT: {exp_event}\n"
                    f"AI-CONTEXT: {ai_context}\n"
                    f"AI-INSTRUCTION: {ai_instruction}\n"
                    f"CHILD-TRANSCRIPT: {full_transcription}"
                )
                
                try:
                    time_before_response = time.time()
                    set_leds_thinking(session)  # Set LEDs to indicate thinking
                    response = chatbot.get_response(prompt)
                    time_after_response = time.time()
                    print(f"Pepper said: {response}")
                    print(f"[Response Time: {time_after_response - time_before_response:.2f} seconds]")
                    log_interaction(
                        exp_event=exp_event,
                        ai_context=ai_context,
                        ai_instruction=ai_instruction,
                        child_transcript=full_transcription,
                        ai_response=response
                    )
                    set_leds_speaking(session)  # Set LEDs to indicate speaking
                    conversation_history.append(timestamped_entry(f"Pepper: {response}\n"))
                    tts.say(response)
                    time.sleep(1.5)  # A brief pause to let the prompt complete`
                    set_leds_idle(session)
                    transcriber.reset()
                    user_transcriptions.clear()
                except Exception as e:
                    print(f"Error during chatbot response: {e}")
                    tts.say("I had trouble understanding that. I think I have a headache. Ouch!")
                    time.sleep(1.5)  # A brief pause to let the prompt complete`
                    transcriber.reset()
                    attempts += 1
                    continue

                if "##SATISFACTORY RESPONSE##" in response or "##NOT INTERESTED##" in response:
                    print(f"Response 'satisfactory' or 'not interested'. Moving to next picture.")
                    break

            attempts += 1

        tablet.hideImage()
        current_index += 1  # Normal forward progression

    return True


def render_interactive_page(session):
    pass  # This function is in development, a placeholder for rendering an interactive HTML page on Pepper's tablet.
    tablet_service = session.service("ALTabletService")
    url = "http://198.18.0.1/apps/your_app/interactive_image_1.html"
    tablet_service.showWebview(url)
    # Subscribe to the custom event from the tablet
    memory_service = session.service("ALMemory")
    subscriber = memory_service.subscriber("ALTabletService/ALTabletBinding/button_pressed")
    # subscriber.signal.connect(cat_clicked)


def save_history_to_file(history, filename, start_time=None, end_time=None):
    """
    Saves the conversation history list to a text file.

    Args:
        history (list): A list of strings, where each string is a line of dialogue.
        filename (str): The name of the file to save the history to.
        start_time (datetime): Conversation start time.
        end_time (datetime): Conversation end time.
    """
    try:
        with open(filename, 'w') as f:
            if start_time:
                f.write(f"Conversation started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            for entry in history:
                f.write(entry)
            if end_time:
                f.write(f"\nConversation ended at: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        print(f"Conversation history successfully saved to: {filename}")
    except Exception as e:
        print(f"An error occurred while saving the history file: {e}")

if __name__ == "__main__":
    main()