#!/usr/bin/env python3
import os
import glob
import soundfile as sf
import numpy as np
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Concaténer tous les fichiers audio (.wav) du dossier courant en un seul fichier audio.")
    parser.add_argument("-o", "--output", default="merged.wav",
                        help="Nom du fichier audio de sortie (par défaut: merged.wav)")
    args = parser.parse_args()

    # Recherche des fichiers .wav dans le dossier courant, triés par ordre alphabétique
    audio_files = sorted(glob.glob("*.wav"))
    if not audio_files:
        print("Aucun fichier .wav trouvé dans le dossier courant.")
        return

    print("Fichiers trouvés :", audio_files)

    combined_audio = []
    sample_rate = None

    # Chargement de chaque fichier et vérification du taux d'échantillonnage
    for file in audio_files:
        print(f"Lecture de {file}...")
        data, sr = sf.read(file)
        if sample_rate is None:
            sample_rate = sr
        elif sr != sample_rate:
            print(f"Attention : le fichier {file} a un taux d'échantillonnage différent ({sr}) "
                  f"du taux de référence ({sample_rate}). Il sera ignoré.")
            continue
        combined_audio.append(data)

    if not combined_audio:
        print("Aucun audio compatible trouvé.")
        return

    # Concaténation de tous les tableaux audio
    combined_audio = np.concatenate(combined_audio)
    
    # Sauvegarde du fichier audio concaténé
    sf.write(args.output, combined_audio, sample_rate)
    print(f"Fichier audio concaténé enregistré sous : {args.output}")

if __name__ == "__main__":
    main()
