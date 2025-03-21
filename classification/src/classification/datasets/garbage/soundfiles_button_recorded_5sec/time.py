import soundfile as sf

# Provide the full path of the file
file_path = "LELEC210X/classification/src/classification/datasets/soundfiles/gunshot_06.wav"

with sf.SoundFile(file_path) as audio_file:
    duration = len(audio_file) / audio_file.samplerate
    print(f"Duration of {file_path}: {duration:.2f} seconds")