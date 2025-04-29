"""import os
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import fftconvolve

# Define the key frequencies and amplitudes in dB
frequencies = np.array([
    10, 20, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 
    1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 
    10000, 11000, 12000])  # Hz

amplitudes_db = np.array([
    -20, -14, -6, -3, -1, 0, 0, 0, 0, 0, 0, 0, 
    0, 0, 0.5, 1, 2, 4, 5, 6, 7, 
    8, -6, -15])  # dB

# Convert amplitudes to linear scale
amplitudes_linear = 10**(amplitudes_db / 20)

# Interpolate to match the desired number of samples (55125)
num_samples = 55125
sampling_rate = 22050  # Example sampling rate
freqs_interpolated = np.linspace(0, sampling_rate / 2, num=num_samples // 2 + 1)  # Include Nyquist frequency
response_interpolated = np.interp(freqs_interpolated, frequencies, amplitudes_linear)

# Symmetrize the frequency response for IFFT
response_symmetric = np.concatenate((response_interpolated, response_interpolated[-2:0:-1]))

# Transform into an impulse response (time domain)
impulse_response = np.fft.irfft(response_symmetric, n=num_samples)

# Plot the frequency response
plt.figure()
plt.semilogx(freqs_interpolated, 20 * np.log10(response_interpolated))
plt.title("Frequency Response with 55125 Samples")
plt.xlabel("Frequency (Hz)")
plt.ylabel("Amplitude (dB)")
plt.grid(True)
plt.show()

# Ensure the data directory exists
os.makedirs("classification/data", exist_ok=True)

# Save the filter response
np.save("classification/data/frequency_filter.npy", response_interpolated)

# Save the impulse response
np.save("classification/data/impulse_response.npy", impulse_response)

print("Filter response and impulse response saved successfully in the 'data' directory.")
"""


import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import fftconvolve

# 1. Définir les fréquences clés et amplitudes en dB (approximé à partir du graphe)
frequencies = np.array([
    10, 20, 50, 100, 200, 300, 400, 500, 600, 700, 800, 900, 
    1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 
    10000, 11000, 12000])  # en Hz

amplitudes_db = np.array([
    -20, -14, -6, -3, -1, 0, 0, 0, 0, 0, 0, 0, 
    0, 0, 0.5, 1, 2, 4, 5, 6, 7, 
    8, -6, -15])  # Normalisé en dB


# 2. Convertir les amplitudes en gain linéaire
amplitudes_linear = 10**(amplitudes_db / 20)

# 3. Interpoler pour obtenir une réponse fréquentielle détaillée
freqs_interpolated = np.logspace(np.log10(10), np.log10(20000), num=500)
response_interpolated = np.interp(freqs_interpolated, frequencies, amplitudes_linear)

# 4. Symétriser la réponse fréquentielle pour l'IFFT
response_symmetric = np.concatenate((response_interpolated, response_interpolated[::-1]))

# 5. Transformer en réponse impulsionnelle (temporelle)
impulse_response = np.fft.irfft(response_symmetric)

# 6. Appliquer le filtre par convolution sur un signal d'entrée
def apply_filter(signal, sr):
    filtered_signal = fftconvolve(signal, impulse_response, mode='full')
    return filtered_signal

# Visualisation
plt.figure()
plt.semilogx(freqs_interpolated, 20 * np.log10(response_interpolated))
plt.title("Réponse fréquentielle recréée")
plt.xlabel("Fréquence (Hz)")
plt.ylabel("Amplitude (dB)")
plt.grid(True)
plt.show()
