#! python3.7

import numpy as np
import speech_recognition as sr
import whisper
import torch
import time

from datetime import datetime, timedelta
from queue import Queue
# from time import sleep
from sys import platform

# pipe_path = "/tmp/transcribe_demo_dell_pipe"
# pipe = open(pipe_path, 'w', buffering=1)

class Transcriber:
    def __init__(self, model="small", non_english=False, energy_threshold=1000,
                 record_timeout=2, phrase_timeout=5, default_microphone='Built-in Microphone'):#HDA Intel PCH: ALC3266 Analog (hw:0,0)'):
        self.non_english = non_english
        self.model= model
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.phrase_timeout = phrase_timeout
        self.default_microphone = default_microphone
        self.source = None
        self.transcription = []
        self.transcription_history = []
        self.silence_threshold = 8

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
            self.source = sr.Microphone(sample_rate=16000)#, device_index=index)

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
        self.leading_empty_count = 0
        self.post_speech_empty_count = 0
        self.speech_started = False

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
                    self.text = result['text'].strip()
                    
                    if not self.speech_started:
                        if self.text == '':
                            self.leading_empty_count += 1
                        else:
                            self.speech_started = True
                            self.empty_text_count = 0
                        # print("Empty text count is - ", self.empty_text_count)
                    else:
                        if self.text == '':
                            self.post_speech_empty_count += 1
                        else:
                            self.post_speech_empty_count = 0
                    if self.transcription:
                        self.transcription[-1] = self.text
                    else:
                        self.transcription.append(self.text)
                        # print(f"New text is - {text} and transcription is now: ({self.transcription})")
                        
                        # print(f"Phrase incomplete, new text is - {text} and transcription is now: ({transcription})")

                # Check for phrase completion based on time since last audio
                #if self.speech_started and (
                    #(self.phrase_time and (datetime.utcnow() - self.phrase_time > timedelta(seconds=self.phrase_timeout))) or self.post_speech_empty_count >= self.silence_threshold):
                if self.speech_started and self.post_speech_empty_count >= self.silence_threshold:
                    print(f"post speech empty count is {self.post_speech_empty_count}, stopping transcription.")
                    break
                    # Complete the phrase

                if self.speech_started and self.phrase_time is not None:
                    # Check if the phrase has been idle for too long
                    if datetime.utcnow() - self.phrase_time > timedelta(seconds=self.phrase_timeout):
                    #     print(f"datetime.utcnow() - self.phrase_time is {datetime.utcnow() - self.phrase_time}, phrase timeout reached.")
                    #     print(f"phrase timeout is {self.phrase_timeout} seconds.")s
                    #     print("Phrase timeout reached, pausing transcription.")
                    #     #print("Full transcription: ")
                        break
                    #     self.phrase_bytes = bytes()

                if not self.speech_started and self.leading_empty_count > 10:
                    #That is, waiting for a long time without speech, reset
                    print(f"leading empty count is {self.leading_empty_count}, resetting transcription.")
                    print("No speech detected for a while, reseting transcription")
                    self.leading_empty_count = 0

                time.sleep(0.25)  # Avoid busy waiting

            except KeyboardInterrupt:
                print("\n\nKeyboard Interrupt detected. Final Transcription:")
                for line in self.transcription:
                    print(line)
                break
        
    
        if self.phrase_bytes:
            audio_np = np.frombuffer(self.phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            result = self.audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
            self.text = result['text'].strip()
            #Only append if text is not a repeat of the last phrase
            if not self.transcription or self.text != self.transcription[-1] or self.text == '':
                self.transcription.append(self.text)
            # print(f"Phrase complete, new text is - {text} and transcription is now: ({self.transcription})")
            self.phrase_bytes = bytes()
        ##phrase_time = None
        post_speech_empty_count = 0
        # check for silence
        self.joined_text = ''.join(t for t in self.transcription if t.strip() != '')
        # For debugging purposes only, I can print the joined text 
        # print(f"Joined text is : {self.joined_text}")
        # print("\nSilence detected. Final transcription. \n")
        # print("Full transcription: ")
        for line in self.transcription:
            print(line)
        return ' '.join(self.transcription).strip()  # Return the full transcription
        
            