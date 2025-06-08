#! python3.7

import argparse
import os
import numpy as np
import speech_recognition as sr
import whisper
import torch

from datetime import datetime, timedelta
from queue import Queue
from time import sleep
from sys import platform

# pipe_path = "/tmp/transcribe_demo_dell_pipe"
# pipe = open(pipe_path, 'w', buffering=1)

class Transcriber:
    def __init__(self, model="small", non_english=False, energy_threshold=1000,
                 record_timeout=2, phrase_timeout=3, default_microphone='HDA Intel PCH: ALC3266 Analog (hw:0,0)'):
        self.non_english = non_english
        self.model= model
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.phrase_timeout = phrase_timeout
        self.default_microphone = default_microphone
        self.source = None
        self.transcription = []
        self.transcription_history = []

        if 'linux' in platform:
            mic_name = default_microphone
            if not mic_name or mic_name == 'list':
                print("Available microphone devices are: ")
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    print(f"Microphone with name \"{name}\" found")
                return
            else:
                for index, name in enumerate(sr.Microphone.list_microphone_names()):
                    if mic_name in name:
                        self.source = sr.Microphone(sample_rate=16000)#, device_index=index)
                        break
        else:
            self.source = sr.Microphone(sample_rate=16000, device_index=index)

        # Load Whisper model
        if model in ["tiny", "base", "small", "medium", "large"]:# and not non_english:
            model = model + ".en"
        
        self.audio_model = whisper.load_model(model)
        print(f"Using Whisper model: {model}")

        self.record_timeout = record_timeout
        self.data_queue = Queue()
        self.phrase_timeout = phrase_timeout
        self.transcription = ['']
        self.empty_text_count = 0
        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = energy_threshold
        self.recorder.dynamic_energy_threshold = False  # Disable dynamic energy thresholding
        self.default_microphone = default_microphone
        self.last_audio_time = None
        self.empty_text_count = 0
        self.phrase_time = None
        self.phrase_bytes = bytes()
        # self.transcription = []
        self.empty_text_count = 0

        with self.source:
            self.recorder.adjust_for_ambient_noise(self.source)

        def record_callback(_, audio:sr.AudioData) -> None:
            """
            Threaded callback function to receive audio data when recordings finish.
            audio: An AudioData containing the recorded bytes.
            """
            # Grab the raw bytes and push it into the thread safe queue.
            data = audio.get_raw_data()
            self.data_queue.put(data)

            # Create a background thread that will pass us raw audio bytes.
            # We could do this manually but SpeechRecognizer provides a nice helper.
        self.recorder.listen_in_background(self.source, record_callback, phrase_time_limit=record_timeout)

            # Cue the user that we're ready to go.
        print("Transcriber initialised and Model loaded. Ready.\n", flush=True)
        
        # pass

    def get_transcription(self):
        """
        Returns the current transcription as a string.
        """
        self.transcription = []
        while True:
            try:
                now = datetime.utcnow()
                if not self.data_queue.empty():
                    # New audio data has arrived
                    audio_data = b''.join(self.data_queue.queue)
                    self.data_queue.queue.clear()
                    self.phrase_bytes += audio_data
                    self.phrase_time = now  # Only update when new data arrives

                    # Transcribe current phrase so far (optional, for live feedback)
                    audio_np = np.frombuffer(self.phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    result = self.audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                    text = result['text'].strip()

                    if text == '':
                        self.empty_text_count += 1
                    else:
                        self.empty_text_count = 0
                    # print("Empty text count is - ", self.empty_text_count)
                    if self.transcription:
                        self.transcription[-1] = text
                    else:
                        self.transcription.append(text)
                    # print(f"New text is - {text} and transcription is now: ({self.transcription})")
                    
                        self.transcription[-1] = text
                    # print(f"Phrase incomplete, new text is - {text} and transcription is now: ({transcription})")

                # Check for phrase completion based on time since last audio
                if self.phrase_time and (datetime.utcnow() - self.phrase_time > timedelta(seconds=self.phrase_timeout)) or self.empty_text_count >= 3:
                    # Complete the phrase
                    if self.phrase_bytes:
                        audio_np = np.frombuffer(self.phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                        result = self.audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                        text = result['text'].strip()
                        self.transcription.append(text)
                        # print(f"Phrase complete, new text is - {text} and transcription is now: ({self.transcription})")
                        self.phrase_bytes = bytes()
                        # return text  # Return the last transcription
                    #No worries.
                        self.transcription_history  += self.transcription                  
                        return ''.join(self.transcription)  # Return the full transcription
                    self.phrase_time = None
                    self.empty_text_count = 0  # Reset empty text count

                sleep(0.25)  # Avoid busy waiting

            except KeyboardInterrupt:
                print("\n\nTranscription:")
                for line in self.transcription:
                    print(line)
                break

            sleep(0.25)  # Avoid busy waiting
        