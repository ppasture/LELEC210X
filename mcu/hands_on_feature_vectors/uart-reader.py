import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
from serial.tools import list_ports
import pickle
import os

from classification.utils.plots import plot_specgram_textlabel

# ====================================================
# ===          CONFIGURATION MANUELLE              ===
# ====================================================
MODELTYPE = "xgb"          # "rf" ou "xgb"
PCA = True                # True ou False
AUGMENTATION = True      # True ou False
NORMALISATION = False      # True ou False

LOG_PATH = "../../classification/data/played_sounds/predicted_sounds.txt"
if MODELTYPE == "rf":
    MODEL_DIR = "../../classification/data/models/random_forest/"
else:
    MODEL_DIR = "../../classification/data/models/xgboost/"

PRINT_PREFIX = "DF:HEX:"
FREQ_SAMPLING = 10200
MELVEC_LENGTH = 20
N_MELVECS = 20

dt = np.dtype(np.uint16).newbyteorder("<")


# ====================================================
# ===                Fonctions utiles              ===
# ====================================================

def parse_buffer(line):
    line = line.strip()
    if line.startswith(PRINT_PREFIX):
        return bytes.fromhex(line[len(PRINT_PREFIX):])
    else:
        print(line)
        return None


def reader(port=None):
    ser = serial.Serial(port=port, baudrate=115200)
    while True:
        line = ""
        while not line.endswith("\n"):
            line += ser.read_until(b"\n", size=2 * N_MELVECS * MELVEC_LENGTH).decode("ascii")
        line = line.strip()
        buffer = parse_buffer(line)
        if buffer is not None:
            buffer_array = np.frombuffer(buffer, dtype=dt)
            yield buffer_array


def build_model_filename(modeltype, pca, aug, norm):
    pca_str = "pca" if pca else "nopca"
    aug_str = "aug" if aug else "noaug"
    norm_str = "norm" if norm else "nonorm"
    return f"{modeltype}_{pca_str}_{aug_str}_{norm_str}.pickle"


# ====================================================
# ===           Démarrage du programme             ===
# ====================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Nom du port série (ex: COM3, /dev/ttyUSB0)", required=False)
    args = parser.parse_args()

    print("uart-reader lancé...\n")

    if args.port is None:
        print("Aucun port spécifié. Ports disponibles :")
        print("================")
        for p in list_ports.comports():
            print(p.device)
        print("================")
        print("Lance le script avec [-p NOM_DU_PORT] pour accéder au port série.")
        exit(0)

    # === Chargement du modèle ===
    model_filename = build_model_filename(MODELTYPE, PCA, AUGMENTATION, NORMALISATION)
    model_path = os.path.join(MODEL_DIR, model_filename)

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle introuvable : {model_path}")

    model = pickle.load(open(model_path, "rb"))
    print(f"Modèle chargé : {model_filename} ({type(model).__name__})")

    # === Chargement du PCA si demandé ===
    if PCA:
        # Remove "rf_" or "xgb_" from the model filename
        pca_filename = model_filename.split("_", 1)[1]  # get everything after first "_"
        pca_path = os.path.join(MODEL_DIR, pca_filename)
        if not os.path.exists(pca_path):
            raise FileNotFoundError(f"PCA introuvable : {pca_path}")
        pca = pickle.load(open(pca_path, "rb"))
        print(f"PCA chargé : {pca_filename}")
    else:
        pca = None

    input_stream = reader(port=args.port)
    msg_counter = 0
    plt.figure(figsize=(8, 6))

    with open(LOG_PATH, "a") as log_file:
        log_file.write("# Predicted Classes for Played Sounds\n\n")

        for melvec in input_stream:
            msg_counter += 1
            print(f"\nMEL Spectrogram #{msg_counter}")

            fv = melvec.reshape(1, -1)
            if np.linalg.norm(fv) < 400:
                print("Valeur trop faible, on ignore ce melvec")
                continue
            # Normalisation locale
            norm_val = np.linalg.norm(fv)
            if norm_val != 0 and NORMALISATION:
                fv = fv / norm_val

            # PCA transformation
            if pca is not None:
                fv = pca.transform(fv)

            # Prediction
            pred = model.predict(fv)

            proba = model.predict_proba(fv) if hasattr(model, "predict_proba") else None

            print(f"Predicted class: {pred[0]}")
            if proba is not None:
                print(f"Probabilities: {proba}")

            # Logging
            log_entry = f"Sound #{msg_counter}: Predicted class: {pred[0]}\n"
            log_file.write(log_entry)
            log_file.flush()

            # Format predicted label text
            if proba is not None and hasattr(model, "classes_"):
                class_names = model.classes_
                class_names_str = ["chainsaw", "fire", "fireworks", "gunshot"]
                probabilities = np.round(proba[0] * 100, 2)
                max_len = max(len(name) for name in class_names_str)
                probabilities_str = " ".join([f"{prob:.2f}%".ljust(max_len) for prob in probabilities])
                textlabel = f"{class_names_str}\n{probabilities_str}\n\nPredicted class: {class_names_str[pred[0]]}"
            else:
                textlabel = f"Predicted class: {class_names_str[pred[0]]}"

            # Plot
            plot_specgram_textlabel(
                melvec.reshape((N_MELVECS, MELVEC_LENGTH)).T,
                ax=plt.gca(),
                is_mel=True,
                title=f"MEL Spectrogram #{msg_counter}",
                xlabel="Mel vector",
                textlabel=textlabel,
            )
            plt.draw()
            #plt.savefig(f"../../classification/data/played_sounds/melspectrograms_played_sounds/melspec_{msg_counter}.pdf")
            plt.pause(0.1)
            plt.clf()
