import os
import time
import sounddevice as sd
import numpy as np
import wave
import scipy.io.wavfile as wav
from src.classification.utils.audio_student import AudioUtil  # Gestion audio

def record_audio(duration, sample_rate, output_path):
    """ Enregistre l'audio du microphone et sauvegarde dans un fichier .wav. """
    print(f"Enregistrement en cours : {output_path}")
    recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16)
    sd.wait()  # Attendre la fin de l'enregistrement

    # Sauvegarde du fichier enregistré
    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())

    print(f"Enregistrement sauvegardé : {output_path}")

def play_audio_files(directory_path, output_directory, pause=0, log_path="classification/history_of_played_sounds.txt"):
    """
    Joue *tous* les fichiers audio .wav du dossier *dans l'ordre exact* et enregistre simultanément.
    """
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)  # Crée le dossier de sauvegarde s'il n'existe pas

    all_audio_files = [f for f in os.listdir(directory_path) if f.endswith(".wav")]
    
    if not all_audio_files:
        print("Aucun fichier .wav trouvé.")
        return

    # 🔹 Trier les fichiers par ordre alphabétique
    all_audio_files.sort()

    print(f"Lecture de {len(all_audio_files)} fichiers avec une pause de {pause}s.")

    with open(log_path, "w") as log_file:
        log_file.write("Index\tLabel/Class\n")
        log_file.write("=" * 30 + "\n")

        for idx, audio_file in enumerate(all_audio_files, start=1):
            file_path = os.path.join(directory_path, audio_file)
            label = audio_file.split("")[0] if "" in audio_file else "Unknown"
            output_file_path = os.path.join(output_directory, audio_file)  # Même nom de fichier

            print(f"Lecture : {audio_file} (Classe : {label})")
            log_file.write(f"{idx}\t{label}\n")

            try:
                # Charger et jouer l'audio
                audio_data = AudioUtil.open(file_path)
                sample_rate = audio_data[1]  # Fréquence d'échantillonnage
                duration = len(audio_data[0]) / sample_rate  # Durée de lecture
                
                # Jouer le son avec sounddevice pour éviter les problèmes de AudioUtil.play()
                print(f"Lecture en cours : {file_path}")
                sd.play(audio_data[0], sample_rate)
                sd.wait()  # Attendre la fin du son
                print("Son terminé.")

                # Démarrer l'enregistrement
                record_audio(duration, sample_rate, output_file_path)

                # Pause après la lecture
                time.sleep(pause)
            except Exception as error:
                print(f"Erreur avec {audio_file} : {error}")
                log_file.write(f"{idx}\t{label} - ERREUR: {error}\n")

if _name_ == "_main_":
    import argparse

    parser = argparse.ArgumentParser(description="Lecture et enregistrement audio simultané.")
    parser.add_argument("--delay", type=float, default=0, help="Pause entre les sons (par défaut: 0s).")
    parser.add_argument("--log", type=str, default="src/classification/datasets/played_sounds/history_of_played_sounds.txt", help="Fichier de log.")
    parser.add_argument("--output", type=str, default="src/classification/datasets/new_dataset", help="Dossier pour sauvegarder les enregistrements.")

    args = parser.parse_args()

    audio_folder = 'src/classification/datasets/soundfiles'
    play_audio_files(audio_folder, args.output, args.delay, args.log)