#!/usr/bin/env python3
import argparse
import serial
from serial.tools import list_ports

BUFFER_SIZE = 50000  # 25000 échantillons * 2 octets
WRITE_BUFFER_LIMIT = 10  # nombre de paquets à accumuler avant écriture

def reader(port=None):
    ser = serial.Serial(port=port, baudrate=115200)
    # Pré-allouer un buffer mutable
    buf = bytearray(BUFFER_SIZE)
    while True:
        n = ser.readinto(buf)
        if n != BUFFER_SIZE:
            print("Erreur: paquet incomplet")
            continue
        # Créer une copie immuable pour éviter les altérations ultérieures
        yield bytes(buf)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enregistrement binaire depuis le port série.")
    parser.add_argument("-p", "--port", help="Port de communication série")
    parser.add_argument("-o", "--output", help="Nom du fichier binaire de sortie", default="output.bin")
    args = parser.parse_args()

    if args.port is None:
        print("Aucun port spécifié. Voici la liste des ports disponibles :")
        for p in list_ports.comports():
            print(p.device)
        print("Lancez ce script avec [-p PORT_REF]")
    else:
        print("Démarrage de l'enregistrement binaire...")
        write_buffer = bytearray()
        msg_counter = 0
        try:
            with open(args.output, "wb") as f:
                for msg in reader(port=args.port):
                    # Pour améliorer les performances, on réduit le nombre de prints
                    if msg_counter % WRITE_BUFFER_LIMIT == 0:
                        print(f"Acquisition #{msg_counter}: traitement d'un paquet")
                    write_buffer += msg
                    msg_counter += 1

                    # Écriture groupée
                    if msg_counter % WRITE_BUFFER_LIMIT == 0:
                        f.write(write_buffer)
                        write_buffer = bytearray()

                # Écriture du dernier buffer incomplet (si existant)
                if write_buffer:
                    f.write(write_buffer)
        except KeyboardInterrupt:
            print("Arrêt de l'enregistrement.")
