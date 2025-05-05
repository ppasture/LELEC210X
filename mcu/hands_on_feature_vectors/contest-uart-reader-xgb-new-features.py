#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Realtime ESC‑50 inference script (serial or contest‑wave mode).

Modifié : 2025‑04‑18
 • gestion générique .pkl/.pickle
 • chargement auto scaler Z‑score et PCA
 • suppression normalisation L2 – on applique le scaler si demandé
"""

import argparse, os, sys, time, pickle, joblib
from datetime import datetime

import numpy as np
import pygame
import matplotlib.pyplot as plt
from pydub import AudioSegment
from pydub.playback import play
import serial
from serial.tools import list_ports
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.models import load_model

from classification.utils.plots import plot_specgram_textlabel

# ───────────────────────────────────────────────────────────
#  CONFIGURATION
# ───────────────────────────────────────────────────────────
MODELTYPE      = "xgb_new_features"   # "rf" | "xgb" | "cnn" | "xgb_new_features"
PCA            = False                 # applique la PCA si disponible
AUGMENTATION   = True
NORMALISATION  = True                 # applique le scaler Z‑score si disponible
CONTEST        = True
RECORDED       = False
VARIANCE_MODE  = "both"

ALPHA               = 0.75
ENERGY_MULTIPLIER   = 1
avg_energy          = 0.0

CONTEST_WAV   = "../../classification/contest_simulator/contest_ESC50_sounds.wav"
EVENT_LOG     = "../../classification/contest_simulator/event_log_ESC50_sounds.txt"
if RECORDED:
    CONTEST_WAV = "../../classification/contest_simulator/contest_recorded_sounds.wav"
    EVENT_LOG   = "../../classification/contest_simulator/event_log_recorded_sounds.txt"

LOG_PATH  = "../../classification/data/played_sounds/predicted_sounds.txt"
MODEL_DIR = f"../../classification/data/models/{MODELTYPE}"

PRINT_PREFIX   = "DF:HEX:"
FREQ_SAMPLING  = 10200
MELVEC_LENGTH  = 20
N_MELVECS      = 20
FINAL_SHAPE    = (21, 20) if MODELTYPE == "xgb_new_features" else (20, 20)
dt             = np.dtype(np.uint16).newbyteorder("<")

CLASS_NAMES = ["chainsaw", "fire", "fireworks", "gunshot"]   # ordre fixe attendu

# ───────────────────────────────────────────────────────────
#  UTILITAIRES
# ───────────────────────────────────────────────────────────

def add_variance_features(vec, mode="both", n_mels=20):
    if mode not in {"band", "column", "both"}:
        raise ValueError("mode must be 'band', 'column' or 'both'")

    mel = vec.reshape(n_mels, 20)
    feats = [vec.flatten()]

    if mode in {"band", "both"}:
        var_band = np.var(mel, axis=1, ddof=0)  # variance temporelle (par bande)
        feats.append(var_band)

    if mode in {"column", "both"}:
        var_col = np.var(mel, axis=0, ddof=0)  # variance spectrale (par trame)
        feats.append(var_col)

    return np.concatenate(feats).astype(np.float32)

def load_pickle(path):
    with open(path, "rb") as f:
        try:
            return pickle.load(f)
        except Exception:
            return joblib.load(f)

def build_stem(modeltype, pca, aug, norm):
    pca_str  = "pca"  if pca  else "nopca"
    aug_str  = "aug"  if aug  else "noaug"
    norm_str = "norm" if norm else "nonorm"
    return f"{modeltype}_{pca_str}_{aug_str}_{norm_str}"

def build_model_path(stem):
    if MODELTYPE == "cnn":
        return os.path.join(MODEL_DIR, stem + ".h5")
    for ext in (".pickle", ".pkl"):
        path = os.path.join(MODEL_DIR, stem + ext)
        if os.path.exists(path):
            return path
    raise FileNotFoundError(f"Aucun fichier modèle trouvé pour le stem {stem}")

def build_aux_path(kind, stem):
    for ext in (".pkl", ".pickle"):
        path = os.path.join(MODEL_DIR, f"{kind}_{stem}{ext}")
        if os.path.exists(path):
            return path
    return None

def zscore_transform(x, scaler):
    return scaler.transform(x)

def sound_bigger_than_adaptive_threshold(buf):
    global avg_energy
    buf = buf.reshape((20, 20)).T
    energies = np.sum(buf ** 2, axis=1)
    total_energy = np.sum(energies)
    avg_energy = ALPHA * avg_energy + (1.0 - ALPHA) * total_energy
    return np.any(energies * 20 > ENERGY_MULTIPLIER * avg_energy)

def parse_buffer(line):
    line = line.strip()
    return bytes.fromhex(line[len(PRINT_PREFIX):]) if line.startswith(PRINT_PREFIX) else None

def reader(port):
    ser = serial.Serial(port=port, baudrate=115200)
    while True:
        line = ser.readline().decode("ascii")
        buf = parse_buffer(line)
        if buf is not None:
            yield np.frombuffer(buf, dtype=dt)

def parse_timestamp(ts):
    try:
        return int(float(ts))
    except ValueError:
        for fmt in ("%H:%M:%S.%f", "%H:%M:%S"):
            try:
                d = datetime.strptime(ts, fmt)
                return int((d.hour*3600 + d.minute*60 + d.second)*1000 + d.microsecond/1000)
            except ValueError:
                pass
    raise ValueError(f"Bad timestamp : {ts}")

def parse_event_log(path):
    evts = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            p = ln.split()
            if len(p) >= 3:
                try:
                    s = parse_timestamp(p[0])
                    e = parse_timestamp(p[1])
                    lbl = p[2]
                    evts.append((s, e, lbl))
                except ValueError as ve:
                    print(f"Erreur parsing ligne : {ln}\n{ve}")
    return evts

def gt_label(events, t_ms):
    for s, e, lbl in events:
        if s <= t_ms < e:
            return lbl
    return None

def compute_metrics(preds, gts, classes):
    idx = {c:i for i,c in enumerate(classes)}
    n   = len(classes)
    cm  = np.zeros((n, n), int)
    for p, t in zip(preds, gts):
        if t not in idx or p not in idx: continue
        cm[idx[t], idx[p]] += 1
    acc_class = [cm[i,i]/cm[i].sum() if cm[i].sum() else 0 for i in range(n)]
    prec      = [cm[i,i]/cm[:,i].sum() if cm[:,i].sum() else 0 for i in range(n)]
    rec       = [cm[i,i]/cm[i].sum()   if cm[i].sum()   else 0 for i in range(n)]
    return {"cm": cm, "acc_class": acc_class, "prec": prec, "rec": rec, "overall": cm.trace()/cm.sum() if cm.sum() else 0}

# ───────────────────────────────────────────────────────────
#  MAIN
# ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    prsr = argparse.ArgumentParser()
    prsr.add_argument("-p", "--port", required=False, help="Port série (COM3 / /dev/ttyUSB0)")
    args = prsr.parse_args()

    if args.port is None:
        print("Ports disponibles :")
        for p in list_ports.comports(): print(" •", p.device)
        sys.exit("Spécifie un port avec -p")

    stem       = build_stem(MODELTYPE, PCA, AUGMENTATION, NORMALISATION)
    model_path = build_model_path(stem)
    print("Chargement modèle :", os.path.basename(model_path))
    model = load_pickle(model_path)

    scaler = None
    if NORMALISATION:
        scaler_path = build_aux_path("scaler", stem)
        if scaler_path:
            scaler = load_pickle(scaler_path)
            print("Scaler Z‑score chargé")
        else:
            print("⚠️  NORMALISATION=True mais aucun scaler trouvé ; normalisation ignorée.")
            NORMALISATION = False

    pca = None
    if PCA:
        pca_path = build_aux_path("pca", stem)
        if pca_path:
            pca = load_pickle(pca_path)
            print("PCA chargée")
        else:
            print("⚠️PCA=True mais aucun fichier PCA trouvé ; PCA ignorée.")
            PCA = False

    if CONTEST:
        audio_wav = AudioSegment.from_wav(CONTEST_WAV)
        events    = parse_event_log(EVENT_LOG)
        contest_ms = len(audio_wav)
        pygame.mixer.init()
        pygame.mixer.music.load(CONTEST_WAV)

    print("\nDémarrage dans 2 s…")
    time.sleep(2)
    start_time = time.time()
    print("GO !")
    if CONTEST: pygame.mixer.music.play()

    ser_stream = reader(args.port)
    msg_id     = 0
    preds, gts = [], []
    predictions_list = []

    with open(LOG_PATH, "a") as log:
        log.write(f"# Session {datetime.now()}\n")
        plt.figure(figsize=(8,6))

        for raw in ser_stream:
            if CONTEST and (time.time() - start_time) * 1000 > contest_ms:
                break

            msg_id += 1
            mel = raw.reshape((N_MELVECS, MELVEC_LENGTH)).T      # (20,20)

            if not sound_bigger_than_adaptive_threshold(mel[:20]):
                continue

            fv = add_variance_features(mel, VARIANCE_MODE)
            fv = fv.reshape(1, -1)

            if NORMALISATION:
                fv = zscore_transform(fv, scaler)

            if PCA:
                fv = pca.transform(fv)

            pred_label_idx = model.predict(fv)[0]
            if hasattr(model, "predict_proba"):
                proba = model.predict_proba(fv)[0]
            else:
                proba = None

            class_names_str = CLASS_NAMES
            predicted_class_name = class_names_str[pred_label_idx]
            print(f"Prédiction: {predicted_class_name}")

            if CONTEST:
                elapsed_ms = (time.time() - start_time) * 1000.0
                predictions_list.append((elapsed_ms, predicted_class_name))

            probabilities = np.round(proba * 100, 2)
            textlabel = "\n".join([f"{name}: {prob:.2f}%" for name, prob in zip(class_names_str,probabilities)]) + f"\n\nPredicted class: {predicted_class_name}"

            plot_specgram_textlabel(
                mel,
                ax=plt.gca(),
                is_mel=True,
                title=f"MEL Spectrogram #{msg_id}",
                xlabel="Mel vector",
                textlabel=textlabel,
            )
            plt.draw()
            plt.pause(0.1)
            plt.clf()

    if CONTEST:
        print("\n=== METRICS ===")
        ground_truth_labels = [gt_label(events, t) for (t, _) in predictions_list]
        predicted_labels = [lbl for (_, lbl) in predictions_list]
        metrics = compute_metrics(predicted_labels, ground_truth_labels, class_names_str)

        print("Confusion matrix:")
        print(metrics["cm"])
        for i, cname in enumerate(class_names_str):
            print(f"{cname}: Acc={metrics['acc_class'][i]:.2f}  Prec={metrics['prec'][i]:.2f}  Rec={metrics['rec'][i]:.2f}")
        print(f"Overall Accuracy: {metrics['overall']:.3f}")