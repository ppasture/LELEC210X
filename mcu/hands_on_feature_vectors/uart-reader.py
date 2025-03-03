import sys
import os
from pathlib import Path
classification_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../classification/src/classification"))
sys.path.append(classification_path)
from utils.plots import plot_specgram_textlabel


import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
from serial.tools import list_ports
import pickle

PRINT_PREFIX = "DF:HEX:"
FREQ_SAMPLING = 10200
MELVEC_LENGTH = 20
N_MELVECS = 20
NUM_NOISE_SAMPLES = 10  # Number of samples used to compute noise

dt = np.dtype(np.uint16).newbyteorder("<")

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
            print(line)
        line = line.strip()
        buffer = parse_buffer(line)
        if buffer is not None:
            buffer_array = np.frombuffer(buffer, dtype=dt)
            yield buffer_array

if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-p", "--port", help="Port for serial communication")
    argParser.add_argument(
        "--log",
        type=str,
        default="../../classification/data/played_sounds/predicted_sounds.txt",
        help="Path to the log file (default: ../../classification/data/played_sounds/predicted_sounds.txt)."
    )
    args = argParser.parse_args()
    print("uart-reader launched...\n")

    if args.port is None:
        print(
            "No port specified, here is a list of serial communication port available"
        )
        print("================")
        port = list(list_ports.comports())
        for p in port:
            print(p.device)
        print("================")
        print("Launch this script with [-p PORT_REF] to access the communication port")
    else:
        input_stream = reader(port=args.port)
        msg_counter = 0
        noise_vectors = []
        noise_mean = None
        
        # Load the model from pickle file
        pca_path = Path("classification/data/models/pca.pickle")
        rf_model_path = Path("classification/data/models/model.pickle")
        with pca_path.open("rb") as pca_file:
            pca = pickle.load(pca_file)

        with rf_model_path.open("rb") as rf_file:
            model_rf = pickle.load(rf_file)


        plt.figure(figsize=(8, 6))

        # Open the log file in append mode
        with open(args.log, "a") as log_file:
            log_file.write("# Predicted Classes for Played Sounds\n\n")
            
            for melvec in input_stream:
                msg_counter += 1
                melvec = melvec[12:].reshape(1, -1)  # Remove the header

                if msg_counter <= NUM_NOISE_SAMPLES:
                    noise_vectors.append(melvec)
                    print(f"Collecting noise sample {msg_counter}/{NUM_NOISE_SAMPLES}")
                    if msg_counter == NUM_NOISE_SAMPLES:
                        noise_mean = np.mean(np.vstack(noise_vectors), axis=0)
                        print("Computed noise mean:\n", noise_mean)
                else:
                    melvec -= noise_mean  # Remove noise
                    melvecs_pca = pca.transform(melvec)
                    
                    proba_rf = model_rf.predict_proba(melvecs_pca)[0]
                    prediction_rf = model_rf.predict(melvecs_pca)
                    print(f"Predicted class: {prediction_rf}\n")
                    print(f"Predicted probabilities: {proba_rf}\n")

                    sorted_indices = np.argsort(proba_rf)[::-1]
                    best_class = sorted_indices[0]
                    second_best_class = sorted_indices[1]
                    
                    if proba_rf[best_class] >= proba_rf[second_best_class] + 0.05:
                        prediction_given = best_class

                        log_entry = f"Sound #{msg_counter}: Predicted class: {prediction_given}\n"
                        log_file.write(log_entry)
                        log_file.flush()
                        print(f"Logged: {log_entry.strip()}")

                        class_names = model_rf.classes_
                        probabilities = np.round(proba_rf * 100, 2)
                        max_len = max(len(name) for name in class_names)
                        class_names_str = " ".join([f"{name:<{max_len}}" for name in class_names])
                        probabilities_str = " ".join([f"{prob:.2f}%".ljust(max_len) for prob in probabilities])
                        textlabel = f"{class_names_str}\n{probabilities_str}\n\nPredicted class: {prediction_given}\n"

                        plot_specgram_textlabel(
                            melvec[0].reshape((N_MELVECS, MELVEC_LENGTH)).T,
                            ax=plt.gca(),
                            is_mel=True,
                            title=f"MEL Spectrogram #{msg_counter}",
                            xlabel="Mel vector",
                            textlabel=textlabel,
                        )
                        plt.draw()
                        plt.savefig(f"../../classification/data/played_sounds/melspectrograms_played_sounds/melspec_{msg_counter}.pdf")
                        plt.pause(0.1)
                        plt.clf()
                    else:
                        print(f"Prediction {best_class} rejected: {proba_rf[best_class]:.2f} vs {proba_rf[second_best_class]:.2f}")