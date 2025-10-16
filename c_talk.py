import asyncio
import pyaudio
from livekit import rtc
import numpy as np
import dotenv
import concurrent.futures

dotenv.load_dotenv(".env.livekit")
USER_TOKEN = dotenv.get_key(".env.livekit", "USER_TOKEN")
ROOM_NAME = dotenv.get_key(".env.livekit", "ROOM_NAME")
WS_URL = dotenv.get_key(".env.livekit", "LIVEKIT_URL")

# async def play_audio_track(track: rtc.RemoteAudioTrack):
#     """Play incoming audio from the agent."""
#     pa = pyaudio.PyAudio()
    
#     # List available audio devices
#     print(f"[DEBUG] Available audio output devices:")
#     for i in range(pa.get_device_count()):
#         info = pa.get_device_info_by_index(i)
#         if info['maxOutputChannels'] > 0:
#             print(f"  [{i}] {info['name']}")
    
#     stream = pa.open(
#         format=pyaudio.paInt16,
#         channels=1,
#         rate=48000,
#         output=True,
#         frames_per_buffer=480)
    
#     print("[DEBUG] Audio stream opened")
#     audio_stream = rtc.AudioStream(track)
#     frame_count = 0
    
#     try:
#         async for event in audio_stream:
#             frame_count += 1
#             if frame_count % 100 == 0:  # Print every 100 frames
#                 print(f"\n[DEBUG] Received {frame_count} audio frames")
#             frame = event.frame
#             # The event.frame is an AudioFrame object
#             # Access the raw data buffer directly
#             audio_data = bytes(event.frame.data)
#             stream.write(audio_data)
#             # stream.write(frame.data.tobytes())
#     except Exception as e:
#         print(f"\nError playing audio: {e}")
#         import traceback
#         traceback.print_exc()
#     finally:
#         print(f"\n[DEBUG] Audio playback stopped. Total frames: {frame_count}")
#         stream.stop_stream()
#         stream.close()
#         pa.terminate()


async def play_audio_track(track: rtc.RemoteAudioTrack):
    pa = pyaudio.PyAudio()
    stream = pa.open(format=pyaudio.paInt16,
                     channels=1,
                     rate=24000,
                     output=True,
                     frames_per_buffer=480)

    audio_stream = rtc.AudioStream(track)

    # ---- executor pool for blocking PyAudio ----
    loop = asyncio.get_running_loop()
    stream = None
    frame_count = 0
    first_frame = True
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        try:
            async for event in audio_stream:
                frame = event.frame
                frame_count += 1
                if first_frame:
                    print(f"\n[DEBUG] Received first audio frame")
                    first_frame = False
                    
                    with open("audio_format.txt", "w") as f:
                        f.write(f"Sample rate: {frame.sample_rate}\n")
                        f.write(f"Channels: {frame.num_channels}\n")
                        f.write(f"Samples per channel: {frame.samples_per_channel}\n")
                    
                    print(f"\n[FORMAT] {frame.sample_rate}Hz, {frame.num_channels}ch - saved to audio_format.txt\n")
                
                # if frame_count == 1:
                #     print(f"\n[AUDIO FORMAT]")
                #     print(f"  Sample rate: {frame.sample_rate} Hz")
                #     print(f"  Channels: {frame.num_channels}")
                #     print(f"  Samples per channel: {frame.samples_per_channel}")
                #     print(f"  Data length: {len(frame.data.tobytes())} bytes\n")
                    
                    # Create stream with agent's actual format
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=frame.num_channels,
                        rate=frame.sample_rate,
                        output=True,
                        frames_per_buffer=frame.samples_per_channel
                    )
                    
                audio_bytes = frame.data.tobytes()
                # run the blocking write in a thread
                if len(audio_bytes) > 0:
                    audio_array = np.frombuffer(audio_bytes, np.int16)
                    mean_square = np.mean(audio_array.astype(np.float64)**2)
                    rms = int(np.sqrt(mean_square)) if mean_square >= 0 else 0
                    print(f"[DEBUG] recv {len(audio_bytes)} B, agent RMS {rms}")
                else:
                    rms = 0
                # rms = int(np.sqrt(np.mean(np.frombuffer(audio_bytes, np.int16)**2)))
                # print(f"[DEBUG] agent RMS {rms}")  
                await loop.run_in_executor(pool, stream.write, frame.data.tobytes())
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()

async def publish_microphone(local: rtc.LocalParticipant):
    # Ask the OS for an audio track
    source = rtc.AudioSource(48000, 1)          # 48 kHz, mono
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)

    # Publish it to the room
    options = rtc.TrackPublishOptions()
    options.source = rtc.TrackSource.SOURCE_MICROPHONE
    await local.publish_track(track, options)

    # Start the capture loop (keeps the mic open)
    asyncio.create_task(capture_microphone(source))

async def capture_microphone(source: rtc.AudioSource):
    """Read microphone frames and push them into the source."""
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=48000,
        input=True,
        frames_per_buffer=480)          # 10 ms @ 48 kHz
    try:
        while True:
            data = stream.read(480, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)
            
            # Calculate RMS for visual feedback
            rms = int(np.sqrt(np.mean(np.abs(frame.astype(np.float64))**2)))
            bar = "█" * min(50, rms // 10)
            print(f"\r RMS {rms:4d}  {bar:<50}", end='', flush=True)
            
            await source.capture_frame(rtc.AudioFrame(
                data=frame.tobytes(),
                sample_rate=48000,
                samples_per_channel=480,
                num_channels=1))
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


async def main() -> None:
    # The room object
    room = rtc.Room()

    # Define event handlers
    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant):
        print(f"\n🎵  Subscribed to {participant.identity}'s track")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            print("🔊  Playing agent audio...")
            asyncio.create_task(play_audio_track(track))

    @room.on("participant_connected")
    def on_participant_connected(participant):
        print(f"\n👋  {participant.identity} connected")

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        print(f"\n👋  {participant.identity} disconnected")

    @room.on("data_received")
    def on_data_received(payload: bytes, participant, kind):
        print(f"\n📨  Got message: {payload.decode()}")

    # Connect to the room
    print("Connecting…")
    await room.connect(WS_URL, USER_TOKEN)
    print(f"✅  Connected to room: {ROOM_NAME}")

    # SID = room's unique ID
    print(f"    SID: {await room.sid}")
    all_ids = [room.local_participant.identity] + list(room.remote_participants.keys())
    print(f"Participants: {all_ids}")
    print("\nSpeak into your microphone. Press Ctrl+C to exit.\n")
    
    await publish_microphone(room.local_participant)
    
    try:
        await asyncio.Event().wait()  # Keep running until interrupted
    except KeyboardInterrupt:
        print("\nInterrupted. Leaving...")
    finally:
        await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())