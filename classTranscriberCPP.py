import numpy as np
import speech_recognition as sr
from pywhispercpp.model import Model  # Import Whisper.cpp bindings
import time
from datetime import datetime, timedelta
from queue import Queue
from sys import platform

class Transcriber:
    def __init__(self, model="base.en", energy_threshold=1000,
                 record_timeout=2, phrase_timeout=5, default_microphone='Built-in Microphone'):
        self.energy_threshold = energy_threshold
        self.record_timeout = record_timeout
        self.phrase_timeout = phrase_timeout
        self.default_microphone = default_microphone
        self.source = None
        self.transcription = []
        self.transcription_history = []
        self.silence_threshold = 8

        # Initialize Whisper.cpp model
        self.audio_model = Model(model)
        print(f"Using Whisper.cpp model: {model}")

        self.data_queue = Queue()
        self.recorder = sr.Recognizer()
        self.recorder.energy_threshold = energy_threshold
        self.recorder.dynamic_energy_threshold = False  # Disable dynamic energy thresholding

        # Set up microphone
        if 'linux' in platform:
            mic_name = default_microphone
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if mic_name in name:
                    self.source = sr.Microphone(sample_rate=16000, device_index=index)
                    break
                if self.source is None:
                    print("No matching microphone found. Using default microphone.")
                    self.source = sr.Microphone(sample_rate=16000)
        else:
            self.source = sr.Microphone(sample_rate=16000)

        with self.source:
            self.recorder.adjust_for_ambient_noise(self.source)

        def record_callback(_, audio: sr.AudioData) -> None:
            """Threaded callback function to receive audio data."""
            data = audio.get_raw_data()
            self.data_queue.put(data)

        self.recorder.listen_in_background(self.source, record_callback, phrase_time_limit=record_timeout)
        print("Transcriber initialized and Whisper.cpp model loaded. Ready.\n", flush=True)

    def get_transcription(self):
        """Returns the current transcription as a string."""
        self.transcription = []
        while True:
            try:
                now = datetime.utcnow()
                if not self.data_queue.empty():
                    audio_data = b''.join(self.data_queue.queue)
                    self.data_queue.queue.clear()
                    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                    # Transcribe using Whisper.cpp
                    result = self.audio_model.transcribe(audio_np)
                    if isinstance(result, list):
                        result = ''.join([s.text if hasattr(s, 'text') else str(s) for s in result])
                    self.text = result.strip()

                    if not self.transcription or self.text != self.transcription[-1]:
                        self.transcription.append(self.text)

                if self.transcription and len(self.transcription) > self.silence_threshold:
                    break

                time.sleep(0.25)  # Avoid busy waiting

            except KeyboardInterrupt:
                print("\n\nKeyboard Interrupt detected. Final Transcription:")
                for line in self.transcription:
                    print(line)
                break

        return ' '.join(self.transcription).strip()