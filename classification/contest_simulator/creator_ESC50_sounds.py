from pydub import AudioSegment
import os
import random
from datetime import timedelta

def normalize_audio_to_target_dbfs(audio_segment, target_dbfs=-1.0):
    """Normalise un segment à un niveau dBFS donné (par défaut -1.0 dBFS)"""
    change_in_dBFS = target_dbfs - audio_segment.max_dBFS
    return audio_segment.apply_gain(change_in_dBFS)


def make_5s_gunshot_segment(gunshot_folder):
    """
    Pick exactly 3 random gunshot_xx.wav files from gunshot_folder,
    each of length 1 second, separated by 1 second of silence,
    for a total of ~5s.
    """
    gunshot_candidates = [
        f for f in os.listdir(gunshot_folder)
        if f.startswith("gunshot_")
        and f.endswith(".wav")
        and len(f.split("_")[1].split(".")[0]) == 2
    ]
    if len(gunshot_candidates) < 3:
        raise ValueError(
            f"Not enough gunshot_xx.wav files in {gunshot_folder} to pick 3."
        )

    chosen_3 = random.sample(gunshot_candidates, 3)
    final_segment = AudioSegment.silent(duration=0)

    for i, shot_file in enumerate(chosen_3):
        shot_path = os.path.join(gunshot_folder, shot_file)
        shot = AudioSegment.from_wav(shot_path)
        shot = shot[:1000]  # 1 second only
        final_segment += shot
        # add 1s silence between the 3 shots
        if i < 2:
            final_segment += AudioSegment.silent(duration=1000)

    return final_segment

def ms_to_timestamp(ms):
    """
    Convert milliseconds to an hh:mm:ss.milliseconds string.
    """
    return str(timedelta(milliseconds=ms))

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
    """
    1) Collect random segments for each class from a single folder.
    2) Optionally handle gunshot differently if gunshot_exception=True.
    3) Shuffle and concatenate them, adding random silences overlaid
       with background noise.
    4) Overlay a continuous background noise track over the entire result.
    5) Write a log listing start/end times for each event.
    """
    # Classes to handle
    class_names = ["chainsaw", "fire", "fireworks", "gunshot"]
    # This will hold (AudioSegment, label)
    all_segments = []
    # For event logging: (start_time, end_time, label)
    segment_info = []

    # Gunshot folder if we do the special exception logic
    gunshot_folder = "classification/src/classification/datasets/garbage/useless_sounds"

    # For each class, collect the correct files from `input_folder`
    for cname in class_names:
        # If gunshot exception is set, we build them differently
        if cname == "gunshot" and gunshot_exception:
            segments = []
            for _ in range(segments_per_class):
                seg = make_5s_gunshot_segment(gunshot_folder)
                segments.append((seg, "gunshot"))
            print(f"[{cname}] Generated {len(segments)} special 5s gunshot segments.")
        else:
            # Collect files from `input_folder` that match e.g. "chainsaw_XX.wav"
            class_files = [
                f
                for f in os.listdir(input_folder)
                if f.startswith(f"{cname}_")
                and f.endswith(".wav")
                and len(f.split("_")[1].split(".")[0]) == 2
            ]
            if not class_files:
                raise ValueError(f"No files found for class '{cname}' in {input_folder}")

            # Randomly sample the needed number of files
            chosen_files = random.sample(
                class_files, min(len(class_files), segments_per_class)
            )
            segments = []
            for file in chosen_files:
                file_path = os.path.join(input_folder, file)
                segment = AudioSegment.from_wav(file_path)
                if len(segment) < segment_duration:
                    print(
                        f"⚠️  File {file} is too short ({len(segment)} ms). Skipped."
                    )
                    continue
                # Keep only the desired duration
                segments.append((segment[:segment_duration], cname))

            print(f"[{cname}] {len(segments)} segment(s) obtained.")
        # Aggregate these segments across all classes
        all_segments.extend(segments)

    # Shuffle the entire list of segments from all classes
    random.shuffle(all_segments)

    # Start building the final composition
    combined = AudioSegment.silent(duration=0)
    current_time = 0

    # For each segment, add random silence (with noise) after
    for segment, label in all_segments:
        # Lower volume of main sound
        if label == "fire":
            segment = segment + sound_level + 20  # extra +10 dB for fire
        else:
            segment = segment + sound_level

        # Add the segment to the final track
        start_time = current_time
        combined += segment
        end_time = start_time + len(segment)
        segment_info.append((ms_to_timestamp(start_time), ms_to_timestamp(end_time), label))

        current_time += len(segment)

        # Add a random delay between segments
        delay_duration = random.randint(3000, 5000) # 2 sec latency + 1-3 sec blank
        background_noise = AudioSegment.from_file(bg_file) + bg_level
        # Make sure background noise is at least 'delay_duration' long
        if len(background_noise) < delay_duration:
            background_noise *= (delay_duration // len(background_noise)) + 1
        # Slice out exactly the needed delay
        background_noise = background_noise[:delay_duration]
        combined += background_noise
        current_time += delay_duration

    # Overlay a continuous background for the entire length
    final_length = len(combined)
    full_bg = AudioSegment.from_file(bg_file) + bg_level
    # Extend the background to match the entire final length
    if len(full_bg) < final_length:
        full_bg *= (final_length // len(full_bg)) + 1
    full_bg = full_bg[:final_length]

    # Mix: overlay the final composition with continuous background
    final_audio = combined.overlay(full_bg)

    # Export the final result
    final_audio.export(output_file, format="wav")
    print(f"\n✅ Audio file generated: {output_file}")

    # Write event log
    log_path = os.path.join("classification/contest_simulator", "event_log_ESC50_sounds.txt")
    with open(log_path, "w") as f:
        f.write("# start_time\tend_time\tlabel\n")
        for start, end, label in segment_info:
            f.write(f"{start}\t{end}\t{label}\n")
    print(f"📄 Event log written to: {log_path}")

# Example usage
if __name__ == "__main__":
    concatenate_audio(
        input_folder="classification/src/classification/datasets/garbage/soundfiles_ESC50_5sec",
        output_file="classification/contest_simulator/contest_ESC50_sounds.wav",
        bg_file="classification/src/classification/datasets/background/background.wav",
        sound_level=0,
        bg_level=-30,
        segments_per_class=5,
        gunshot_exception=True
    )
