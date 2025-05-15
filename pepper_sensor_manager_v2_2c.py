#! /usr/bin/env python
# -*- encoding: UTF-8 -*-

"""
Enhanced main script for managing Pepper's sensors and events with face tracking.
This script handles:
- Speech recognition with proper cleanup
- Bumper sensors with voice feedback
- Tactile sensors with voice feedback
- LED eye color changes based on listening mode
- Face tracking with keyboard toggle
"""

# Add these imports at the top
import qi
import argparse
import sys
import time
import traceback
import threading
import select
import termios
import tty
from naoqi_callbacks_v2_2c import NaoqiEventHandler

class KeyboardReader:
    def __init__(self):
        if sys.platform != 'win32':
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
        self.has_terminal = sys.stdin.isatty()

    def getch(self):
        if not self.has_terminal:
            return sys.stdin.read(1) if select.select([sys.stdin], [], [], 0)[0] else None
        try:
            tty.setraw(self.fd)
            ch = sys.stdin.read(1)
            return ch
        finally:
            if sys.platform != 'win32':
                termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def reset(self):
        if sys.platform != 'win32' and self.has_terminal:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

class KeyboardListener(threading.Thread):
    def __init__(self, handler):
        threading.Thread.__init__(self)
        self.handler = handler
        self.daemon = True
        self.running = True
        self.keyboard = KeyboardReader()

    def run(self):
        print "\nCommands:"
        print "  'l' - Toggle listening mode"
        print "  'f' - Toggle face tracking"
        print "  'q' - Quit"
        
        try:
            while self.running:
                ch = self.keyboard.getch()
                if ch:
                    if ch == 'l':
                        print "\nToggling listening mode..."
                        self.handler.toggle_listening()
                    elif ch == 'f':
                        print "\nToggling face tracking..."
                        self.handler.toggle_face_tracking()
                    elif ch == 'q':
                        print "\nQuitting..."
                        self.handler.stop()
                        self.running = False
                        break
                    # Ignore other characters
                time.sleep(0.1)
        finally:
            self.keyboard.reset()

# ... (keep existing sensor setup functions) ...

def setup_face_tracking(session):
    """Setup face tracking services"""
    print "Setting up face tracking..."
    try:
        # Get basic services
        motion = session.service("ALMotion")
        tracker = session.service("ALTracker")
        
        # Initial setup
        motion.wakeUp()  # Make sure robot is awake
        
        # Configure tracker
        tracker.stopTracker()  # Stop any existing tracking
        targetName = "Face"
        faceWidth = 0.1  # Face width in meters
        tracker.registerTarget(targetName, faceWidth)
        
        # Set tracker to move only head, not whole body
        tracker.setMode("Head")
        
        print "Face tracking services configured successfully"
        return motion, tracker
        
    except Exception as e:
        print "Error setting up face tracking: %s" % e
        return None, None

def cleanup_services(session, handler, asr_service):
    """Cleanup all services properly"""
    print "\nCleaning up services..."
    
    try:
        # Stop the handler first
        if handler:
            handler.stop()
            print "Handler stopped"

        if session:
            # Cleanup face tracking
            try:
                awareness = session.service("ALBasicAwareness")
                tracker = session.service("ALTracker")
                
                awareness.stopAwareness()
                tracker.stopTracker()
                print "Face tracking stopped"
            except Exception as e:
                print "Error cleaning up face tracking: %s" % e

            # ... (keep existing cleanup code for other services) ...

    except Exception as e:
        print "Error during cleanup: %s" % e
    
    print "Cleanup completed"

def setup_speech_recognition(session, memory_service, service_name):
    """Setup speech recognition with vocabulary and word spotting"""
    print "Setting up speech recognition..."
    try:
        asr = session.service("ALSpeechRecognition")
        print "ALSpeechRecognition service obtained"
        
        # Configure speech recognition
        asr.setLanguage("English")
        asr.setVisualExpression(False)
        
        # Define vocabulary
        vocabulary = [
            "yes", "no", "please", "thank you",
            "hello", "goodbye", "pepper",
            "stop", "move", "turn",
            "left", "right", "forward", "backward",
            "what", "where", "when", "how",
            "elephant", "Dotun", "Datum"
        ]
        
        # Enable word spotting and set vocabulary
        asr.setVocabulary(vocabulary, True)  # True enables word spotting
        print "Speech recognition configured with vocabulary:"
        print ", ".join(vocabulary)
        
        # Subscribe to word recognized events
        memory_service.subscribeToEvent("WordRecognized", service_name, "on_sound_detected")
        asr.pause(False)  # Make sure speech recognition is running
        
        print "Speech recognition started and listening..."
        return asr  # Return the service for later use
        
    except Exception as e:
        print "Error setting up speech recognition: %s" % e
        return None

def setup_bumper_sensors(memory_service, service_name):
    """Setup bumper sensor subscriptions"""
    print "Setting up bumper sensors..."
    try:
        bumper_events = ["RightBumperPressed", "LeftBumperPressed", "BackBumperPressed"]
        for event in bumper_events:
            memory_service.subscribeToEvent(event, service_name, "on_bumper_pressed")
            print "Subscribed to %s" % event
        print "Bumper sensors configured and listening..."
    except Exception as e:
        print "Error setting up bumper sensors: %s" % e

def setup_tactile_sensors(memory_service, service_name):
    """Setup all tactile sensor subscriptions"""
    print "Setting up tactile sensors..."
    try:
        # Head tactile sensors
        head_events = ["FrontTactilTouched", "MiddleTactilTouched", "RearTactilTouched"]
        for event in head_events:
            memory_service.subscribeToEvent(event, service_name, "on_head_touched")
            print "Subscribed to %s" % event
            
        # Hand tactile sensors
        hand_events = ["LeftHandTactilTouched", "RightHandTactilTouched"]
        for event in hand_events:
            memory_service.subscribeToEvent(event, service_name, "on_hand_touched")
            print "Subscribed to %s" % event
            
        print "All tactile sensors configured and listening..."
    except Exception as e:
        print "Error setting up tactile sensors: %s" % e

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
    parser.add_argument("--port", type=int, default=9559,
                        help="Naoqi port number")

    args = parser.parse_args()
    session = None
    handler = None
    asr_service = None
    keyboard_listener = None

    try:
        print "Attempting to connect to Naoqi at %s:%d..." % (args.ip, args.port)
        session = qi.Session()
        session.connect("tcp://" + args.ip + ":" + str(args.port))
        print "Connection successful!\n"

        # Setup services
        session.listen("tcp://0.0.0.0:0")
        service_name = "NaoqiEventHandler"
        
        # Setup face tracking (simplified)
        motion, tracker = setup_face_tracking(session)
        
        # Initialize handler with face tracking services (no awareness)
        handler = NaoqiEventHandler(session, motion, tracker)
        session.registerService(service_name, handler)
        print "NaoqiEventHandler service registered"
        
        # Setup memory service
        memory_service = session.service("ALMemory")
        print "ALMemory service obtained.\n"

        # Setup speech recognition
        asr_service = setup_speech_recognition(session, memory_service, service_name)
        if asr_service:
            handler.set_asr_service(asr_service)

        # Setup other sensors
        setup_tactile_sensors(memory_service, service_name)
        setup_bumper_sensors(memory_service, service_name)

        # Start keyboard listener
        keyboard_listener = KeyboardListener(handler)
        keyboard_listener.start()

        # Main loop with better handling
        while handler.is_running():
            try:
                time.sleep(0.1)
            except KeyboardInterrupt:
                handler.stop()
                break

    except Exception as e:
        print "\nAn unexpected error occurred: %s" % e
        traceback.print_exc()
    finally:
        if keyboard_listener:
            keyboard_listener.running = False
            keyboard_listener.keyboard.reset()
        cleanup_services(session, handler, asr_service)
        print "Script finished."

if __name__ == "__main__":
    main() 