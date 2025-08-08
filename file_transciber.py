import whisper
from pyannote.audio import Pipeline
import soundfile as sf

# File paths and Hugging Face token
audio_file = "/home/dotunolutunbi/Downloads/session_audio_20250807_120850.wav"
output_file = "transcript.txt"
HUGGINGFACE_TOKEN = "hf_QppLjNPKfZZqzHumthkarpBYlWlbVQFW"

# 1. Transcribe audio with Whisper
print("Loading Whisper model and transcribing...")
model = whisper.load_model("base")
result = model.transcribe(audio_file, word_timestamps=True)
segments = result["segments"]

# 2. Run pyannote.audio diarization
print("Loading pyannote model and performing diarization...")
pipeline = Pipeline.from_pretrained(
    "pyannote/speaker-diarization-3.1",
    use_auth_token=HUGGINGFACE_TOKEN
)
diarization = pipeline(audio_file)

# 3. Map Whisper segments to speakers
def find_speaker(time, diarization):
    # Returns speaker label active at a given time, else None
    for segment, _, speaker in diarization.itertracks(yield_label=True):
        if segment.start <= time < segment.end:
            return speaker
    return "Unknown"

# 4. Write diarized transcript to file
print(f"Writing diarized transcript to {output_file}...")
with open(output_file, "w", encoding="utf-8") as f:
    for seg in segments:
        start_time = seg['start']
        end_time = seg['end']
        text = seg['text'].strip()
        speaker = find_speaker((start_time + end_time)/2, diarization)  # Approximate: use mid-segment
        line = f"{speaker} [{start_time:.2f}-{end_time:.2f}s]: {text}\n"
        f.write(line)

print("Done. Transcript saved!")

