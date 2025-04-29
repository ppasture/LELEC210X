import numpy as np
import soundfile as sf
import os
import soundfile as sf

def crop_and_replicate_gunshot(index, crop_seconds, crop_position="end", replication_factor=1, save_copy=False, replicate_sconds=0, replicate_position="end"):
    """
    Crop a gunshot sound file by removing a given number of seconds from the beginning or end,
    then replicate (repeat) the cropped sound a given number of times.
    
    Before cropping, optionally replicate a segment from the beginning or end of the original sound.
    For example, if replicate_sconds is 0.1 and replicate_position is "begin", the first 0.1 second 
    of the sound will be replicated and prepended to the audio.

    Parameters:
    - index (int): The index of the gunshot to modify (00 to 39).
    - crop_seconds (float): Number of seconds to remove.
    - crop_position (str): Either "begin" or "end" to specify where to crop.
    - replication_factor (int): Number of times to repeat the cropped sound after cropping.
    - save_copy (bool): If True, saves the modified file with a new name instead of overwriting.
    - replicate_sconds (float): Duration (in seconds) of the segment to replicate from the original sound.
    - replicate_position (str): Either "begin" or "end" to specify which end of the sound to replicate.

    The function overwrites the original file unless save_copy=True.
    """
    # Define the base path
    base_path = "C:/Users/pierr/Documents/LELEC210X/classification/src/classification/datasets/soundfiles/"
    
    # Format the filename correctly with zero-padding
    file_name = f"gunshot_{index:02d}.wav"
    file_path = os.path.join(base_path, file_name)

    # Check if file exists
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    try:
        # Load the audio file
        data, sample_rate = sf.read(file_path)

        # Optionally replicate a segment from the original sound before cropping
        if replicate_sconds > 0:
            samples_to_replicate = int(replicate_sconds * sample_rate)
            if replicate_position == "begin":
                # Extract the beginning segment and prepend it
                replicate_segment = data[:samples_to_replicate]
                data = np.concatenate((replicate_segment, data), axis=0)
            elif replicate_position == "end":
                # Extract the end segment and append it
                replicate_segment = data[-samples_to_replicate:]
                data = np.concatenate((data, replicate_segment), axis=0)
            else:
                print("Error: replicate_position must be 'begin' or 'end'.")
                return

        # Calculate the number of samples to crop
        
        # Perform cropping
        if crop_seconds > 0:
            samples_to_crop = int(crop_seconds * sample_rate)
            if crop_position == "begin":
                data = data[samples_to_crop:]  # Remove from beginning
            elif crop_position == "end":
                data = data[:-samples_to_crop]  # Remove from end
            else:
                print("Error: crop_position must be 'begin' or 'end'.")
                return

        # Replicate the cropped sound
        if replication_factor > 0:
            data = np.tile(data, replication_factor)

        # Save the modified file (overwrite or save as a copy)
        if save_copy:
            new_file_name = f"gunshot_{index:02d}_modified.wav"
            save_path = os.path.join(base_path, new_file_name)
        else:
            save_path = file_path  # Overwrite original

        sf.write(save_path, data, sample_rate)
        print(f"Successfully processed {file_name}: replicated {replicate_sconds} seconds at the {replicate_position}, cropped {crop_seconds} seconds from the {crop_position}, and replicated the cropped sound {replication_factor} times.")

    except Exception as e:
        print(f"Error processing file '{file_path}': {e}")

# Main execution block with manual inputs
if __name__ == "__main__":
    index = 14              # Gunshot index (0 to 39)

    replicate_sconds = 0.03  # Duration of the segment to replicate before cropping
    replicate_position = "end"  # "begin" or "end"
    
    crop_seconds = 0     # Seconds to crop from the sound
    crop_position = "end"   # "begin" or "end"
    
    replication_factor = 5   # Number of times to replicate the cropped sound
    save_copy = False       # True to save as a new file, False to overwrite the original

    crop_and_replicate_gunshot(index, crop_seconds, crop_position, replication_factor, save_copy, replicate_sconds, replicate_position)
