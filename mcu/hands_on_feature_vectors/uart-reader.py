import sys
import os
classification_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../classification/src/classification"))
sys.path.append(classification_path)
from utils.plots import plot_specgram_textlabel


import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
from serial.tools import list_ports
import pickle

# Define model 
class PCA_RF_Model:
    def __init__(self, pca, model):
        self.pca = pca
        self.model = model

    def fit(self, X, y):
        X_pca = self.pca.fit_transform(X)
        self.model.fit(X_pca, y)

    def predict(self, X):
        X_pca = self.pca.transform(X)
        return self.model.predict(X_pca)

    def predict_proba(self, X):
        X_pca = self.pca.transform(X)
        return self.model.predict_proba(X_pca)

PRINT_PREFIX = "DF:HEX:"
FREQ_SAMPLING = 10200
MELVEC_LENGTH = 20
N_MELVECS = 20

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

        # Load the model from pickle file
        model_rf = pickle.load(open("../../classification/data/models/final_model_with_pca.pickle", "rb"))
        print(f"Model {type(model_rf).__name__} has been loaded from pickle file.\n")
        print(f"PCA expected components: {model_rf.pca.n_components_}")

        plt.figure(figsize=(8, 6))

        # Open the log file in append mode
        with open(args.log, "a") as log_file:
            log_file.write("# Predicted Classes for Played Sounds\n\n")
            
            for melvec in input_stream:
                msg_counter += 1

                print(f"MEL Spectrogram #{msg_counter}")
                fv = melvec[12:].reshape(1, -1)  # Remove the header
                fv = fv / np.linalg.norm(fv)

                # Predict the class of the mel vector
                pred = model_rf.predict(fv)
                proba = model_rf.predict_proba(fv)
                print(f"Predicted class: {pred[0]}\n")
                print(f"Predicted probabilities: {proba}\n")

                # Log the predicted class
                log_entry = f"Sound #{msg_counter}: Predicted class: {pred[0]}\n"
                log_file.write(log_entry)
                log_file.flush()  # Ensure immediate write
                print(f"Logged: {log_entry.strip()}")

                class_names = model_rf.model.classes_
                probabilities = np.round(proba[0] * 100, 2)
                max_len = max(len(name) for name in class_names)
                class_names_str = " ".join([f"{name:<{max_len}}" for name in class_names])
                probabilities_str = " ".join([f"{prob:.2f}%".ljust(max_len) for prob in probabilities])
                textlabel = f"{class_names_str}\n{probabilities_str}"
                textlabel = textlabel + f"\n\nPredicted class: {pred[0]}\n"

                # Plot and save the spectrogram
                plot_specgram_textlabel(
                    melvec[12:].reshape((N_MELVECS, MELVEC_LENGTH)).T,
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
