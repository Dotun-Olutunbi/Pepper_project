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

pipe_path = "/tmp/transcribe_demo_dell_pipe"
pipe = open(pipe_path, 'w', buffering=1)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="small", help="Model to use",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
    parser.add_argument("--energy_threshold", default=1000,
                        help="Energy level for mic to detect.", type=int)
    parser.add_argument("--record_timeout", default=2,
                        help="How real time the recording is in seconds.", type=float)
    parser.add_argument("--phrase_timeout", default=2,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)
    if 'linux' in platform:
        parser.add_argument("--default_microphone", default='HDA Intel PCH: ALC3266 Analog (hw:0,0)',
                            help="Default microphone name for SpeechRecognition."
                                 "Run this with 'list' to view available Microphones.", type=str) #arecord -l
    args = parser.parse_args()

    # The last time a recording was retrieved from the queue.
    phrase_time = None
    # Thread safe Queue for passing data from the threaded recording callback.
    data_queue = Queue()
    # Bytes object which holds audio data for the current phrase
    phrase_bytes = bytes()
    # We use SpeechRecognizer to record our audio because it has a nice feature where it can detect when speech ends.
    recorder = sr.Recognizer()
    recorder.energy_threshold = args.energy_threshold
    # Definitely do this, dynamic energy compensation lowers the energy threshold dramatically to a point where the SpeechRecognizer never stops recording.
    recorder.dynamic_energy_threshold = False

    # Important for linux users.
    # Prevents permanent application hang and crash by using the wrong Microphone
    if 'linux' in platform:
        mic_name = args.default_microphone
        if not mic_name or mic_name == 'list':
            print("Available microphone devices are: ")
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                print(f"Microphone with name \"{name}\" found")
            return
        else:
            for index, name in enumerate(sr.Microphone.list_microphone_names()):
                if mic_name in name:
                    source = sr.Microphone(sample_rate=16000)#, device_index=index)
                    break
    else:
        source = sr.Microphone(sample_rate=16000, device_index=index)

    # Load / D
    model = args.model
    if args.model != "large" and args.model != "turbo" and not args.non_english:
        model = model + ".en"
    audio_model = whisper.load_model(model)

    record_timeout = args.record_timeout
    phrase_timeout = args.phrase_timeout

    transcription = ['']

    with source:
        recorder.adjust_for_ambient_noise(source)

    def record_callback(_, audio:sr.AudioData) -> None:
        """
        Threaded callback function to receive audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push it into the thread safe queue.
        data = audio.get_raw_data()
        data_queue.put(data)

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
    recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
    print("Model loaded.\n")
    print("ready", flush=True)

    last_audio_time = None
    empty_text_count = 0
    while True:
        try:
            now = datetime.utcnow()
            if not data_queue.empty():
                # New audio data has arrived
                audio_data = b''.join(data_queue.queue)
                data_queue.queue.clear()
                phrase_bytes += audio_data
                phrase_time = now  # Only update when new data arrives

                # Transcribe current phrase so far (optional, for live feedback)
                audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                text = result['text'].strip()

                if text == '':
                    empty_text_count += 1
                else:
                    empty_text_count = 0

                if transcription:
                    transcription[-1] = text
                else:
                    transcription.append(text)
                print(f"New text is - {text} and transcription is now: ({transcription})")
                 
                # transcription[-1] = text
                # print(f"Phrase incomplete, new text is - {text} and transcription is now: ({transcription})")

            # Check for phrase completion based on time since last audio
            if phrase_time and (datetime.utcnow() - phrase_time > timedelta(seconds=phrase_timeout)):
                # Complete the phrase
                if phrase_bytes:
                    audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                    result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
                    text = result['text'].strip()
                    transcription.append(text)
                    print(f"Phrase complete, new text is - {text} and transcription is now: ({transcription})")
                    phrase_bytes = bytes()
                phrase_time = None
                empty_text_count = 0  # Reset empty text count

            sleep(0.25)  # Avoid busy waiting

        except KeyboardInterrupt:
            print("\n\nTranscription:")
            for line in transcription:
                print(line)
            break

        sleep(0.25)  # Avoid busy waiting
            # else:
            #     # No new audio data; check for phrase completion
            #     if phrase_time and (datetime.utcnow() - phrase_time > timedelta(seconds=phrase_timeout)):
            #         # Phrase is complete
            #         audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            #         result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
            #         text = result['text'].strip()
            #         transcription.append(text)
            #         print(f"Phrase complete, new text is - {text} and transcription is now: ({transcription})")
            #         phrase_bytes = bytes()
            #         phrase_time = None  # Reset until new data arrives

            #     sleep(0.25)  # Avoid busy waiting

            # (Optional) Clear and print transcription as before
            # os.system('cls' if os.name=='nt' else 'clear')
            # for line in transcription:
            #     print(line)
            # print('', end='', flush=True)

    # except KeyboardInterrupt:
    #     print("\n\nTranscription:")
    #     for line in transcription:
    #         print(line)
    #     break

    # while True:
    #     try:
    #         now = datetime.utcnow()
    #         # Pull raw recorded audio from the queue.
    #         if not data_queue.empty():
    #             phrase_complete = False
    #             # If enough time has passed between recordings, consider the phrase complete.
    #             # Clear the current working audio buffer to start over with the new data.
    #             # print("Let's see time: ", phrase_time, now, timedelta(seconds=phrase_timeout))
    #             if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
    #                 phrase_bytes = bytes()
    #                 phrase_complete = True
    #             # This is the last time we received new audio data from the queue.
    #             phrase_time = now
                
    #             # Combine audio data from queue
    #             audio_data = b''.join(data_queue.queue)
    #             data_queue.queue.clear()

    #             # Add the new audio data to the accumulated data for this phrase
    #             phrase_bytes += audio_data

    #             # Convert in-ram buffer to something the model can use directly without needing a temp file.
    #             # Convert data from 16 bit wide integers to floating point with a width of 32 bits.
    #             # Clamp the audio stream frequency to a PCM wavelength compatible default of 32768hz max.
    #             audio_np = np.frombuffer(phrase_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    #             # Read the transcription.
    #             result = audio_model.transcribe(audio_np, fp16=torch.cuda.is_available())
    #             text = result['text'].strip()

    #             # If we detected a pause between recordings, add a new item to our transcription.
    #             # Otherwise edit the existing one.
    #             if phrase_complete:
    #                 transcription.append(text)
    #                 if text:
    #                     pipe.write(text + '\n')
    #                     pipe.flush()
    #             else:
    #                 transcription[-1] = text

    #             # Clear the console to reprint the updated transcription.
    #             os.system('cls' if os.name=='nt' else 'clear')
    #             for line in transcription:
    #                 print(line)
    #             # Flush stdout.
    #             print('', end='', flush=True)
    #         else:
    #             # Infinite loops are bad for processors, must sleep.
    #             sleep(0.25)
    #     except KeyboardInterrupt:
    #         break
    
    # Check if the pipe is still open and close it
    print("\n\nTranscription:")
    for line in transcription:
        print(line)


if __name__ == "__main__":
    main()
