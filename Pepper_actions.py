import argparse
import qi
import time
from moviepy import VideoFileClip, AudioFileClip
from datetime import datetime

# # Replace with your Pepper's IP address
PEPPER_IP = "169.254.246.50"
PORT = 9559

def pepper_wave(session, ip=PEPPER_IP, port=PORT):
    print("I'm here to wave at you!")
    motion_service = session.service("ALMotion")
    posture_service = session.service("ALRobotPosture")

    # Stand up straight (optional)
    posture_service.goToPosture("StandInit", 0.5)

    names = ["RShoulderPitch", "RShoulderRoll", "RElbowYaw", "RElbowRoll", "RWristYaw"]
    # Start pose (hand up, ready to wave)
    wave_down = [-0.195, -0.655, 1.2, 1.0, 0.0]

    wave_up = [-0.195, -0.657, 1.2, 0.5, 0.0]
    fractionMaxSpeed = 0.2 #Lower speed for smoother motion

    # Move to wave-up position smoothly
    motion_service.angleInterpolationWithSpeed(names, wave_up, fractionMaxSpeed)
 

    # Move to starting wave position

    motion_service.setAngles(names, wave_down, fractionMaxSpeed)
    time.sleep(1)

    # Wave hand back and forth
    for _ in range(3):
        # motion_service.setAngles(names, wave_up, fractionMaxSpeed)
        motion_service.angleInterpolationWithSpeed(names, wave_down, fractionMaxSpeed)
        time.sleep(0.5)
        motion_service.angleInterpolationWithSpeed(names, wave_up, fractionMaxSpeed)
        # motion_service.setAngles(names, wave_down, fractionMaxSpeed)
        time.sleep(0.5)


def record_audio(session, duration_sec=5, filename="pepper_audio"):
    tts = session.service("ALTextToSpeech")
    audio_recorder = session.service("ALAudioRecorder")
    output_path = f"/home/nao/recordings/microphones/{filename}.wav"
    tts.say("Recording audio now. Say hi.")
    channels = [0, 0, 1, 0]  # Use front mic; [FL, FR, Center, Rear]
    audio_recorder.startMicrophonesRecording(output_path, "wav", 16000, channels)
    print("Recording audio...")
    time.sleep(duration_sec)
    audio_recorder.stopMicrophonesRecording()
    print(f"Audio was saved on the robot: {output_path}")
    return output_path



def record_video(session, duration_sec=5, filename="myvideo"):
    import paramiko
    # Get the ALVideoRecorder service
    video_recorder = session.service("ALVideoRecorder")

    # Set video parameters
    video_recorder.setResolution(2)        # 1=320x240, 2=640x480, .. resolution
    video_recorder.setFrameRate(15)        # 15 fps
    video_recorder.setVideoFormat("MJPG")  # MJPG format
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"pepper_video_{timestamp}"
    # Start recording
    video_recorder.startRecording("/home/nao/recordings/cameras", filename)
    print(f"Recording video for {duration_sec} seconds...")
    time.sleep(duration_sec)

    # Stop recording
    video_info = video_recorder.stopRecording()
    print("Video was saved on the robot:", video_info) #video_info is a tuple with (filename, resolution, framerate)
    PEPPER_USER = "nao"
    PEPPER_PASS = "nao"
    REMOTE_PATH = video_info[1]  # This is the filename returned by stopRecording
    LOCAL_PATH = f"./{filename}.avi"
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(PEPPER_IP, username=PEPPER_USER, password=PEPPER_PASS)

    sftp = ssh.open_sftp()
    sftp.get(REMOTE_PATH, LOCAL_PATH)
    sftp.close()
    ssh.close()
    print(f"Video {filename} downloaded to your computer!")
    return LOCAL_PATH

def merge_audio_video(video_path, audio_path, output_path):
    """
    Merges the specified audio file with the video file and writes the combined file to output_path.

    Args:
        video_path (str): Path to the input video file (e.g., .avi).
        audio_path (str): Path to the input audio file (e.g., .wav).
        output_path (str): Path for the output merged video file (e.g., .mp4).
    """
    # from moviepy.editor import VideoFileClip, AudioFileClip

    # Load the video and audio clips
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)

    # Set the audio for the video clip
    final_clip = video_clip.with_audio(audio_clip)

    # Write the result to a new file
    final_clip.write_videofile(output_path)

    print(f"Merged video saved as {output_path}")
    return output_path


def main():
    # Connect to the robot session
    session = qi.Session()
    filename = "pepper_video_20250708_155419.avi"
    try:
        session.connect(f"tcp://{PEPPER_IP}:{PORT}")
        pepper_wave(session)
        tts = session.service("ALTextToSpeech")  # Pause speech recognition if needed
        tts.say("Hello! Let's wave together!")
        time.sleep(2)  # Wait for the speech to finish
        vidpath = record_video(session, duration_sec=5, filename="pepper_wave_video")
        audpath = record_audio(session, duration_sec=5, filename="pepper_wave_audio")
        tts.say("Recording complete. Thank you for waving with me!")
        print(audpath, vidpath)
        # merge_audio_video(f"/home/nao/recordings/microphones/{filename}", )
    except RuntimeError:
        print(f"Could not connect to Pepper at {PEPPER_IP}:{PORT}. Please check the IP address and port.")
        return 
    

# def main(session):
#     motion   = session.service("ALMotion")
#     posture  = session.service("ALRobotPosture")

#     # Make sure stiffness is on
#     motion.setStiffnesses("Body", 1.0)

#     try:
#         wave(motion, posture)
#     finally:
#         # Always relax joints afterwards
#         motion.setStiffnesses("Body", 0.0)
    

# if __name__ == "__main__":
#     parser = argparse.ArgumentParser(description="Make Pepper wave hello.")
#     parser.add_argument("--ip", default="127.0.0.1",
#                         help="Robot IP address. Default is 127.0.0.1")
#     parser.add_argument("--port", type=int, default=9559,
#                         help="Naoqi port. Default is 9559.")
#     args = parser.parse_args()

#     # Connect to the robot
#     session = qi.Session()
#     try:
#         session.connect("tcp://{}:{}".format(args.ip, args.port))
#     except RuntimeError:
#         print("Can't connect to Naoqi at {}:{}".format(args.ip, args.port))
#         exit(1)

#     main(session)

if __name__ == "__main__":
    main()