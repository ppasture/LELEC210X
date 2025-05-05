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
from tensorflow.keras.models import load_model
from sklearn.preprocessing import StandardScaler

from classification.utils.plots import plot_specgram_textlabel

# ====================================================
# ===          CONFIGURATION MANUELLE              ===
# ====================================================
MODELTYPE = "cnn"
AUGMENTATION = True
NORMALISATION = True

CONTEST = True
RECORDED = True

ALPHA = 0.75
ENERGY_MULTIPLIER = 0.8
avg_energy = 0.0

COOLDOWN_SEC = 5
last_pred_time = -np.inf

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
FINAL_SHAPE = (20, 20)
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
        buffer = parse_buffer(line.strip())
        if buffer is not None:
            yield np.frombuffer(buffer, dtype=dt)

def build_model_filename(aug, norm):
    aug_str = "aug" if aug else "noaug"
    norm_str = "norm" if norm else "nonorm"
    return f"cnn_{aug_str}_{norm_str}.h5"

def parse_timestamp(ts_str):
    for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
        try:
            t = datetime.strptime(ts_str, fmt)
            return int((t.hour * 3600 + t.minute * 60 + t.second) * 1000 + t.microsecond / 1000)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized timestamp format: {ts_str}")

def parse_event_log(path):
    events = []
    with open(path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) < 3:
                continue
            try:
                start = parse_timestamp(parts[0])
                end = parse_timestamp(parts[1])
                label = parts[2]
                events.append((start, end, label))
            except Exception as e:
                print(f"Erreur parsing: {line} => {e}")
    return events

def get_ground_truth_label(events, t_ms):
    for (start, end, label) in events:
        if start <= t_ms < end:
            return label
    return None

def compute_metrics(preds, truths, class_names):
    label_to_idx = {name: i for i, name in enumerate(class_names)}
    n = len(class_names)
    cm = np.zeros((n, n), dtype=int)
    for p, t in zip(preds, truths):
        if p in label_to_idx and t in label_to_idx:
            cm[label_to_idx[t], label_to_idx[p]] += 1
    acc = np.diag(cm).sum() / cm.sum()
    return cm, acc

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

    model_filename = build_model_filename(AUGMENTATION, NORMALISATION)
    model_path = os.path.join(MODEL_DIR, model_filename)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle introuvable : {model_path}")
    model = load_model(model_path)
    print(f"Modèle CNN chargé : {model_filename}")

    scaler = None
    if NORMALISATION:
        scaler_path = os.path.join(MODEL_DIR, "scaler_aug.pkl" if AUGMENTATION else "scaler.pkl")
        if not os.path.exists(scaler_path):
            raise FileNotFoundError(f"Scaler introuvable : {scaler_path}")
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)

    input_stream = reader(port=args.port)
    pygame.mixer.init()
    pygame.mixer.music.load(CONTEST_WAV)

    class_names_str = ["chainsaw", "fire", "fireworks", "gunshot"]
    predictions_list = []

    if CONTEST:
        events = parse_event_log(EVENT_LOG_PATH)
        contest_duration_ms = len(AudioSegment.from_wav(CONTEST_WAV))

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
                melvec_raw = next(input_stream)
            except StopIteration:
                break

            melvec = melvec_raw.reshape((20, 20)).T
            fv = melvec.reshape(1, -1)

            sound_detected = sound_bigger_than_adaptive_threshold(melvec)
            if not sound_detected:
                continue

            now = time.time() - start_time
            if now - last_pred_time < COOLDOWN_SEC:
                continue  # skip prediction, but threshold was updated
            last_pred_time = now

            if NORMALISATION and scaler is not None:
                fv = scaler.transform(fv)

            fv = fv.reshape((1, 20, 20, 1))
            proba = model.predict(fv, verbose=0)[0]
            pred_idx = np.argmax(proba)
            pred_label = class_names_str[pred_idx]

            msg_counter += 1
            t_ms = int(now * 1000)
            print(f"Prédiction #{msg_counter:03d} ({t_ms} ms) : {pred_label}")
            log_file.write(f"{t_ms} ms -> {pred_label}\n")
            log_file.flush()

            if CONTEST:
                predictions_list.append((t_ms, pred_label))

            probabilities = np.round(proba * 100, 2)
            textlabel = "\n".join([f"{name}: {prob:.2f}%" for name, prob in zip(class_names_str, probabilities)]) + f"\n\nPredicted: {pred_label}"
            plot_specgram_textlabel(
                melvec,
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
        gt_labels = [get_ground_truth_label(events, t) for (t, _) in predictions_list]
        pred_labels = [lbl for (_, lbl) in predictions_list]
        cm, acc = compute_metrics(pred_labels, gt_labels, class_names_str)
        print("Confusion matrix:\n", cm)
        print(f"Overall Accuracy: {acc:.3f}\n")

        print("Vérification qu’il n’y a qu’UNE prédiction par événement :")
        for (start, end, lbl) in events:
            preds_in_event = [p for (t, p) in predictions_list if start <= t < end]
            n_preds = len(preds_in_event)
            status = "✅ OK" if n_preds == 1 else f"⚠ {n_preds} prédictions"
            print(f"{lbl:<10s}  [{start:>6d}-{end:>6d} ms]  ->  {status}")
