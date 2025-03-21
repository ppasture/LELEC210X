import random
from typing import Tuple

import librosa
import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
import soundfile as sf
from numpy import ndarray
from scipy.signal import fftconvolve
from scipy import signal
from scipy.signal import firwin, lfilter

# -----------------------------------------------------------------------------
"""
Synthesis of the classes in :
- AudioUtil : util functions to process an audio signal.
- Feature_vector_DS : Create a dataset class for the feature vectors.
"""
# -----------------------------------------------------------------------------


class AudioUtil:
    """
    Define a new class with util functions to process an audio signal.
    """

    def open(audio_file) -> Tuple[ndarray, int]:
        """
        Load an audio file.

        :param audio_file: The path to the audio file.
        :return: The audio signal as a tuple (signal, sample_rate).
        """
        sig, sr = sf.read(audio_file)
        if sig.ndim > 1:
            sig = sig[:, 0]
        return (sig, sr)

    def play(audio):
        """
        Play an audio file.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        """
        sig, sr = audio
        sd.play(sig, sr)

    def normalize(audio, target_dB=52) -> Tuple[ndarray, int]:
        """
        Normalize the energy of the signal.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param target_dB: The target energy in dB.
        """
        sig, sr = audio
        sign = sig / np.sqrt(np.sum(np.abs(sig) ** 2))
        C = np.sqrt(10 ** (target_dB / 10))
        sign *= C
        return (sign, sr)

    def resample(audio, newsr=11025) -> Tuple[ndarray, int]:
        """
        Resample to target sampling frequency.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param newsr: The target sampling frequency.
        """
        sig, sr = audio

        ### TO COMPLETE
        time_duration = len(sig)/sr
        resig = signal.resample(sig, int(newsr*time_duration))
        return (resig, newsr)


    def pad_trunc(audio, max_ms) -> Tuple[ndarray, int]:
        """
        Pad (or truncate) the signal to a fixed length 'max_ms' in milliseconds.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param max_ms: The target length in milliseconds.
        """
        sig, sr = audio
        sig_len = len(sig)
        max_len = int(sr * max_ms / 1000)

        if sig_len > max_len:
            # Truncate the signal to the given length at random position
            # begin_len = random.randint(0, max_len)
            begin_len = 0
            sig = sig[begin_len : begin_len + max_len]

        elif sig_len < max_len:
            # Length of padding to add at the beginning and end of the signal
            pad_begin_len = random.randint(0, max_len - sig_len)
            pad_end_len = max_len - sig_len - pad_begin_len

            # Pad with 0s
            pad_begin = np.zeros(pad_begin_len)
            pad_end = np.zeros(pad_end_len)

            # sig = np.append([pad_begin, sig, pad_end])
            sig = np.concatenate((pad_begin, sig, pad_end))

        return (sig, sr)

    def time_shift(audio, shift_limit=1) -> Tuple[ndarray, int]:
        """
        Shifts the signal to the left or right by some percent. Values at the end are 'wrapped around' to the start of the transformed signal.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param shift_limit: The percentage (between 0.0 and 1.0) by which to circularly shift the signal.
        """
        sig, sr = audio
        sig_len = len(sig)
        
        shift_limit = max(0.0, min(shift_limit, 1.0))
        shift_amt = int(random.uniform(-shift_limit, shift_limit) * sig_len)
        shifted_sig = np.roll(sig, shift_amt)

        return (shifted_sig, sr)

    def scaling(audio, scaling_limit=10) -> Tuple[ndarray, int]:
        """
        Augment the audio signal by scaling it by a random factor.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param scaling_limit: The maximum scaling factor.
        """
        sig, sr = audio

        ### TO COMPLETE
        scaling_factor = random.uniform(1.0 / scaling_limit, scaling_limit)

        scaled_sig = sig * scaling_factor
        return (scaled_sig, sr)

    def add_noise(audio: Tuple[ndarray, int], snr_db: float = 20) -> Tuple[ndarray, int]:
        """
        Add Gaussian noise to the signal to achieve a desired SNR in dB.

        :param audio: Tuple (signal, sample_rate)
        :param snr_db: Desired Signal-to-Noise Ratio in dB (default: 20)
        :return: Tuple (noisy_signal, sample_rate)
        """
        sig, sr = audio
        # Compute signal power
        signal_power = np.mean(sig**2)
        # Compute desired noise power for given SNR
        snr_linear = 10**(snr_db / 10)
        noise_power = signal_power / snr_linear
        # Generate noise with this power
        noise = np.random.normal(0, np.sqrt(noise_power), size=sig.shape)
        # Add noise to the original signal
        noisy_signal = sig + noise
        return noisy_signal, sr


    def echo(audio, nechos) -> Tuple[ndarray, int]:
        """
        Add echo to the audio signal by convolving it with an impulse response. The taps are regularly spaced in time and each is twice smaller than the previous one.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param nechos: The number of echoes.
        """
        sig, sr = audio
        sig_len = len(sig)
        if nechos <= 0:
            return sig, sr
        
        echo_sig = np.zeros(sig_len)
        echo_sig[0] = 1
        echo_sig[(np.arange(nechos) / nechos * sig_len).astype(int)] = (
            1 / 2
        ) ** np.arange(nechos)

        sig = fftconvolve(sig, echo_sig, mode="full")[:sig_len]
        return (sig, sr)

    def filter(audio, filt) -> Tuple[ndarray, int]:
        """
        Filter the audio signal with a provided filter. Note the filter is given for positive frequencies only and is thus symmetrized in the function.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param filt: The filter to apply.
        """
        sig, sr = audio

        ### TO COMPLETE
        # Symmetrize the filter
        filt = np.concatenate((filt, filt[::-1]))
        # Apply the filter
        filtered_sig = np.convolve(sig, filt, mode='full')
        return (filtered_sig, sr)

    def add_bg(
        audio, dataset, num_sources=1, max_ms=5000, amplitude_limit=0.1
    ) -> Tuple[ndarray, int]:
        """
        Adds up sounds uniformly chosen at random to audio.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param dataset: The dataset to sample from.
        :param num_sources: The number of sounds to add.
        :param max_ms: The maximum duration of the sounds to add.
        :param amplitude_limit: The maximum amplitude of the added sounds.
        """
        sig, sr = audio
       ### TO COMPLETE

        class_name = dataset.list_classes()[random.randint(0,len(dataset.list_classes())-1)] #gets a random sound class
        random_soundidx = random.randint(0,len(dataset)//len(dataset.list_classes())-1)
        add_audio = AudioUtil.open(dataset[class_name,random_soundidx])#gets a random sound in the class
        add_audio = AudioUtil.resample(add_audio,sr) #ensure both sounds are at the same sample rate
        add_audio = AudioUtil.pad_trunc(add_audio,max_ms=max_ms)  #limit the duration of the sound
        add_sound = add_audio[0]*amplitude_limit/max(add_audio[0]) #limit the amplitude
        new_sound = sig + add_sound
        return new_sound,sr


    def specgram(audio, Nft=512, fs2=11025) -> ndarray:
        """
        Compute a Spectrogram.

        :param aud: The audio signal as a tuple (signal, sample_rate).
        :param Nft: The number of points of the FFT.
        :param fs2: The sampling frequency.
        """
        ### TO COMPLETE
        # stft /= float(2**8)
        audio = AudioUtil.resample(audio, fs2)
        y = audio[0]
        y = y[: len(y) - len(y) % Nft]
        audiomat = np.reshape(y, (len(y) // Nft, Nft))
        audioham = audiomat * np.hamming(Nft)
        stft = np.fft.fft(audioham, axis=1)
        stft_mag = np.abs(stft[:, : Nft // 2].T)

        

        return stft_mag

    def get_hz2mel(fs2=11025, Nft=512, Nmel=20) -> ndarray:
        """
        Get the hz2mel conversion matrix.

        :param fs2: The sampling frequency.
        :param Nft: The number of points of the FFT.
        :param Nmel: The number of mel bands.
        """
        mels = librosa.filters.mel(sr=fs2, n_fft=Nft, n_mels=Nmel)
        mels = mels[:, :-1]
        mels = mels / np.max(mels)

        return mels

    def melspectrogram(audio, Nmel=20, Nft=512, fs2=11025) -> ndarray:
        """
        Generate a Melspectrogram.

        :param audio: The audio signal as a tuple (signal, sample_rate).
        :param Nmel: The number of mel bands.
        :param Nft: The number of points of the FFT.
        :param fs2: The sampling frequency.
        """
        ### TO COMPLETE
        stft = AudioUtil.specgram(audio, Nft=Nft, fs2=fs2)
        mels = AudioUtil.get_hz2mel(fs2=fs2, Nft=Nft, Nmel=Nmel)
        melspec = np.dot(mels, stft)


        
        return melspec

    def spectro_aug_timefreq_masking(
        spec, max_mask_pct=0.1, n_freq_masks=1, n_time_masks=1
    ) -> ndarray:
        """
        Augment the Spectrogram by masking out some sections of it in both the frequency dimension (ie. horizontal bars) and the time dimension (vertical bars) to prevent overfitting and to help the model generalise better. The masked sections are replaced with the mean value.


        :param spec: The spectrogram.
        :param max_mask_pct: The maximum percentage of the spectrogram to mask out.
        :param n_freq_masks: The number of frequency masks to apply.
        :param n_time_masks: The number of time masks to apply.
        """
        Nmel, n_steps = spec.shape
        mask_value = np.mean(spec)
        aug_spec = np.copy(spec)  # avoids modifying spec

        freq_mask_param = max_mask_pct * Nmel
        for _ in range(n_freq_masks):
            height = int(np.round(random.random() * freq_mask_param))
            pos_f = np.random.randint(Nmel - height)
            aug_spec[pos_f : pos_f + height, :] = mask_value

        time_mask_param = max_mask_pct * n_steps
        for _ in range(n_time_masks):
            width = int(np.round(random.random() * time_mask_param))
            pos_t = np.random.randint(n_steps - width)
            aug_spec[:, pos_t : pos_t + width] = mask_value

        return aug_spec

    def lowpass_filter(audio: Tuple[ndarray, int], cutoff_hz: float = 3000.0, numtaps: int = 101) -> Tuple[ndarray, int]:
        """
        Apply a low-pass filter to the audio signal.

        :param audio: Tuple (signal, sample_rate)
        :param cutoff_hz: Cutoff frequency in Hz
        :param numtaps: Number of filter taps
        :return: Tuple (filtered_signal, sample_rate)
        """
        sig, sr = audio
        nyquist = sr / 2
        norm_cutoff = cutoff_hz / nyquist

        # Create low-pass filter
        taps = firwin(numtaps, norm_cutoff)

        # Apply the filter using lfilter
        filtered_sig = lfilter(taps, 1.0, sig)

        return filtered_sig, sr
        
class Feature_vector_DS:
    """
    Dataset of Feature vectors.
    """

    def __init__(
        self,
        dataset,
        Nft=512,
        nmel=20,
        duration=500,
        shift_pct=0.4,
        normalize=False,
        data_aug=None,
        pca=None,
    ):
        self.dataset = dataset
        self.Nft = Nft
        self.nmel = nmel
        self.duration = duration  # ms
        self.sr = 11025
        self.shift_pct = shift_pct  # percentage of total
        self.normalize = normalize
        self.data_aug = data_aug
        self.data_aug_factor = 1
        if isinstance(self.data_aug, list):
            self.data_aug_factor += len(self.data_aug) +1
        else:
            self.data_aug = [self.data_aug]
        self.ncol = int(
            self.duration * self.sr / (1e3 * self.Nft)
        )  # number of columns in melspectrogram
        self.pca = pca

    def __len__(self) -> int:
        """
        Number of items in dataset.
        """
        return len(self.dataset) * self.data_aug_factor

    def get_audiosignal(self, cls_index: Tuple[str, int, str, str]) -> Tuple[ndarray, int]:
        """
        Get temporal signal of i'th item in dataset.

        :param cls_index: Class name and index.
        """
        aug = cls_index[2]
        filtering = cls_index[3]
        cls_index = cls_index[:2]
        audio_file = self.dataset[cls_index]
        aud = AudioUtil.open(audio_file)
        aud = AudioUtil.resample(aud, self.sr)
        aud = AudioUtil.pad_trunc(aud, self.duration)
        if (filtering == "lowpass"):
            aud = AudioUtil.lowpass_filter(aud, cutoff_hz=3000)
        if aug != "original":
            if aug == "add_bg":
                aud = AudioUtil.add_bg(aud, self.dataset, num_sources=1, max_ms=self.duration, amplitude_limit=0.04)
            if aug == "echo":
                aud = AudioUtil.echo(aud, nechos=2)
            if aug == "noise":
                aud = AudioUtil.add_noise(aud, snr_db=20)
            if aug == "filter":
                filt = np.array([1, -1])
                aud = AudioUtil.filter(aud, filt)
            if aug == "scaling":
                aud = AudioUtil.scaling(aud, scaling_limit=10)
            if aug == "shifting":
                aud = AudioUtil.time_shift(aud, shift_limit=1)
            for num_str in map(str, range(0, 22)):  # Generate strings "1" to "20"
                if aug == num_str:   
                    amplitude_limit = int(num_str) * 0.02
                    aud = AudioUtil.add_bg(aud, self.dataset, num_sources=1, max_ms=self.duration, amplitude_limit=amplitude_limit)
        return aud

    def __getitem__(self, cls_index: Tuple[str, int, str, str]) -> Tuple[ndarray, int]:
        """
        Get i'th item in dataset.

        :param cls_index: Class name and index.
        """
        aud = self.get_audiosignal(cls_index)
        sgram = AudioUtil.melspectrogram(aud, Nmel=self.nmel, Nft=self.Nft)
        aug = cls_index[2]
        if aug == "aug_sgram":
            sgram = AudioUtil.spectro_aug_timefreq_masking(sgram, max_mask_pct=0.1, n_freq_masks=2, n_time_masks=2)

        sgram_crop = sgram[:, : self.ncol]
        fv = sgram_crop.flatten()  # feature vector
        #fv /= np.linalg.norm(fv) no normalization
        return fv

    def display(self, cls_index: Tuple[str, int]):
        """
        Play sound and display i'th item in dataset.

        :param cls_index: Class name and index.
        """
        audio = self.get_audiosignal(cls_index)
        AudioUtil.play(audio)
        plt.figure(figsize=(4, 3))
        plt.imshow(
            AudioUtil.melspectrogram(audio, Nmel=self.nmel, Nft=self.Nft),
            cmap="jet",
            origin="lower",
            aspect="auto",
        )
        plt.colorbar()
        plt.title(audio)
        plt.title(self.dataset.__getname__(cls_index))
        plt.show()

    def mod_data_aug(self, data_aug) -> None:
        """
        Modify the data augmentation options.

        :param data_aug: The new data augmentation options.
        """
        self.data_aug = data_aug
        self.data_aug_factor = 1
        if isinstance(self.data_aug, list):
            self.data_aug_factor = len(self.data_aug)
        else:
            self.data_aug = [self.data_aug]
