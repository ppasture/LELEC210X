import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
from serial.tools import list_ports
import pickle
import os
import time
import sys
from pydub import AudioSegment  # for reading contest_sound.wav length
from datetime import datetime

from classification.utils.plots import plot_specgram_textlabel

# ====================================================
# ===          CONFIGURATION MANUELLE              ===
# ====================================================
MODELTYPE = "xgb"      # "rf" ou "xgb"
PCA = True             # True ou False
AUGMENTATION = True    # True ou False
NORMALISATION = False  # True ou False

CONTEST = True         # True => listens only for the duration of contest_sound.wav
                       # and compares predictions to ground truth

# If you run in contest mode, we'll parse these:
CONTEST_WAV = "../../classification/contest_simulator/contest_sound.wav"
EVENT_LOG_PATH = "../../classification/contest_simulator/sound_event_log.txt"

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
    """
    Generator reading from serial. Yields each complete buffer as a np.array of shape (N_MELVECS*MELVEC_LENGTH,).
    """
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


# ====== Ground-Truth Parsing (for Contest Mode) ======
def parse_timestamp(ts_str):
    """
    Converts timestamp to milliseconds.
    Accepts:
      - milliseconds (as int string): "5000"
      - or time format like "0:00:05" => 5000 ms
    """
    try:
        return int(float(ts_str))  # Already in ms
    except ValueError:
        # Assume time format
        t = datetime.strptime(ts_str, "%H:%M:%S")
        return (t.hour * 3600 + t.minute * 60 + t.second) * 1000

def parse_event_log(event_log_path):
    """
    Parses events like:
    0:00:00 0:00:05 chainsaw
    or
    0 5000 chainsaw
    """
    events = []
    with open(event_log_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            try:
                start_ms = parse_timestamp(parts[0])
                end_ms = parse_timestamp(parts[1])
                label = parts[2]
                events.append((start_ms, end_ms, label))
            except Exception as e:
                print(f"❌ Erreur de parsing sur la ligne: {line}")
                print(e)
    return events

def get_ground_truth_label(events, t_ms):
    """
    Given a list of (start_ms, end_ms, label),
    returns the label that covers t_ms, or None if none match.
    """
    for (start, end, label) in events:
        if start <= t_ms < end:
            return label
    return None


# ============= METRICS: Overall + Per-Class =================
from collections import defaultdict

def compute_metrics(predictions, ground_truth_labels, class_names_str):
    """
    predictions: [str, str, ...], each is predicted label
    ground_truth_labels: [str, str, ...], same length
    class_names_str: ["chainsaw", "fire", "fireworks", "gunshot"]
    Returns per-class accuracy, precision, recall + overall accuracy.
    """

    # Convert each label to an index for confusion matrix
    label_to_idx = {lbl: i for i, lbl in enumerate(class_names_str)}
    n_classes = len(class_names_str)
    conf_matrix = np.zeros((n_classes, n_classes), dtype=int)

    for pred_lbl, true_lbl in zip(predictions, ground_truth_labels):
        if true_lbl is None:
            # Means outside any event => skip or treat as background
            continue
        if pred_lbl not in label_to_idx:
            continue
        if true_lbl not in label_to_idx:
            continue

        i_pred = label_to_idx[pred_lbl]
        i_true = label_to_idx[true_lbl]
        conf_matrix[i_true, i_pred] += 1

    # Now compute metrics
    # Per-class accuracy is conf_matrix[i,i] / row_sum
    # Precision is conf_matrix[i,i] / col_sum
    # Recall is conf_matrix[i,i] / row_sum
    # Overall accuracy = sum(diag) / sum(all)
    per_class_accuracy = []
    per_class_precision = []
    per_class_recall = []

    for i in range(n_classes):
        row_sum = conf_matrix[i, :].sum()
        col_sum = conf_matrix[:, i].sum()
        tp = conf_matrix[i, i]
        accuracy_i = tp / row_sum if row_sum != 0 else 0
        recall_i = tp / row_sum if row_sum != 0 else 0
        precision_i = tp / col_sum if col_sum != 0 else 0

        per_class_accuracy.append(accuracy_i)
        per_class_recall.append(recall_i)
        per_class_precision.append(precision_i)

    overall_acc = conf_matrix.trace() / conf_matrix.sum() if conf_matrix.sum() else 0

    return {
        "conf_matrix": conf_matrix,
        "per_class_accuracy": per_class_accuracy,
        "per_class_precision": per_class_precision,
        "per_class_recall": per_class_recall,
        "overall_accuracy": overall_acc
    }


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
        sys.exit(0)

    # === 1) Chargement du modèle ===
    model_filename = build_model_filename(MODELTYPE, PCA, AUGMENTATION, NORMALISATION)
    model_path = os.path.join(MODEL_DIR, model_filename)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Modèle introuvable : {model_path}")

    model = pickle.load(open(model_path, "rb"))
    print(f"Modèle chargé : {model_filename} ({type(model).__name__})")

    # === 2) Chargement du PCA si demandé ===
    if PCA:
        # Remove "rf_" or "xgb_" from the model filename
        pca_filename = model_filename.split("_", 1)[1]
        pca_path = os.path.join(MODEL_DIR, pca_filename)
        if not os.path.exists(pca_path):
            raise FileNotFoundError(f"PCA introuvable : {pca_path}")
        pca = pickle.load(open(pca_path, "rb"))
        print(f"PCA chargé : {pca_filename}")
    else:
        pca = None

    # === 3) Préparation variables
    input_stream = reader(port=args.port)
    msg_counter = 0
    plt.figure(figsize=(8, 6))

    # If needed, define custom strings for classes:
    class_names_str = ["chainsaw", "fire", "fireworks", "gunshot"]

    # We'll track predictions/timestamps for the "contest" mode
    predictions_list = []  # list of (time_ms, predicted_label)

    # We'll parse ground-truth if CONTEST is True
    if CONTEST:
        # 3a) read event log
        events = parse_event_log(EVENT_LOG_PATH)
        # 3b) read length of 'contest_sound.wav' in ms
        audio_segment = AudioSegment.from_wav(CONTEST_WAV)
        contest_duration_ms = len(audio_segment)
        print(f"Durée du contest_sound.wav : {contest_duration_ms} ms")

        start_time = time.time()

    with open(LOG_PATH, "a") as log_file:
        log_file.write("# Predicted Classes for Played Sounds\n\n")

        while True:
            # 4) If contest mode => stop after contest_duration
            if CONTEST:
                elapsed_ms = (time.time() - start_time) * 1000.0
                if elapsed_ms > contest_duration_ms:
                    print("\nFin du contest (temps dépassé).")
                    break

            try:
                melvec = next(input_stream)  # read one mel vector from serial
            except StopIteration:
                print("Fin du flux serial ?")
                break

            msg_counter += 1
            print(f"\nMEL Spectrogram #{msg_counter}")

            fv = melvec.reshape(1, -1)
            # Filtre si l'énergie est trop faible
            if np.linalg.norm(fv) < 600:
                print("Valeur trop faible, on ignore ce melvec")
                continue

            # Normalisation locale
            if NORMALISATION:
                norm_val = np.linalg.norm(fv)
                if norm_val != 0:
                    fv = fv / norm_val

            # PCA transformation
            if pca is not None:
                fv = pca.transform(fv)

            # Prediction
            pred = model.predict(fv)
            pred_label_idx = pred[0]
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(fv)[0]
            else:
                proba = None

            # Print
            print(f"Predicted class index: {pred_label_idx}")
            predicted_class_name = class_names_str[pred_label_idx]
            print(f"Class name: {predicted_class_name}")
            if proba is not None:
                print(f"Probabilities: {proba}")

            # Logging
            log_entry = f"Sound #{msg_counter}: Predicted class: {predicted_class_name}\n"
            log_file.write(log_entry)
            log_file.flush()

            # If in contest mode, store timestamp + predicted label
            if CONTEST:
                elapsed_ms = (time.time() - start_time) * 1000.0
                predictions_list.append((elapsed_ms, predicted_class_name))

            # Prepare textlabel for plot
            if proba is not None:
                probabilities_percent = np.round(proba * 100, 2)
                max_len = max(len(name) for name in class_names_str)
                prob_str = " ".join([f"{p:.2f}%".ljust(max_len) for p in probabilities_percent])
                textlabel = f"{class_names_str}\n{prob_str}\n\nPredicted: {predicted_class_name}"
            else:
                textlabel = f"Predicted class: {predicted_class_name}"

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
            plt.pause(0.1)
            plt.clf()

    # ==================================================
    # ===       If CONTEST => compute final metrics   ===
    # ==================================================
    if CONTEST:
        print("\n=== Calcul des metrics du contest ===")

        # Build ground-truth labels for each predicted timestamp
        #  We do a simple approach: each melvec's timestamp => find which event covers it
        ground_truth_labels = []
        for (t_ms, pred_lbl) in predictions_list:
            gt_label = get_ground_truth_label(events, t_ms)
            ground_truth_labels.append(gt_label)

        predicted_labels = [p[1] for p in predictions_list]

        # Per-class accuracy, precision, recall, overall accuracy
        metrics = compute_metrics(predicted_labels, ground_truth_labels, class_names_str)

        # Display results
        conf_matrix = metrics["conf_matrix"]
        print("Confusion matrix (rows=True Label, cols=Pred Label):")
        print(conf_matrix, "\n")

        print("Per-class metrics (order: chainsaw, fire, fireworks, gunshot):")
        for i, cname in enumerate(class_names_str):
            print(f"\nClass: {cname}")
            print(f"  Accuracy:  {metrics['per_class_accuracy'][i]:.3f}")
            print(f"  Precision: {metrics['per_class_precision'][i]:.3f}")
            print(f"  Recall:    {metrics['per_class_recall'][i]:.3f}")

        print(f"\nOverall Accuracy: {metrics['overall_accuracy']:.3f}")

        print("\nFin du programme.")
        sys.exit(0)
