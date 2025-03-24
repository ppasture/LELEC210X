import os
import time
from src.classification.utils.audio_student import AudioUtil  # Importing AudioUtil for audio operations

def play_audio_files(directory_path, pause=0, log_path="classification/history_of_played_sounds.txt"):
    """
    Play exactly 40 files per class sequentially from the specified directory.
    The files are played in alphabetical order within each class.

    :param directory_path: Directory containing .wav audio files.
    :param pause: Pause duration (in seconds) between consecutive files.
    :param log_path: File path for storing playback logs.
    """
    # Retrieve all .wav files from the specified directory
    all_audio_files = [f for f in os.listdir(directory_path) if f.endswith(".wav")]

    if not all_audio_files:
        print("No .wav files found in the provided directory.")
        return

    # Group files by class
    class_groups = {}
    for audio_file in all_audio_files: 
        label = audio_file.split("_")[0] if "_" in audio_file else "Unknown"
        if label == "fire" or label == "chainsaw" or label == "gunshot":
            continue

        if label not in class_groups:
            class_groups[label] = []
        class_groups[label].append(audio_file)
    
    # Sort files within each class and take the first 40 (if available)
    selected_audio_files = []
    for label, files in sorted(class_groups.items()):  # Sort classes alphabetically
        files.sort()  # Sort files alphabetically within the class
        if len(files) < 40:
            print(f"Not enough files in class '{label}' to select 40. Found {len(files)} files.")
            return
        selected_files = files[:40]  # Take the first 40 files in alphabetical order
        selected_audio_files.extend(selected_files)
    
    print(f"Playing files ({len(selected_audio_files)} total) sequentially with a pause of {pause}s.")

    # Open the log file for recording playback details
    with open(log_path, "w") as log_file:
        log_file.write("Index\tLabel/Class\n")
        log_file.write("=" * 30 + "\n")

        for idx, audio_file in enumerate(selected_audio_files, start=1):
            file_path = os.path.join(directory_path, audio_file)

            # Derive the label/class from the filename (text before the first '_')
            label = audio_file.split("_")[0] if "_" in audio_file else "Unknown"

            print(f"Now playing: {audio_file} (Label: {label})")
            log_file.write(f"{idx}\t{label}\n")

            try:
                # Load the audio file
                audio_data = AudioUtil.open(file_path)

                # Play the audio file
                AudioUtil.play(audio_data)

                # Calculate playback duration and add the specified pause
                playback_time = len(audio_data[0]) / audio_data[1]  # samples / sample_rate
                time.sleep(playback_time + pause)
            except Exception as error:
                print(f"Failed to play {audio_file}: {error}")
                log_file.write(f"{idx}\t{label} - ERROR: {error}\n")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Audio playback tool for selected .wav files in a directory.")
    parser.add_argument("--delay", type=float, default=0, help="Pause duration between playback (default: 0 seconds).")
    parser.add_argument("--log", type=str, default="classification/data/played_sounds/history_of_played_sounds.txt", help="Path to the log file (default: classification/history_of_played_sounds.txt).")

    args = parser.parse_args()

    audio_folder = 'classification/src/classification/datasets/soundfiles'
    play_audio_files(audio_folder, args.delay, args.log)
