import os
import wave
import contextlib

from pydub import AudioSegment

# Nom du fichier source
input_filename = "background_recorded.wav"
output_filename = "background_cropped.wav"

# Charger l'audio
audio = AudioSegment.from_wav(input_filename)

# Garder les 5 premières secondes (5000 ms)
cropped_audio = audio[5000:]

# Exporter dans un nouveau fichier
cropped_audio.export(output_filename, format="wav")

print(f"Cropped file saved as {output_filename}")