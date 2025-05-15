#!/usr/bin/env python3
# -*- encoding: UTF-8 -*-
"""
Event handler class for Pepper robot.
Handles:
- Speech recognition
- Bumper and tactile sensor events
- LED eye color changes
- Face tracking
"""

import qi
import time
import threading
import queue
import numpy as np
import wave
import os
import tempfile
import subprocess
import json
from datetime import datetime
import sys
import traceback

class NaoqiEventHandler:
    def __init__(self, session=None, motion=None, tracker=None):
        """Initialize the event handler with optional session and face tracking services"""
        self.session = session
        self.tts = None
        self.memory = None
        self.leds = None
        self.asr = None
        self.motion = motion
        self.tracker = tracker
        self.is_listening = True
        self.is_tracking = False
        self.running = True
        
        if session:
            try:
                self.tts = session.service("ALTextToSpeech")
                self.memory = session.service("ALMemory")
                self.leds = session.service("ALLeds")
                print("Services initialized successfully")
            except Exception as e:
                print("Warning: Could not initialize some services: %s" % e)

    def say(self, text):
        """Make Pepper speak the given text"""
        try:
            if self.tts:
                self.tts.say(str(text))
            else:
                print("Text-to-speech not available, would have said: %s" % text)
        except Exception as e:
            print("Error in text-to-speech: %s" % e)

    def reset_head_position(self):
        """Reset head to default position"""
        try:
            if self.motion:
                # Define default head position (yaw, pitch in radians)
                self.motion.setAngles(["HeadYaw", "HeadPitch"], [0.0, 0.0], 0.3)
                print("Head position reset")
        except Exception as e:
            print("Error resetting head position: %s" % e)

    def toggle_face_tracking(self):
        """Toggle face tracking mode"""
        if not all([self.motion, self.tracker]):
            print("Face tracking services not available")
            return
            
        try:
            self.is_tracking = not self.is_tracking
            
            if self.is_tracking:
                print("Starting face tracking...")
                
                # Enable stiffness and start tracking
                self.motion.setStiffnesses("Head", 1.0)
                self.tracker.track("Face")
                
                # Visual feedback
                if self.leds:
                    self.leds.fadeRGB("FaceLeds", 0, 255, 0, 0.5)  # Green
                
                print("Face tracking: ON")
                self.say("Face tracking enabled")
            else:
                print("Stopping face tracking...")
                
                # Stop tracking and disable stiffness
                self.tracker.stopTracker()
                self.motion.setStiffnesses("Head", 0.0)
                
                # Reset LED color based on listening state
                if self.leds:
                    if self.is_listening:
                        self.leds.fadeRGB("FaceLeds", 0, 0, 255, 0.5)  # Blue
                    else:
                        self.leds.fadeRGB("FaceLeds", 255, 255, 255, 0.5)  # White
                
                print("Face tracking: OFF")
                self.say("Face tracking disabled")
                
        except Exception as e:
            print("Error toggling face tracking: %s" % e)
            print("Detailed error:", traceback.format_exc())
            # Try to cleanup in case of error
            try:
                self.tracker.stopTracker()
                self.motion.setStiffnesses("Head", 0.0)
            except:
                pass

    def stop(self):
        """Stop all services and cleanup"""
        self.running = False
        
        # Stop face tracking
        if self.tracker:
            try:
                print("Stopping face tracking...")
                self.tracker.stopTracker()
                self.reset_head_position()  # Reset head position before stopping
                time.sleep(1)  # Give time for head to center
                if self.motion:
                    self.motion.setStiffnesses("Head", 0.0)
            except Exception as e:
                print("Error stopping face tracking: %s" % e)

        # Stop speech recognition
        if self.asr:
            try:
                self.asr.pause(True)
            except Exception as e:
                print("Error pausing speech recognition: %s" % e)

        # Reset LEDs
        if self.leds:
            try:
                self.leds.fadeRGB("FaceLeds", 255, 255, 255, 0.5)
            except Exception as e:
                print("Error resetting LEDs: %s" % e)

    def is_running(self):
        """Check if the handler is running"""
        return self.running

    def set_asr_service(self, asr_service):
        """Set the speech recognition service"""
        self.asr = asr_service

    def toggle_listening(self):
        """Toggle listening mode with proper cleanup"""
        if not self.asr:
            print("Speech recognition not available")
            return
            
        try:
            self.is_listening = not self.is_listening
            
            if self.is_listening:
                self.asr.pause(False)
                if self.leds:
                    self.leds.fadeRGB("FaceLeds", 0, 0, 255, 0.5)  # Blue
                print("Listening mode: ON")
                self.say("I'm listening")
            else:
                self.asr.pause(True)
                if self.leds:
                    self.leds.fadeRGB("FaceLeds", 255, 255, 255, 0.5)  # White
                print("Listening mode: OFF")
                self.say("I'm not listening")
        except Exception as e:
            print("Error toggling listening mode: %s" % e)

    def on_sound_detected(self, key, value):
        """Process detected sounds"""
        if not self.is_listening or not value:
            return
            
        print("\n---------- Speech Detected ----------")
        print("Event Received:   ", key)
        print("Raw Event Value:  ", value)
        
        try:
            if isinstance(value, list) and len(value) >= 2:
                recognized_word = str(value[0])
                confidence_score = float(value[1])
                
                print("Recognized Word:  '%s'" % recognized_word)
                print("Confidence Score: %.3f" % confidence_score)
                
                if confidence_score > 0.52:
                    clean_word = recognized_word.strip().lower()
                    
                    if clean_word in ["hello", "hi"]:
                        self.say("Hello! Nice to hear you!")
                    elif clean_word in ["goodbye", "bye"]:
                        self.say("Goodbye! Have a nice day!")
                    elif clean_word == "pepper":
                        self.say("Yes, I'm here!")
                    else:
                        self.say("I heard: " + clean_word)
                    
                    if self.leds:
                        self.leds.fadeRGB("FaceLeds", 0, 255, 0, 0.1)  # Green flash
                        self.leds.fadeRGB("FaceLeds", 0, 0, 255, 0.1)  # Back to blue
                else:
                    print("Confidence too low, ignoring...")
                    
        except Exception as e:
            print("Error processing speech: %s" % e)
            
        print("-----------------------------------\n")

    def on_head_touched(self, value):
        """Handle head touch events"""
        if value:
            self.say("Head touched")

    def on_bumper_pressed(self, value):
        """Handle bumper press events"""
        if value:
            self.say("Bumper pressed") 