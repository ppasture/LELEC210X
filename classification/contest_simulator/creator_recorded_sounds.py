from pydub import AudioSegment
import os
import random
from datetime import timedelta

def slice_audio_segments(file_path, segment_duration_ms):
    audio = AudioSegment.from_wav(file_path)
    segments = []
    for start in range(0, len(audio) - segment_duration_ms + 1, segment_duration_ms):
        segments.append(audio[start:start + segment_duration_ms])
    return segments

def make_5s_gunshot_segment(gunshot_folder):
    gunshot_candidates = [
        f for f in os.listdir(gunshot_folder)
        if f.startswith("gunshot_")
        and f.endswith(".wav")
        and len(f.split("_")[1].split(".")[0]) == 2
    ]
    if len(gunshot_candidates) < 3:
        raise ValueError(f"Pas assez de fichiers gunshot_xx.wav dans {gunshot_folder} pour en choisir 3.")

    chosen_3 = random.sample(gunshot_candidates, 3)
    final_segment = AudioSegment.silent(duration=0)

    for i, shot_file in enumerate(chosen_3):
        shot_path = os.path.join(gunshot_folder, shot_file)
        shot = AudioSegment.from_wav(shot_path)
        shot = shot[:1000]  # Keep only the first 1s
        final_segment += shot
        if i < 2:
            final_segment += AudioSegment.silent(duration=1000)  # 1s silence

    return final_segment

def ms_to_timestamp(ms):
    td = timedelta(milliseconds=ms)
    return str(td)

def concatenate_audio(
    input_folder,
    output_file,
    bg_file,
    sound_level=-10,
    bg_level=-30,
    segment_duration=5000,
    segments_per_class=10,
    gunshot_exception=False,
):
    combined = AudioSegment.silent(duration=0)
    class_files = ["chainsaw_2.wav", "fire_2.wav", "fireworks_2.wav", "gunshot_2.wav"]
    all_segments = []
    segment_info = []  # To log events

    gunshot_folder = os.path.join(input_folder, "soundfiles")

    for filename in class_files:
        file_path = os.path.join(input_folder, filename)

        if filename == "gunshot.wav" and gunshot_exception:
            segments = []
            for _ in range(segments_per_class):
                seg = make_5s_gunshot_segment(gunshot_folder)
                segments.append((seg, "gunshot"))
            print(f"{filename} : {len(segments)} segment(s) spéciaux générés")
        else:
            segments = slice_audio_segments(file_path, segment_duration)
            print(f"{filename} : {len(segments)} segment(s) trouvés")
            if len(segments) > segments_per_class:
                segments = random.sample(segments, segments_per_class)
            elif len(segments) < segments_per_class:
                print(f"⚠️ Moins de {segments_per_class} segments pour {filename}, on prend tout.")

            label = filename.replace(".wav", "")
            segments = [(seg, label) for seg in segments]

        all_segments.extend(segments)

    random.shuffle(all_segments)

    current_time = 0

    for segment, label in all_segments:
        if label.split('_')[0] == "fire":
            segment = segment + sound_level + 10  # extra +10 dB for fire
        else:
            segment = segment + sound_level

        delay_duration = random.randint(3000, 5000)  # 2 sec latency + 1-3 sec blank
        delay = AudioSegment.silent(duration=delay_duration)

        # Log start & end time of the sound
        start_time = current_time
        end_time = start_time + len(segment)
        segment_info.append((ms_to_timestamp(start_time), ms_to_timestamp(end_time), label))

        # Update audio
        combined += segment

        # Add background noise as transition
        background_noise = AudioSegment.from_file(bg_file) + bg_level
        if len(background_noise) < delay_duration:
            background_noise *= (delay_duration // len(background_noise)) + 1
        background_noise = background_noise[:delay_duration]
        combined += background_noise

        # Update time pointer
        current_time += len(segment) + delay_duration

    full_bg = AudioSegment.from_file(bg_file) + bg_level
    if len(full_bg) < len(combined):
        full_bg *= (len(combined) // len(full_bg)) + 1
    full_bg = full_bg[:len(combined)]

    final_audio = combined.overlay(full_bg)
    final_audio.export(output_file, format="wav")
    print(f"\n✅ Fichier audio généré : {output_file}")

    # Write event log
    log_path = os.path.join("classification/contest_simulator", "event_log_recorded_sounds.txt")
    with open(log_path, "w") as f:
        f.write("# start_time\tend_time\tlabel\n")
        for start, end, label in segment_info:
            f.write(f"{start}\t{end}\t{label.split('_')[0]}\n")
    print(f"📄 Log des événements écrit dans : {log_path}")


# Example usage
if __name__ == "__main__":
    concatenate_audio(
        input_folder="classification/src/classification/datasets/recordings/",
        output_file="classification/contest_simulator/contest_recorded_sounds.wav",
        bg_file="classification/src/classification/datasets/background/background_recorded.wav",
        sound_level=0,
        bg_level=-20,
        segments_per_class=5,
        gunshot_exception=False
    )
