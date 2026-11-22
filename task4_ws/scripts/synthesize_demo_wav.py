"""Synthesize a Mandarin test instruction into a local 16 kHz PCM WAV."""

import argparse
import audioop
from io import BytesIO
from pathlib import Path
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("text", help="Text to synthesize")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", type=Path, default=Path(
        "models/weights/piper-huayan/zh_CN-huayan-medium.onnx"
    ))
    args = parser.parse_args()
    if not args.text.strip():
        parser.error("text must contain a spoken instruction")

    from piper import PiperVoice

    voice = PiperVoice.load(args.model)
    native = BytesIO()
    with wave.open(native, "wb") as recording:
        voice.synthesize_wav(args.text, recording)
    native.seek(0)
    with wave.open(native, "rb") as recording:
        if (recording.getnchannels(), recording.getsampwidth()) != (1, 2):
            raise ValueError("Piper must produce mono 16-bit PCM")
        samples, _ = audioop.ratecv(
            recording.readframes(recording.getnframes()), 2, 1, recording.getframerate(), 16000, None
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.out), "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(samples)


if __name__ == "__main__":
    main()
