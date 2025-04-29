import os
import matplotlib.pyplot as plt
import numpy as np
import librosa
import librosa.display
from src.classification.utils.audio_student import AudioUtil  # Utilisé pour charger les fichiers audio

def create_spectrograms(input_directory, output_directory):
    """
    Parcourt tous les fichiers .wav dans le dossier d'entrée, calcule leur spectrogramme et
    sauvegarde chaque image au format PDF dans le dossier de sortie.
    
    :param input_directory: Chemin du dossier contenant les fichiers audio (.wav).
    :param output_directory: Chemin du dossier où sauvegarder les PDF des spectrogrammes.
    """
    # Créer le dossier de sortie s'il n'existe pas
    os.makedirs(output_directory, exist_ok=True)
    
    # Liste de tous les fichiers .wav dans le dossier d'entrée
    audio_files = [f for f in os.listdir(input_directory) if f.endswith(".wav")]
    
    if not audio_files:
        print("Aucun fichier .wav trouvé dans le dossier spécifié.")
        return
    
    for audio_file in audio_files:
        file_path = os.path.join(input_directory, audio_file)
        try:
            # Charger le fichier audio via AudioUtil.open
            # On suppose que AudioUtil.open renvoie un tuple (data, sample_rate)
            audio_data, sr = AudioUtil.open(file_path)
            # Si audio_data est multicanal, prendre la première piste
            if audio_data.ndim > 1:
                audio_data = audio_data[0]
            
            # Calculer le spectrogramme via la transformée de Fourier à court terme
            S = np.abs(librosa.stft(audio_data))
            S_db = librosa.amplitude_to_db(S, ref=np.max)
            
            # Création de la figure
            plt.figure(figsize=(10, 4))
            librosa.display.specshow(S_db, sr=sr, x_axis='time', y_axis='log', cmap='magma')
            plt.colorbar(format='%+2.0f dB')
            plt.title(f"Spectrogramme de {audio_file}")
            plt.tight_layout()
            
            # Nom du fichier PDF de sortie
            base_name = os.path.splitext(audio_file)[0]
            output_file = os.path.join(output_directory, f"{base_name}.pdf")
            plt.savefig(output_file, format='pdf')
            plt.close()
            print(f"Spectrogramme sauvegardé: {output_file}")
            
        except Exception as e:
            print(f"Erreur lors du traitement de {audio_file}: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Génération de spectrogrammes en PDF pour tous les sons d'un dossier.")
    parser.add_argument("--input", type=str, default="classification/src/classification/datasets/soundfiles",
                        help="Chemin du dossier contenant les fichiers audio (.wav).")
    parser.add_argument("--output", type=str, default="classification/data/spectrograms",
                        help="Chemin du dossier de sortie pour les PDF des spectrogrammes.")
    args = parser.parse_args()
    
    create_spectrograms(args.input, args.output)
