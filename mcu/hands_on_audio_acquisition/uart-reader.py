import argparse
import matplotlib.pyplot as plt
import numpy as np
import serial
import soundfile as sf
from serial.tools import list_ports

FREQ_SAMPLING = 10200
VAL_MAX_ADC = 4096
VDD = 3.3
LABELS = ["garbage"]
SAMPLES_PER_LABEL = 40
BUFFER_SIZE = 50000  # 25000 échantillons * 2 octets

def reader(port=None):
    ser = serial.Serial(port=port, baudrate=115200)
    while True:
        buffer = ser.read(BUFFER_SIZE)
        if len(buffer) != BUFFER_SIZE:
            print("Erreur: paquet incomplet")
            continue
        dt = np.dtype(np.uint16)
        dt = dt.newbyteorder("<")  # Little endian
        buffer_array = np.frombuffer(buffer, dtype=dt)
        yield buffer_array

def generate_audio(buf, file_name):
    buf = np.asarray(buf, dtype=np.float64)
    buf = buf - np.mean(buf)
    buf /= max(abs(buf))
    sf.write(f"{file_name}.wav", buf, FREQ_SAMPLING)

if __name__ == "__main__":
    argParser = argparse.ArgumentParser()
    argParser.add_argument("-p", "--port", help="Port for serial communication")
    args = argParser.parse_args()
    print("uart-reader launched...\n")

    if args.port is None:
        print("No port specified, here is a list of serial communication port available")
        print("================")
        port = list(list_ports.comports())
        for p in port:
            print(p.device)
        print("================")
        print("Launch this script with [-p PORT_REF] to access the communication port")
    else:
        plt.figure(figsize=(10, 5))
        input_stream = reader(port=args.port)
        msg_counter = 0
        label_index = 0

        for msg in input_stream:
            if label_index >= len(LABELS):
                print("Acquisition complete.")
                break

            file_name = f"{LABELS[label_index]}_{msg_counter % SAMPLES_PER_LABEL:02d}"
            print(f"Acquisition #{msg_counter}: Saving as {file_name}.wav")

            buffer_size = len(msg)
            times = np.linspace(0, buffer_size - 1, buffer_size) * 1 / FREQ_SAMPLING
            voltage_mV = msg * VDD / VAL_MAX_ADC * 1e3

            generate_audio(msg, file_name)
            msg_counter += 1

            if msg_counter % SAMPLES_PER_LABEL == 0:
                label_index += 1
