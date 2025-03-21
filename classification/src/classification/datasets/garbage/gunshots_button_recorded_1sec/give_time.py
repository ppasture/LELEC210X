import os
import librosa

def print_audio_durations(directory):
    for filename in os.listdir(directory):
        if filename.endswith(".wav"):
            filepath = os.path.join(directory, filename)
            try:
                audio, sr = librosa.load(filepath, sr=None)
                duration = len(audio) / sr
                print(f"{filename}: {duration:.3f} seconds")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    file_path = "classification/src/classification/datasets/garbage/gunshots_button_recorded_1sec"
    print_audio_durations(file_path)
