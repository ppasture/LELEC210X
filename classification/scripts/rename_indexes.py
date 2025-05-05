import os

# Liste des classes attendues
CLASSES = ["fire", "chainsaw", "fireworks", "gunshot"]

# Récupère tous les fichiers .wav du dossier courant
all_files = [f for f in os.listdir('.') if f.endswith('.wav')]

# Dictionnaire pour regrouper les fichiers par classe
class_files = {cls: [] for cls in CLASSES}

# Regroupement
for f in all_files:
    for cls in CLASSES:
        if f.startswith(cls + "_"):
            class_files[cls].append(f)
            break

# Renommage avec indices à 3 chiffres
for cls, files in class_files.items():
    files.sort()  # pour une certaine cohérence
    for i, old_name in enumerate(files):
        new_name = f"{cls}_{i:03d}.wav"  # toujours 3 chiffres
        if old_name != new_name:
            print(f"Renaming {old_name} → {new_name}")
            os.rename(old_name, new_name)
        else:
            print(f"{old_name} already correct")
