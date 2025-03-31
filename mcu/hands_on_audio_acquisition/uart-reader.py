#!/usr/bin/env python3
import argparse
import serial
import threading
import queue
from serial.tools import list_ports

BUFFER_SIZE = 50000  # 25000 échantillons * 2 octets
WRITE_BUFFER_LIMIT = 10  # Nombre de paquets à accumuler avant écriture
WRITE_QUEUE_MAXSIZE = 100  # Limite de la file d'attente pour éviter un débordement

def reader(port, data_queue):
    ser = serial.Serial(port=port, baudrate=115200)
    buf = bytearray(BUFFER_SIZE)
    while True:
        n = ser.readinto(buf)
        if n != BUFFER_SIZE:
            print("Erreur: paquet incomplet")
            continue
        # On place une copie immuable du buffer dans la file d'attente
        data_queue.put(bytes(buf))

def writer(output_file, data_queue):
    write_buffer = bytearray()
    msg_counter = 0
    with open(output_file, "wb") as f:
        while True:
            try:
                msg = data_queue.get(timeout=1)
            except queue.Empty:
                continue  # Rien dans la file d'attente, on réessaie

            write_buffer += msg
            msg_counter += 1

            if msg_counter % WRITE_BUFFER_LIMIT == 0:
                f.write(write_buffer)
                write_buffer = bytearray()
                print(f"Acquisition #{msg_counter}: écriture groupée")
            data_queue.task_done()

def main():
    parser = argparse.ArgumentParser(description="Enregistrement binaire depuis le port série.")
    parser.add_argument("-p", "--port", help="Port de communication série")
    parser.add_argument("-o", "--output", help="Nom du fichier binaire de sortie", default="output.bin")
    args = parser.parse_args()

    if args.port is None:
        print("Aucun port spécifié. Voici la liste des ports disponibles :")
        for p in list_ports.comports():
            print(p.device)
        print("Lancez ce script avec [-p PORT_REF]")
        return

    data_queue = queue.Queue(maxsize=WRITE_QUEUE_MAXSIZE)
    print("Démarrage de l'enregistrement binaire avec lecture/écriture asynchrones...")

    # Démarrer le thread d'écriture
    writer_thread = threading.Thread(target=writer, args=(args.output, data_queue), daemon=True)
    writer_thread.start()

    try:
        # Lancer la lecture dans le thread principal
        reader(args.port, data_queue)
    except KeyboardInterrupt:
        print("Arrêt de l'enregistrement.")

if __name__ == "__main__":
    main()