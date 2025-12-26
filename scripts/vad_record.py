import webrtcvad
import sounddevice as sd
import collections
import time
import wave
import numpy as np
import threading
import subprocess
import os 


DIR_PATH = os.path.dirname(os.path.realpath(__file__))

SAMPLE_RATE = 16000
FRAME_DURATION = 30
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)

vad = webrtcvad.Vad(3)

ring_buffer = collections.deque(maxlen=15)
voiced_frames = []

triggered = False
silent_frames = 0

SILENCE_FRAMES_TO_STOP = 50
ENERGY_THRESHOLD = 80

stop_event = threading.Event()

def rms(frame):
    samples = np.frombuffer(frame, dtype=np.int16)
    return np.mean(np.abs(samples))



def callback(indata, frames, time_info, status):
    global triggered, silent_frames

    if stop_event.is_set():
        return

    frame = bytes(indata)
    energy = rms(frame)
    speech = vad.is_speech(frame, SAMPLE_RATE) and energy > ENERGY_THRESHOLD

    if not triggered:
        ring_buffer.append((frame, speech))
        if sum(1 for _, s in ring_buffer if s) > 8:
            triggered = True
            for f, _ in ring_buffer:
                voiced_frames.append(f)
            ring_buffer.clear()
    else:
        voiced_frames.append(frame)

        if speech:
            silent_frames = 0
        else:
            silent_frames += 1

        if silent_frames > SILENCE_FRAMES_TO_STOP:
            stop_event.set()

def a(indata, frames, time_info, status):
    global ENERGY_THRESHOLD
    i=0
    while ((i<20)):
        frame = bytes(indata)
        t = rms(frame)
        i += 1
        if t < ENERGY_THRESHOLD:
            ENERGY_THRESHOLD = t


stream = sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE,
    dtype="int16",
    channels=1,
    callback=a
)
stream.start()
time.sleep(3)
stream.stop()
stream.close()
print(f"Set energy threshold to {ENERGY_THRESHOLD}")
print("Listening...")
#subprocess.run(["eww", "open", "assistant"])
#subprocess.run(["eww", "update", "mode=listening"])

stream = sd.RawInputStream(
    samplerate=SAMPLE_RATE,
    blocksize=FRAME_SIZE,
    dtype="int16",
    channels=1,
    callback=callback
)

stream.start()

stop_event.wait()

stream.stop()
stream.close()
wf = wave.open(f"{DIR_PATH.replace('/scripts', '/tmp')}/query.wav", "wb")
wf.setnchannels(1)
wf.setsampwidth(2)
wf.setframerate(SAMPLE_RATE)
wf.writeframes(b"".join(voiced_frames))
wf.close()

print("Recording stopped")


