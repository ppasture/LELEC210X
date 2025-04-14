import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
from serial.tools import list_ports
import pickle
import os
import time
import sys
import pygame
from pydub import AudioSegment
from datetime import datetime
from pydub.playback import play
from tensorflow.keras.models import load_model

from classification.utils.plots import plot_specgram_textlabel
from classification.utils.plots import (
    plot_decision_boundaries,
    plot_specgram,
    show_confusion_matrix,
)

# ====================================================
# ===          CONFIGURATION MANUELLE              ===
# ====================================================
MODELTYPE = "cnn"      # "rf", "xgb", ou "cnn"
PCA = False            # True ou False
AUGMENTATION = True  # True ou False
NORMALISATION = False  # True ou False

CONTEST = True         # True => écoute et compare avec ground truth
RECORDED = False

ALPHA = 0.75
ENERGY_MULTIPLIER = 1
avg_energy = 0.0

CONTEST_WAV = "../../classification/contest_simulator/contest_ESC50_sounds.wav"
EVENT_LOG_PATH = "../../classification/contest_simulator/event_log_ESC50_sounds.txt"
if RECORDED:
    CONTEST_WAV = "../../classification/contest_simulator/contest_recorded_sounds.wav"
    EVENT_LOG_PATH = "../../classification/contest_simulator/event_log_recorded_sounds.txt"

LOG_PATH = "../../classification/data/played_sounds/predicted_sounds.txt"
MODEL_DIR = f"../../classification/data/models/{MODELTYPE}/"

PRINT_PREFIX = "DF:HEX:"
FREQ_SAMPLING = 10200
MELVEC_LENGTH = 20
N_MELVECS = 20

dt = np.dtype(np.uint16).newbyteorder("<")

# ====================================================
# ===                Fonctions utiles              ===
# ====================================================

def sound_bigger_than_adaptive_threshold(buf):
    global avg_energy
    buf = buf.reshape((20, 20)).T
    energies = np.sum(buf ** 2, axis=1)
    total_energy = np.sum(energies)
    avg_energy = ALPHA * avg_energy + (1.0 - ALPHA) * total_energy
    threshold = ENERGY_MULTIPLIER * avg_energy
    return np.any(energies * 20 > threshold)

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
    extension = ".h5" if modeltype == "cnn" else ".pickle"
    return f"{modeltype}_{pca_str}_{aug_str}_{norm_str}{extension}"

def parse_timestamp(ts_str):
    try:
        return int(float(ts_str))
    except ValueError:
        for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
            try:
                t = datetime.strptime(ts_str, fmt)
                return int((t.hour * 3600 + t.minute * 60 + t.second) * 1000 + t.microsecond / 1000)
            except ValueError:
                continue
        raise ValueError(f"Unrecognized timestamp format: {ts_str}")

def parse_event_log(event_log_path):
    events = []
    with open(event_log_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3: continue
            try:
                start_ms = parse_timestamp(parts[0])
                end_ms = parse_timestamp(parts[1])
                label = parts[2]
                events.append((start_ms, end_ms, label))
            except Exception as e:
                print(f"Erreur parsing: {line} => {e}")
    return events

def get_ground_truth_label(events, t_ms):
    for (start, end, label) in events:
        if start <= t_ms < end:
            return label
    return None

def compute_metrics(predictions, ground_truth_labels, class_names_str):
    label_to_idx = {lbl: i for i, lbl in enumerate(class_names_str)}
    n_classes = len(class_names_str)
    conf_matrix = np.zeros((n_classes, n_classes), dtype=int)
    for pred_lbl, true_lbl in zip(predictions, ground_truth_labels):
        if true_lbl not in label_to_idx or pred_lbl not in label_to_idx:
            continue
        i_pred = label_to_idx[pred_lbl]
        i_true = label_to_idx[true_lbl]
        conf_matrix[i_true, i_pred] += 1
    metrics = {}
    metrics["conf_matrix"] = conf_matrix
    metrics["per_class_accuracy"] = [conf_matrix[i, i] / conf_matrix[i].sum() if conf_matrix[i].sum() else 0 for i in range(n_classes)]
    metrics["per_class_precision"] = [conf_matrix[i, i] / conf_matrix[:, i].sum() if conf_matrix[:, i].sum() else 0 for i in range(n_classes)]
    metrics["per_class_recall"] = [conf_matrix[i, i] / conf_matrix[i].sum() if conf_matrix[i].sum() else 0 for i in range(n_classes)]
    metrics["overall_accuracy"] = conf_matrix.trace() / conf_matrix.sum() if conf_matrix.sum() else 0
    return metrics

# ====================================================
# ===           Démarrage du programme             ===
# ====================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", help="Port série (ex: COM3 ou /dev/ttyUSB0)", required=False)
    args = parser.parse_args()

    if args.port is None:
        print("Aucun port série spécifié. Ports disponibles :")
        for p in list_ports.comports():
            print(p.device)
        sys.exit(0)

    model_filename = build_model_filename(MODELTYPE, PCA, AUGMENTATION, NORMALISATION)
    model_path = os.path.join(MODEL_DIR, model_filename)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle introuvable : {model_path}")

    if MODELTYPE == "cnn":
        model = load_model(model_path)
    else:
        model = pickle.load(open(model_path, "rb"))

    print(f"Modèle chargé : {model_filename}")

    if PCA and MODELTYPE != "cnn":
        pca_filename = model_filename.replace(".pickle", "")
        pca_path = os.path.join(MODEL_DIR, pca_filename + ".pickle")
        pca = pickle.load(open(pca_path, "rb"))
    else:
        pca = None

    input_stream = reader(port=args.port)
    pygame.mixer.init()
    pygame.mixer.music.load(CONTEST_WAV)

    class_names_str = ["chainsaw", "fire", "fireworks", "gunshot"]
    predictions_list = []
    if CONTEST:
        events = parse_event_log(EVENT_LOG_PATH)
        audio_segment = AudioSegment.from_wav(CONTEST_WAV)
        contest_duration_ms = len(audio_segment)

    print("Démarrage dans 2 secondes...")
    time.sleep(2)
    print("GO!")
    pygame.mixer.music.play()
    start_time = time.time()

    with open(LOG_PATH, "a") as log_file:
        log_file.write("# Predicted Classes for Played Sounds\n\n")
        msg_counter = 0
        plt.figure(figsize=(8, 6))

        while True:
            if CONTEST and (time.time() - start_time) * 1000.0 > contest_duration_ms:
                print("\nFin du contest.")
                break

            try:
                melvec = next(input_stream)
            except StopIteration:
                break

            msg_counter += 1
            melvec = melvec.reshape((N_MELVECS, MELVEC_LENGTH)).T
            fv = melvec.reshape(1, -1)

            if not sound_bigger_than_adaptive_threshold(melvec):
                continue

            if NORMALISATION:
                norm_val = np.linalg.norm(fv)
                if norm_val != 0:
                    fv = fv / norm_val

            if pca is not None:
                fv = pca.transform(fv)

            if MODELTYPE == "cnn":
                fv = fv.reshape((1, 20, 20, 1))
                proba = model.predict(fv)[0]
                pred_label_idx = np.argmax(proba)
            else:
                pred_label_idx = model.predict(fv)[0]
                if hasattr(model, "predict_proba"):
                    proba = model.predict_proba(fv)[0]
                else:
                    proba = None

            predicted_class_name = class_names_str[pred_label_idx]
            print(f"Prédiction: {predicted_class_name}")

            log_file.write(f"Sound #{msg_counter}: Predicted class: {predicted_class_name}\n")
            log_file.flush()

            if CONTEST:
                elapsed_ms = (time.time() - start_time) * 1000.0
                predictions_list.append((elapsed_ms, predicted_class_name))

            # Affichage matplotlib
            if proba is not None and hasattr(model, "classes_"):
                class_names = model.classes_
                class_names_str = ["chainsaw", "fire", "fireworks", "gunshot"]
                probabilities = np.round(proba[0] * 100, 2)
                max_len = max(len(name) for name in class_names_str)
                probabilities_str = " ".join([f"{prob:.2f}%".ljust(max_len) for prob in probabilities])
                textlabel = f"{class_names_str}\n{probabilities_str}\n\nPredicted class: {predicted_class_name}"
            else:
                textlabel = f"Predicted class: {predicted_class_name}"

            plot_specgram_textlabel(
                melvec.reshape((N_MELVECS, MELVEC_LENGTH)),
                ax=plt.gca(),
                is_mel=True,
                title=f"MEL Spectrogram #{msg_counter}",
                xlabel="Mel vector",
                textlabel=textlabel,
            )
            plt.draw()
            plt.pause(0.1)
            plt.clf()

    if CONTEST:
        print("\n=== METRICS ===")
        ground_truth_labels = [get_ground_truth_label(events, t) for (t, _) in predictions_list]
        predicted_labels = [lbl for (_, lbl) in predictions_list]
        metrics = compute_metrics(predicted_labels, ground_truth_labels, class_names_str)

        print("Confusion matrix:")
        print(metrics["conf_matrix"])
        for i, cname in enumerate(class_names_str):
            print(f"{cname}: Acc={metrics['per_class_accuracy'][i]:.2f}  Prec={metrics['per_class_precision'][i]:.2f}  Rec={metrics['per_class_recall'][i]:.2f}")
        print(f"Overall Accuracy: {metrics['overall_accuracy']:.3f}")
