"""
uart-reader.py
ELEC PROJECT - 210x
"""

import argparse
import serial
from serial.tools import list_ports
import re  # For extracting numbers

argParser = argparse.ArgumentParser()
argParser.add_argument("-p", "--port", help="Port for serial communication")
args = argParser.parse_args()
print("basic-uart-reader launched...\n")

if args.port is None:
    print("No port specified, here is a list of serial communication ports available")
    print("================")
    port = list(list_ports.comports())
    for p in port:
        print(p.device)
    print("================")
    print("Launch this script with [-p PORT_REF] to access the communication port")
else:
    serialPort = serial.Serial(
        port=args.port,
        baudrate=115200,
        bytesize=8,
        timeout=2,
        stopbits=serial.STOPBITS_ONE,
    )
    serialString = ""  # Used to hold data coming over UART
    values = []  # List to store the numeric values
    max_average = None  # To keep track of the maximum average seen so far

    while True:
        if serialPort.in_waiting > 0:
            serialString = serialPort.readline()

            try:
                line = serialString.decode("Ascii").strip()
                print(line)

                # Use regex to find the first integer in the line
                match = re.search(r'\d+', line)
                if match:
                    value = float(match.group())
                    values.append(value)

                    if len(values) == 20:
                        average = sum(values) / len(values)
                        print(f"\n>>> Average of last 20 readings: {average:.2f}")

                        # Update the maximum average if needed
                        if (max_average is None) or (average > max_average):
                            max_average = average

                        print(f">>> Maximum average so far: {max_average:.2f}\n")

                        values = []  # Reset for next 20 readings
                else:
                    print("No number found in line, skipping.")

            except Exception as e:
                print(f"Error processing line: {e}")
