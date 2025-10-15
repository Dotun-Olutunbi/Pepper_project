import asyncio
import pyaudio
from livekit import rtc
import numpy as np
import dotenv
# from credentials import USER_TOKEN, ROOM_NAME, WS_URL

dotenv.load_dotenv(".env.livekit")
USER_TOKEN = dotenv.get_key(".env.livekit", "USER_TOKEN")
ROOM_NAME = dotenv.get_key(".env.livekit", "ROOM_NAME")
WS_URL = dotenv.get_key(".env.livekit", "LIVEKIT_URL")

async def publish_microphone(local: rtc.LocalParticipant):
            # Ask the OS for an audio track
        source = rtc.AudioSource(48000, 1)          # 48 kHz, mono
        track = rtc.LocalAudioTrack.create_audio_track("mic", source)

        # Publish it to the room
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await local.publish_track(track, options)

        # 3. Start the capture loop (keeps the mic open)
        asyncio.create_task(capture_microphone(source))

async def capture_microphone(source: rtc.AudioSource):
    "Read microphone frames and push them to the source."
    pa = pyaudio.PyAudio()
    stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=48000,
        input=True,
        input_device_index=9,
        frames_per_buffer=480)          # 10 ms @ 48 kHz
    SILENCE_THRESHOLD = 200
    try:
        while True:
            data = stream.read(480, exception_on_overflow=False)
            frame = np.frombuffer(data, dtype=np.int16)
            rms = int(np.sqrt(np.mean(frame.astype(np.float32)**2)))
            bar = '█' * (rms // 100) + '░' * (50 - rms // 100)
            print(f'\r RMS {rms:4d}  {bar}', end='', flush=True)

            if rms > SILENCE_THRESHOLD:
                await source.capture_frame(rtc.AudioFrame(
                    data=frame.tobytes(),
                    sample_rate=48000,
                    samples_per_channel=480,
                    num_channels=1))
            else:
                await asyncio.sleep(0.01)  # avoid busy loop when silent
    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()
    #         print('.', end='', flush=True) # Indicate activity
    # finally:
    #     stream.stop_stream()
    #     stream.close()
    #     pa.terminate()


async def main() -> None:
    # The room object
    room = rtc.Room()

    # Define event handlers
    @room.on("participant_connected")
    def on_participant_connected(participant):
        print(f"👋  {participant.identity} connected")

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        print(f"👋  {participant.identity} disconnected")

    @room.on("data_received")
    def on_data_received(payload: bytes, participant, kind):
        print(f"📨  Got message: {payload.decode()}")

    # 3) Connect to the room
    print("Connecting…")
    await room.connect(WS_URL, USER_TOKEN)
    
    # Subscribe to all existing audio tracks
    for participant in room.remote_participants.values():
        for pub in participant.tracks.values():
            if pub.kind == rtc.TrackKind.KIND_AUDIO:
                await pub.set_subscribed(True)
    
    print(f"✅  Connected to room: {ROOM_NAME}")

    #SID = room's unique ID
    print(f"    SID: {await room.sid}")
    all_ids = [room.local_participant.identity] + list(room.remote_participants.keys())
    print(f"Participants: {all_ids}")
    # print(f"    Participants: {[p.identity for p in room.participants]}")
    
    await publish_microphone(room.local_participant)
    try:
        await asyncio.Event().wait()  # wait for a moment to ensure track is published
    except KeyboardInterrupt:
        print("Interrupted. Leaving...")
    finally:
        await room.disconnect()

    
    # Keep the script alive until Ctrl-C
    # try:
    #     while True:
    #         await asyncio.sleep(1)
    # except KeyboardInterrupt:
    #     print("Leaving…")
    # finally:
    #     await room.disconnect()

if __name__ == "__main__":
    asyncio.run(main())