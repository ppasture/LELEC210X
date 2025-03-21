#!/usr/bin/env python3
import os
from pydub import AudioSegment

def split_into_one_second_segments(filenames, output_dir="new_soundfiles"):
    os.makedirs(output_dir, exist_ok=True)

    for file in filenames:
        # Load the audio file
        audio = AudioSegment.from_wav(file)
        
        # Extract the base name without extension (e.g., "fire" from "fire.wav")
        base_name = os.path.splitext(file)[0]
        
        # Length of the audio in milliseconds
        audio_length_ms = len(audio)
        
        # Determine how many full 1-second segments we can get
        # (Integer division by 1000 to avoid partial segments)
        full_segments = audio_length_ms // 1000
        
        for i in range(full_segments):
            start_ms = i * 1000
            end_ms = (i + 1) * 1000
            
            # Extract 1-second chunk
            chunk = audio[start_ms:end_ms]
            
            # Build output filename, e.g., "fire_00.wav", "fire_01.wav", etc.
            output_filename = f"{base_name}_{i:02d}.wav"
            output_path = os.path.join(output_dir, output_filename)
            
            # Export the segment as a .wav file
            chunk.export(output_path, format="wav")
            print(f"Exported {output_path}")

if __name__ == "__main__":
    files_to_split = ["fire.wav", "fireworks.wav", "chainsaw.wav"]
    split_into_one_second_segments(files_to_split)
