#!/usr/bin/env python3
import os
from pydub import AudioSegment

def split_and_merge_by_class(filenames, class_mapping, output_dir="soundfiles_2"):
    os.makedirs(output_dir, exist_ok=True)

    class_counters = {}  # Pour suivre l'index des fichiers par classe

    for file in filenames:
        filepath = os.path.join("recordings", file)
        
        # Charger le fichier audio
        audio = AudioSegment.from_wav(filepath)

        # Déduire le nom de la classe via le mapping fourni
        base_name = class_mapping[file]

        # Compter combien de segments on peut faire (en secondes pleines)
        full_segments = len(audio) // 1000

        # Initialiser le compteur de segments pour cette classe
        if base_name not in class_counters:
            class_counters[base_name] = 0

        for i in range(full_segments):
            start_ms = i * 1000
            end_ms = (i + 1) * 1000
            chunk = audio[start_ms:end_ms]

            # Index global pour cette classe
            index = class_counters[base_name]
            output_filename = f"{base_name}_{index:02d}.wav"
            output_path = os.path.join(output_dir, output_filename)

            chunk.export(output_path, format="wav")
            print(f"Exported {output_path}")
            
            class_counters[base_name] += 1

if __name__ == "__main__":
    files_to_split = [
        "fire_2.wav", "fireworks_2.wav", "chainsaw_2.wav", "gunshot_2.wav",
        "chainsaw_youtube.wav", "fire_youtube.wav", "fireworks_youtube.wav", "gunshot_youtube.wav"
    ]

    # Mapping fichier -> nom de classe
    class_mapping = {
        "fire_2.wav": "fire",
        "fireworks_2.wav": "fireworks",
        "chainsaw_2.wav": "chainsaw",
        "gunshot_2.wav": "gunshot",
        "chainsaw_youtube.wav": "chainsaw",
        "fire_youtube.wav": "fire",
        "fireworks_youtube.wav": "fireworks",
        "gunshot_youtube.wav": "gunshot"
    }

    split_and_merge_by_class(files_to_split, class_mapping)