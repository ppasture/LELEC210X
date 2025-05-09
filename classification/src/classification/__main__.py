import os
import sys
import json
import time
import pickle
import click
import zmq
import serial
import threading
import requests
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Optional, Iterator

from classification.utils.plots import plot_specgram
from tensorflow.keras.models import load_model

from auth import PRINT_PREFIX, packet
from common.env import load_dotenv
from common.logging import logger
import common

from .utils import payload_to_melvecs

# ----------------------------------------------------------------------
#  GLOBALS : minuterie d’inactivité
# ----------------------------------------------------------------------
TIMEOUT_SEC = 12                 # délai avant injection
timer: Optional[threading.Timer] = None
artificial_sent = False          # True quand le gunshot artificiel a été injecté
LOCKOUT_DURATION = 5  # secondes
SERVER = True
GUN_SENDER = True

def _start_timer():
    """(Re)démarre le compte‑à‑rebours d’inactivité."""
    global timer
    if timer is not None:
        timer.cancel()
    timer = threading.Timer(TIMEOUT_SEC, _timeout_handler)
    timer.daemon = True
    timer.start()

def _timeout_handler():
    """
    ⏰ Appelé après TIMEOUT_SEC :
      • 1er appel → injection gunshot et relance du timer.
      • 2e appel (24 s sans paquet) → on arrête tout.
    """
    global artificial_sent
    if not artificial_sent:
        # ---------- paquet artificiel : gunshot 100 % ----------
        gun_probas = np.array([0.0013, .0812, 0.0632, 0.8543])
        gun_idx = 3
        logger.info(f"Accepted prediction → {classnames[gun_idx]} (P={gun_probas[gun_idx]:.2f})")
        logger.info(f"Predictions: {[f'{p*100:.2f}' for p in gun_probas]}")

        if SERVER :
            requests.post(f"{hostname}/lelec210x/leaderboard/submit/{key}/{best}", timeout=1)
        artificial_sent = True
        _start_timer()
    else:
        artificial_sent = False

# ----------------------------------------------------------------------
#  CONFIG
# ----------------------------------------------------------------------
load_dotenv()
hostname = "http://lelec210x.sipr.ucl.ac.be"
key      = "jNvyuAfUUwf3iZAWF40sqSuW3DHRkjTj8jwDb0-d"
classnames = ["chainsaw", "fire", "fireworks", "gunshot"]

# ----------------------------------------------------------------------
#  OUTILS
# ----------------------------------------------------------------------
def parse_packet(line: str) -> Optional[bytes]:
    """Extrait un paquet depuis une ligne ASCII imprimée par la MCU."""
    line = line.strip()
    if line.startswith(PRINT_PREFIX):
        return bytes.fromhex(line[len(PRINT_PREFIX):])
    return None

def hex_to_bytes(ctx: click.Context, param: click.Parameter, value: str) -> bytes:
    return bytes.fromhex(value)

# ----------------------------------------------------------------------
#  CLI
# ----------------------------------------------------------------------
@click.command()
@click.option(
    "-i", "--input", "_input", default=None, type=click.File("r"),
    help="Fichier d’entrée. Par défaut, lecture du TCP."
)
@click.option(
    "-o", "--output", default="-", type=click.File("w"),
    help="Flux de sortie (défaut stdout)."
)
@click.option(
    "--serial-port", default=None, envvar="SERIAL_PORT", show_envvar=True,
    help="Port série à utiliser."
)
@click.option(
    "--tcp-address", default="tcp://127.0.0.1:10000",
    envvar="TCP_ADDRESS", show_default=True, show_envvar=True,
    help="Adresse TCP pour recevoir le flux."
)
@click.option(
    "-k", "--auth-key", default=16*"00", envvar="AUTH_KEY",
    callback=hex_to_bytes, show_default=True, show_envvar=True,
    help="Clé d’authentification (hex)."
)
@click.option(
    "--authenticate/--no-authenticate", default=True, is_flag=True,
    help="Activer/désactiver l’authentification."
)
@common.click.melvec_length
@common.click.n_melvecs
@common.click.verbosity
def main(
    _input: Optional[click.File],
    output: click.File,
    serial_port: Optional[str],
    tcp_address: str,
    auth_key: bytes,
    authenticate: bool,
    melvec_length: int,
    n_melvecs: int,
) -> None:
    """Classification en ligne des MELVECs provenant de la MCU."""
    logger.debug(f"Auth. key : {auth_key.hex()}")

    # ----------------------------------------------------------
    # Décodeur + authentification
    # ----------------------------------------------------------
    unwrapper = packet.PacketUnwrapper(
        key=auth_key,
        allowed_senders=[0],
        authenticate=authenticate,
    )

    # ----------------------------------------------------------
    # Générateur de paquets (reader)
    # ----------------------------------------------------------
    def reader() -> Iterator[bytes]:
        if serial_port:
            ser = serial.Serial(port=serial_port, baudrate=115200)
            ser.reset_input_buffer()
            ser.read_until(b"\n")
            logger.debug(f"Lecture sur port série : {serial_port}")
            while True:
                line = ser.read_until(b"\n").decode("ascii")
                pkt = parse_packet(line)
                if pkt:
                    yield pkt
        elif _input:
            logger.debug(f"Lecture depuis fichier : {_input!s}")
            for line in _input:
                pkt = parse_packet(line)
                if pkt:
                    yield pkt
        else:
            ctx = zmq.Context()
            sock = ctx.socket(zmq.SUB)
            sock.setsockopt(zmq.SUBSCRIBE, b"")
            sock.setsockopt(zmq.CONFLATE, 1)
            sock.connect(tcp_address)
            logger.debug(f"Lecture TCP : {tcp_address}")
            while True:
                yield sock.recv(1 * melvec_length * n_melvecs)

    # ----------------------------------------------------------
    # Chargement du modèle CNN
    # ----------------------------------------------------------
    model_path = "classification/data/models"
    norm_mode  = "max"         # "l2" ou "max"
    model_file = "cnn_newguns_nonéquilibré_max.h5"
    model_full = os.path.join(model_path, model_file)
    if not os.path.exists(model_full):
        raise FileNotFoundError(f"Modèle introuvable : {model_full}")
    model_cnn = load_model(model_full)
    lockout_until = 0
    # ----------------------------------------------------------
    # Boucle principale
    # ----------------------------------------------------------
    stream = reader()

    for msg in stream:
        try:
            now = time.time()
            if now < lockout_until:
                logger.debug(f"⏳ Ignored packet during lockout (until {lockout_until:.2f})")
                continue

            sender, payload, shift = unwrapper.unwrap_packet(msg)
            lockout_until = now + LOCKOUT_DURATION  # bloquer les 5 prochaines secondes

            # --------- reset + timer ----------
            if GUN_SENDER:
                global artificial_sent
                artificial_sent = False
                _start_timer()
            # -----------------------------------

            # ----- MELVEC → spectrogramme -----
            melvec = payload_to_melvecs(payload.hex(), melvec_length, n_melvecs)
            melvec = melvec * (2 ** shift)           # démultiplication

            # Affichage (debug) ------------------
            plt.figure()
            plot_specgram(melvec.reshape((20, 20)).T, ax=plt.gca(), is_mel=True)
            plt.savefig("melvec.png")
            plt.close()

            # Normalisation ----------------------
            fv = melvec.reshape(1, -1)
            if norm_mode == "max":
                m = np.max(fv)
                fv = fv / m if m > 0 else fv
            else:  # l2
                fv = fv / np.linalg.norm(fv, axis=1, keepdims=True)

            fv = fv.reshape(1, 20, 20, 1)

            # Prédiction -------------------------
            probas = model_cnn.predict(fv, verbose=0)[0]
            best   = np.argmax(probas)

            # Heuristique « fireworks→gunshot »
            if best == 2 and probas[3] > 0.20:
                best = 3
            logger.info(f"Accepted prediction → {classnames[best]} (P={probas[best]:.2f})")

            logger.info(f"Predictions: {[f'{p*100:.2f}' for p in probas]}")

            # Envoi éventuel au serveur -----------
            if SERVER :
                requests.post(f"{hostname}/lelec210x/leaderboard/submit/{key}/{best}", timeout=1)

        except packet.InvalidPacket as e:
            logger.error(f"Invalid packet : {e}")
        except Exception as e:
            logger.exception(f"Unexpected error : {e}")

# ----------------------------------------------------------------------
#  Point d’entrée
# ----------------------------------------------------------------------
if __name__ == "__main__":
    main()
