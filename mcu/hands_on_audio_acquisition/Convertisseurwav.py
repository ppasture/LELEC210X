#!/usr/bin/env python3
import argparse
import numpy as np
import soundfile as sf

FREQ_SAMPLING = 10200
VAL_MAX_ADC = 4096
VDD = 3.3
BUFFER_SIZE = 50000  # Taille en octets par message

def process_message(buffer):
    # Convertir le buffer en tableau numpy de uint16 en littl-endian
    dt = np.dtype(np.uint16).newbyteorder("<")
    data = np.frombuffer(buffer, dtype=dt)
    return data

def generate_audio(buf, file_name):
    buf = np.asarray(buf, dtype=np.float64)
    buf = buf - np.mean(buf)
    if np.max(np.abs(buf)) != 0:
        buf /= np.max(np.abs(buf))
    sf.write(f"{file_name}.wav", buf, FREQ_SAMPLING)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Conversion d'un fichier binaire en fichiers .wav.")
    parser.add_argument("-i", "--input", help="Fichier binaire d'entrée", required=True)
    parser.add_argument("-o", "--output_prefix", help="Préfixe pour les fichiers wav générés", default="audio")
    args = parser.parse_args()

    with open(args.input, "rb") as f:
        file_content = f.read()

    total_size = len(file_content)
    print(f"Taille totale du fichier binaire : {total_size} octets.")

    # Calcul du nombre de messages complets dans le fichier
    num_messages = total_size // BUFFER_SIZE
    print(f"Nombre de messages complets trouvés : {num_messages}")

    for i in range(num_messages):
        buffer = file_content[i * BUFFER_SIZE:(i + 1) * BUFFER_SIZE]
        data = process_message(buffer)
        output_file = f"{args.output_prefix}_{i:02d}"
        print(f"Traitement du message {i} -> {output_file}.wav")
        generate_audio(data, output_file)

