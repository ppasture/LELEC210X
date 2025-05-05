#!/usr/bin/env python3
from pydub import AudioSegment

def convert_mp4_to_wav(input_filename, output_filename):
    # Load the MP4 file
    audio = AudioSegment.from_file(input_filename, format="mp4")
    # Export as WAV
    audio.export(output_filename, format="wav")
    print(f"Converted '{input_filename}' to '{output_filename}'")

if __name__ == "__main__":
    input_file = "gunshot.mp4"
    output_file = "gunshot.wav"
    convert_mp4_to_wav(input_file, output_file)