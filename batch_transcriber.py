import os
import subprocess
import whisper
from pyannote.audio import Pipeline


class BatchVideoTranscriber:
    """
    Batch processor for transcribing and diarizing video (or audio) files.
    Uses OpenAI Whisper for speech-to-text and pyannote.audio for speaker diarization.
    """

    def __init__(self, whisper_model_name, huggingface_token, input_folder_path, output_folder_path=None, auto_convert_to_wav=True):
        """
        Initialize the batch transcriber with constant parameters.

        :param whisper_model_name: Name of the Whisper model (e.g., "turbo", "base", "medium")
        :param huggingface_token: Hugging Face authentication token for pyannote models
        :param input_folder_path: Folder containing input video/audio files
        :param output_folder_path: Folder for saving transcripts (defaults to input folder)
        :param auto_convert_to_wav: Whether to ensure audio is in mono 16kHz WAV format
        """
        self.input_folder_path = input_folder_path
        self.output_folder_path = output_folder_path or input_folder_path
        self.auto_convert_to_wav = auto_convert_to_wav

        # Load models once for entire batch
        print(f"Loading Whisper model '{whisper_model_name}'...")
        self.whisper_model = whisper.load_model(whisper_model_name)

        print("Loading pyannote speaker diarization pipeline...")
        self.diarization_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=huggingface_token
        )

    def convert_video_to_wav(self, video_file_path):
        """
        Convert video to mono 16kHz WAV (required for pyannote), returns the audio file path.
        Skips if already WAV and matches constraints.
        """
        base_name = os.path.splitext(video_file_path)[0]
        wav_file_path = base_name + ".wav"

        if os.path.exists(wav_file_path):
            return wav_file_path

        print(f"Converting {os.path.basename(video_file_path)} to 16kHz mono WAV...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", video_file_path,
            "-ac", "1",        # mono
            "-ar", "16000",    # 16 kHz
            wav_file_path
        ], check=True)

        return wav_file_path

    def find_main_speaker(self, start_time, end_time, diarization_result):
        """
        Find the speaker who talks for the longest overlap in a given time segment.
        """
        max_overlap = 0
        main_speaker = "Unknown"
        for region, _, speaker in diarization_result.itertracks(yield_label=True):
            overlap_start = max(start_time, region.start)
            overlap_end = min(end_time, region.end)
            overlap = max(0, overlap_end - overlap_start)
            if overlap > max_overlap:
                max_overlap = overlap
                main_speaker = speaker
        return main_speaker
    

    def process_single_file(self, file_path):
        """
        Process a single file: convert if necessary, transcribe, diarize, and save transcript.
        """
        if self.auto_convert_to_wav and not file_path.lower().endswith(".wav"):
            audio_file_path = self.convert_video_to_wav(file_path)
        else:
            audio_file_path = file_path

        # Transcription
        whisper_result = self.whisper_model.transcribe(audio_file_path, word_timestamps=True)
        speech_segments = whisper_result["segments"]

        # Diarization
        diarization_result = self.diarization_pipeline(audio_file_path)

        # Output transcript file path
        transcript_name = os.path.splitext(os.path.basename(file_path))[0] + ".txt"
        transcript_path = os.path.join(self.output_folder_path, transcript_name)


        def format_timestamp_seconds(total_seconds):
            """
            Convert a float number of seconds to MM:SS format rounded down to the nearest second.
            """
            minutes, seconds = divmod(int(total_seconds), 60)
            return f"{minutes:02d}:{seconds:02d}"
        
        # Write transcript
        with open(transcript_path, "w", encoding="utf-8") as transcript_file:
            for seg in speech_segments:
                start, end, text = seg['start'], seg['end'], seg['text'].strip()
                start_str = format_timestamp_seconds(start)
                end_str = format_timestamp_seconds(end)
                speaker = self.find_main_speaker(start, end, diarization_result)
                transcript_file.write(f"{speaker} [{start_str}-{end_str}]: {text}\n")

        print(f"Transcript saved: {transcript_path}")

    def process_all_videos(self):
        """
        Loop through all MP4 files in the folder and process them.
        """
        for file_name in os.listdir(self.input_folder_path):
            if file_name.lower().endswith(".mp4"):
                full_path = os.path.join(self.input_folder_path, file_name)
                self.process_single_file(full_path)


if __name__ == "__main__":
    # User configuration
    INPUT_FOLDER = "/home/dotuno/Desktop/SideCam_Thursday"
    OUTPUT_FOLDER = None   # Uses default same folder as input
    HUGGINGFACE_TOKEN = os.getenv("HUGGINGFACE_TOKEN")  # Loaded from environment variable

    transcriber = BatchVideoTranscriber(
        whisper_model_name="turbo",
        huggingface_token=HUGGINGFACE_TOKEN,
        input_folder_path=INPUT_FOLDER,
        output_folder_path=OUTPUT_FOLDER,
        auto_convert_to_wav=True
    )

    transcriber.process_all_videos()
