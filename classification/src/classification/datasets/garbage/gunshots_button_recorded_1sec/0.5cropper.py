import os
import librosa
import soundfile as sf

def crop_audio_files(directory, crop_duration=0.3):
    classes = ["gunshot"]
    
    for classname in classes:
        for i in range(40):
            filename = f"{classname}_{i:02d}.wav"
            filepath = os.path.join(directory, filename)
            
            if os.path.exists(filepath):
                audio, sr = librosa.load(filepath, sr=None)
                cropped_audio = audio[:int(len(audio) - crop_duration * sr)]  # Remove last 0.5 sec
                sf.write(filepath, cropped_audio, sr)  # Overwrite the file
                print(f"Processed: {filename}")
            else:
                print(f"File not found: {filename}")

if __name__ == "__main__":
    file_path = "classification/src/classification/datasets/garbage/gunshots_button_recorded_1sec"
    crop_audio_files(file_path)
