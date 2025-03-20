import os
import time
import sounddevice as sd
from src.classification.utils.audio_student import AudioUtil  # Gestion audio

def loading_animation():
    """ Affiche un chargement de 2 secondes (compteur de 1 à 10). """
    for i in range(1, 11):
        print(f"⏳ Chargement... {i}/10", end="\r")
        time.sleep(0.1)
    print(" " * 20, end="\r")  # Efface la ligne après la fin du chargement

def play_audio_files(directory_path, pause=0):
    """ Joue tous les fichiers audio .wav du dossier sans enregistrer ni logger. """
    if not os.path.exists(directory_path):
        print("❌ Dossier introuvable.")
        return

    all_audio_files = sorted(f for f in os.listdir(directory_path) if f.endswith(".wav"))

    if not all_audio_files:
        print("❌ Aucun fichier .wav trouvé.")
        return

    print(f"🎵 Lecture de {len(all_audio_files)} fichiers avec une pause de {pause}s.")

    for idx, audio_file in enumerate(all_audio_files, start=1):
        file_path = os.path.join(directory_path, audio_file)

        print(f"▶️ Lecture : {audio_file}")
        try:
            audio_data = AudioUtil.open(file_path)
            sample_rate = audio_data[1]

            # Jouer l'audio
            sd.play(audio_data[0], sample_rate)
            sd.wait()  # Attendre la fin du son
            print("✅ Son terminé.")

            # Pause après la lecture
            time.sleep(pause)

            # Ajout du chargement de 2 secondes
            loading_animation()

        except Exception as error:
            print(f"⚠️ Erreur avec {audio_file} : {error}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Lecture audio sans enregistrement ni log.")
    parser.add_argument("--delay", type=float, default=0, help="Pause entre les sons (par défaut: 0s).")

    args = parser.parse_args()

    audio_folder = r'classification\src\classification\datasets\soundfiles'
    play_audio_files(audio_folder, args.delay)
