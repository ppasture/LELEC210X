import numpy as np
import librosa
import matplotlib.pyplot as plt

def compute_max_frequency(file_path, amplitude_threshold):
    """
    Returns the highest frequency (Hz) in 'file_path' 
    whose amplitude (in FFT) is above 'amplitude_threshold'.

    :param file_path: Path to the audio file.
    :param amplitude_threshold: Minimum amplitude considered "present".
    :return: The maximum frequency detected (float).
    """
    # 1. Load audio (mono) with original sample rate
    signal, sr = librosa.load(file_path, sr=None)

    # 2. Compute FFT of the entire audio signal
    spectrum = np.fft.fft(signal)
    freqs = np.fft.fftfreq(len(spectrum), 1 / sr)
    
    # 3. Consider only positive frequencies
    positive_mask = freqs >= 0
    freqs_pos = freqs[positive_mask]
    amps_pos = np.abs(spectrum[positive_mask])

    # 4. Filter out frequencies below the amplitude threshold
    max_frequency = 0.0
    for f, amp in zip(freqs_pos, amps_pos):
        if amp > amplitude_threshold-1 and f > max_frequency:
            max_frequency = f

    return max_frequency



def plot_spectrum_for_index(index):
    """
    Plots the frequency spectrum for the specified index for all 4 sound classes,
    limiting the max frequency displayed to 10,000 Hz.

    :param index: Integer representing the file index (e.g., 00, 01, ..., 39)
    """
    # Format index as two-digit string (e.g., "00", "01", ..., "39")
    index_str = f"{index:02d}"

    # Define file paths
    file_paths = {
        "Gunshot": f"src/classification/datasets/soundfiles/gunshot_{index_str}.wav",
        "Fire": f"src/classification/datasets/soundfiles/fire_{index_str}.wav",
        "Chainsaw": f"src/classification/datasets/soundfiles/chainsaw_{index_str}.wav",
        "Fireworks": f"src/classification/datasets/soundfiles/fireworks_{index_str}.wav",
    }

    # Set up plot
    plt.figure(figsize=(12, 8))

    # Process each file and plot its spectrum
    for i, (label, file_path) in enumerate(file_paths.items(), 1):
        try:
            # Load audio file
            signal, sr = librosa.load(file_path, sr=None)

            # Compute FFT
            spectrum = np.fft.fft(signal)
            freqs = np.fft.fftfreq(len(spectrum), 1 / sr)

            # Keep only positive frequencies
            positive_mask = (freqs >= 0) & (freqs <= 10000)  # Limit max to 10,000 Hz
            freqs_pos = freqs[positive_mask]
            amps_pos = np.abs(spectrum[positive_mask])

            # Plot spectrum
            plt.subplot(2, 2, i)
            plt.plot(freqs_pos, amps_pos, color='blue')
            plt.xlim(0, 10000)  # Limit x-axis to 10,000 Hz
            plt.xlabel("Frequency (Hz)")
            plt.ylabel("Magnitude")
            plt.title(f"Spectrum of {label} ({index_str})")
            plt.grid()

        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    # Show the plot
    plt.tight_layout()
    plt.show()




# Example usage:
if __name__ == "__main__":
    
    """ # Measure max frequency
    max_freq = 0
    for i in range(40):
        index = f"{i:02d}"  # Formats `i` as a two-digit number (e.g., 00, 01, ..., 39)
        file_path_gun = f"src\\classification\\datasets\\soundfiles\\gunshot_{index}.wav"
        file_path_fire = f"src\\classification\\datasets\\soundfiles\\fire_{index}.wav"
        file_path_chainsaw = f"src\\classification\\datasets\\soundfiles\\chainsaw_{index}.wav"
        file_path_fireworks = f"src\\classification\\datasets\\soundfiles\\fireworks_{index}.wav"
        max_freq_gun = compute_max_frequency(file_path_gun, max_freq)
        max_freq_fire = compute_max_frequency(file_path_fire, max_freq)
        max_freq_chainsaw = compute_max_frequency(file_path_chainsaw, max_freq)
        max_freq_fireworks = compute_max_frequency(file_path_fireworks, max_freq)
        if max_freq_gun > max_freq:
            max_freq = max_freq_gun
            print(f"New max frequency found: {max_freq:.2f} Hz")
        if max_freq_fire > max_freq:
            max_freq = max_freq_fire
            print(f"New max frequency found: {max_freq:.2f} Hz")
        if max_freq_chainsaw > max_freq:
            max_freq = max_freq_chainsaw
            print(f"New max frequency found: {max_freq:.2f} Hz")
        if max_freq_fireworks > max_freq:
            max_freq = max_freq_fireworks
            print(f"New max frequency found: {max_freq:.2f} Hz")
            
    print(f"The maximum frequency is approximately {max_freq:.2f} Hz.")
    """
    
    
    spectrum_index = 5  # Change this to any index you want to visualize
    plot_spectrum_for_index(spectrum_index)