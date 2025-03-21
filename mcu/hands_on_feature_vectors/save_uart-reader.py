import sys
import os
from pathlib import Path
import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
from serial.tools import list_ports
import pickle
classification_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../classification/src/classification"))
sys.path.append(classification_path)
from utils.plots import plot_specgram_textlabel

# ------------- CLASSES -------------

class UartReader:
    """
    Reads lines from a specified UART (serial) port and parses them for data frames.
    Yields NumPy arrays of data once each line is processed.
    """
    PRINT_PREFIX = "DF:HEX:"

    def __init__(self, port=None, baudrate=115200, n_melvecs=20, melvec_length=20):
        self.port = port
        self.baudrate = baudrate
        self.n_melvecs = n_melvecs
        self.melvec_length = melvec_length

        # Open serial if a port is given
        if self.port is not None:
            self.ser = serial.Serial(port=self.port, baudrate=self.baudrate)
        else:
            self.ser = None

        # Prepare the dtype for reading
        self.dt = np.dtype(np.uint16).newbyteorder("<")

    def list_available_ports(self):
        """Utility to list all available serial ports."""
        return list(list_ports.comports())

    @staticmethod
    def _parse_buffer(line):
        """If a line starts with PRINT_PREFIX, convert its hex payload to bytes."""
        line = line.strip()
        if line.startswith(UartReader.PRINT_PREFIX):
            return bytes.fromhex(line[len(UartReader.PRINT_PREFIX):])
        else:
            print(line)  # Print any non-data lines
            return None

    def read_lines(self):
        """
        Generator that yields lines from the serial port until newline.
        If no port was specified, it does nothing (or could read from a fallback).
        """
        if self.ser is None:
            # No port specified, just yield nothing
            return

        while True:
            line = ""
            # Read until we find a newline
            while not line.endswith("\n"):
                # We guess a buffer size to avoid partial reads (not critical if small)
                line += self.ser.read_until(
                    b"\n",
                    size=2 * self.n_melvecs * self.melvec_length
                ).decode("ascii")
            yield line.strip()

    def read_data_frames(self):
        """
        Generator that yields NumPy arrays after parsing each line for the data frame.
        """
        for line in self.read_lines():
            buffer_raw = self._parse_buffer(line)
            if buffer_raw is not None:
                buffer_array = np.frombuffer(buffer_raw, dtype=self.dt)
                yield buffer_array


class NoiseManager:
    """
    Manages noise collection and subtraction (if AVERAGE_NOISE == True).
    Collects a specified number of noise samples, computes the average noise,
    and subtracts it from subsequent feature vectors.
    """
    def __init__(self, average_noise=True, num_noise_samples=10):
        self.average_noise = average_noise
        self.num_noise_samples = num_noise_samples
        self.noise_vectors = []
        self.noise_mean = None
        self.sample_count = 0

    def process_noise(self, melvec):
        """
        1. If we are still in the noise-collection phase, collect noise samples.
        2. Once enough samples are collected, compute the noise mean.
        3. Return True if we are still collecting noise (i.e. we should skip further processing).
        """
        if not self.average_noise:
            return False  # No noise management needed

        if self.sample_count < self.num_noise_samples:
            self.sample_count += 1
            self.noise_vectors.append(melvec.copy())
            print(f"Collecting noise sample {self.sample_count}/{self.num_noise_samples}")
            if self.sample_count == self.num_noise_samples:
                # Compute final noise mean
                self.noise_mean = np.mean(np.vstack(self.noise_vectors), axis=0)
                print("Computed noise mean:\n", self.noise_mean)
            return True  # We are still collecting noise samples
        return False

    def subtract_noise(self, melvec):
        """
        Subtract the computed noise mean from the current melvec.
        Only does this if noise_mean is available.
        """
        if self.noise_mean is not None:
            melvec -= self.noise_mean
        return melvec


class SoundPredictor:
    """
    Selects the correct RandomForest model based on the flags:
    - PCA
    - DATA_AUGMENTATION
    Then performs predictions and returns probabilities and predicted classes.
    """
    def __init__(self, pca, pca_model, no_pca_model, no_transformation_model,
                 pca_enabled=False, data_augmentation=False, relative_threshold=0):
        self.pca = pca
        self.pca_model = pca_model
        self.no_pca_model = no_pca_model
        self.no_transformation_model = no_transformation_model
        self.pca_enabled = pca_enabled
        self.data_augmentation = data_augmentation
        self.relative_threshold = relative_threshold

    def predict(self, melvec):
        """
        1. Decide which model to use (with/without PCA, data augmentation).
        2. Apply PCA if needed.
        3. Predict with selected model.
        4. Return (best_class or None, predicted_probabilities).
        """
        # Default model: no_pca_model
        model = self.no_pca_model

        # If PCA is enabled, transform and use PCA-based model
        if self.pca_enabled:
            melvec = self.pca.transform(melvec)
            model = self.pca_model

        # If data augmentation is flagged, use the "no_transformation_model"
        if self.data_augmentation:
            model = self.no_transformation_model

        proba = model.predict_proba(melvec)[0]
        predicted = model.predict(melvec)[0]
        print(f"Predicted class: {predicted}\n")
        print(f"Predicted probabilities: {proba}\n")

        # Determine acceptance
        sorted_indices = np.argsort(proba)[::-1]
        best_class = sorted_indices[0]
        second_best_class = sorted_indices[1]

        if proba[best_class] >= proba[second_best_class] + self.relative_threshold:
            return best_class, proba, model
        else:
            print(f"Prediction {best_class} rejected: "
                  f"{proba[best_class]:.2f} vs {proba[second_best_class]:.2f}")
            return None, proba, model


# ------------- MAIN SCRIPT -------------

def main():
    AVERAGE_NOISE = False
    RELATIVE_THRESHOLD = 0.05
    PCA_FLAG = False
    DATA_AUGMENTATION = False
    SAVE_MELSPECS = False

    N_MELVECS = 20
    MELVEC_LENGTH = 20

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

    # 1. If no port is provided, show available ports and exit
    uart = UartReader(port=args.port, baudrate=115200,
                      n_melvecs=N_MELVECS, melvec_length=MELVEC_LENGTH)
    if args.port is None:
        print("No port specified. Available serial ports:")
        print("================")
        for p in uart.list_available_ports():
            print(p.device)
        print("================")
        print("Launch this script with [-p PORT_REF] to access the communication port")
        sys.exit(0)

    # 2. Initialize NoiseManager
    noise_manager = NoiseManager(average_noise=AVERAGE_NOISE, num_noise_samples=10)

    # 3. Load models
    pca_path = Path("../../classification/data/models/pca.pickle")
    pca_model_path = Path("../../classification/data/models/mod_pca.pickle")
    no_pca_model_path = Path("../../classification/data/models/mod_no_pca.pickle")
    no_transformation_model_path = Path("../../classification/data/models/mod_no_aug.pickle")

    with pca_path.open("rb") as f:
        pca = pickle.load(f)
    with pca_model_path.open("rb") as f:
        pca_model = pickle.load(f)
    with no_pca_model_path.open("rb") as f:
        no_pca_model = pickle.load(f)
    with no_transformation_model_path.open("rb") as f:
        no_transformation_model = pickle.load(f)

    # 4. Create a SoundPredictor instance
    sound_predictor = SoundPredictor(
        pca=pca,
        pca_model=pca_model,
        no_pca_model=no_pca_model,
        no_transformation_model=no_transformation_model,
        pca_enabled=PCA_FLAG,
        data_augmentation=DATA_AUGMENTATION,
        relative_threshold=RELATIVE_THRESHOLD
    )

    # 5. Start reading from UART and process each data frame
    plt.figure(figsize=(8, 6))
    msg_counter = 0

    # 6. Open the log file in append mode
    with open(args.log, "a") as log_file:
        log_file.write("# Predicted Classes for Played Sounds\n\n")

        for buffer_array in uart.read_data_frames():
            msg_counter += 1

            # Convert raw buffer to float32 and remove the header (first 12 values?)
            melvec = np.array(buffer_array[12:].reshape(1, -1), dtype=np.float32)

            # --- Noise Collection Phase ---
            if noise_manager.process_noise(melvec):
                # If we're still collecting noise, skip the rest of processing
                continue

            # --- Noise Subtraction ---
            melvec = noise_manager.subtract_noise(melvec)

            # --- Prediction ---
            best_class, proba_rf, model_used = sound_predictor.predict(melvec)

            if best_class is not None:
                if best_class == 0:
                    best_class_name = "Chainsaw"
                elif best_class == 1:
                    best_class_name = "fire"
                elif best_class == 2:
                    best_class_name = "fireworks"
                elif best_class == 3:
                    best_class_name = "gunshot"
                # Logging
                log_entry = f"Sound #{msg_counter}: Predicted class: {best_class_name}\n"
                log_file.write(log_entry)
                log_file.flush()
                print(f"Logged: {log_entry.strip()}")

                # Visualization
                class_names = model_used.classes_
                probabilities = np.round(proba_rf * 100, 2)
                max_len = max(len(name) for name in class_names)
                class_names_str = " ".join([f"{name:<{max_len}}" for name in class_names])
                probabilities_str = " ".join([f"{prob:.2f}%".ljust(max_len) for prob in probabilities])
                textlabel = f"{class_names_str}\n{probabilities_str}\n\nPredicted class: {best_class_name}\n"

                plot_specgram_textlabel(
                    melvec[0].reshape((N_MELVECS, MELVEC_LENGTH)).T,
                    ax=plt.gca(),
                    is_mel=True,
                    title=f"MEL Spectrogram #{msg_counter}",
                    xlabel="Mel vector",
                    textlabel=textlabel,
                )
                plt.draw()
                if SAVE_MELSPECS:
                    plt.savefig(f"../../classification/data/played_sounds/melspectrograms/melspec_{msg_counter}.pdf")
                plt.pause(0.1)
                plt.clf()


if __name__ == "__main__":
    main()
