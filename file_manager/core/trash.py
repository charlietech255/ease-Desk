import os
import shutil
import datetime
from pathlib import Path

TRASH_DIR = Path.home() / ".local" / "share" / "Trash"
FILES_DIR = TRASH_DIR / "files"
INFO_DIR = TRASH_DIR / "info"

def ensure_trash_dirs():
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    INFO_DIR.mkdir(parents=True, exist_ok=True)

def send_to_trash(original_path: str):
    ensure_trash_dirs()
    path = Path(original_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"No such file or directory: {original_path}")
        
    filename = path.name
    # Handle duplicates
    dest_file = FILES_DIR / filename
    i = 1
    while dest_file.exists() or (INFO_DIR / f"{filename}.trashinfo").exists():
        filename = f"{path.name} {i}"
        dest_file = FILES_DIR / filename
        i += 1
        
    info_file = INFO_DIR / f"{filename}.trashinfo"
    now = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    with open(info_file, "w") as f:
        f.write("[Trash Info]\n")
        f.write(f"Path={path}\n")
        f.write(f"DeletionDate={now}\n")
        
    shutil.move(str(path), str(dest_file))

def list_trash():
    ensure_trash_dirs()
    items = []
    for info_file in INFO_DIR.glob("*.trashinfo"):
        filename = info_file.name[:-10] # remove .trashinfo
        dest_file = FILES_DIR / filename
        if not dest_file.exists():
            continue
        original_path = ""
        deletion_date = ""
        with open(info_file, "r") as f:
            for line in f:
                if line.startswith("Path="):
                    original_path = line[5:].strip()
                elif line.startswith("DeletionDate="):
                    deletion_date = line[13:].strip()
        items.append({
            "name": filename,
            "original_path": original_path,
            "deletion_date": deletion_date,
            "trash_path": str(dest_file),
            "info_path": str(info_file)
        })
    return items

def restore_trash(filename: str):
    ensure_trash_dirs()
    info_file = INFO_DIR / f"{filename}.trashinfo"
    dest_file = FILES_DIR / filename
    if not info_file.exists() or not dest_file.exists():
        raise FileNotFoundError("Item not found in trash")
        
    original_path = None
    with open(info_file, "r") as f:
        for line in f:
            if line.startswith("Path="):
                original_path = line[5:].strip()
                break
                
    if not original_path:
        raise ValueError("Invalid trashinfo")
        
    target_path = Path(original_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    shutil.move(str(dest_file), str(target_path))
    info_file.unlink()

def empty_trash():
    ensure_trash_dirs()
    shutil.rmtree(FILES_DIR)
    shutil.rmtree(INFO_DIR)
    ensure_trash_dirs()

def delete_permanently(filename: str):
    ensure_trash_dirs()
    info_file = INFO_DIR / f"{filename}.trashinfo"
    dest_file = FILES_DIR / filename
    if dest_file.exists():
        if dest_file.is_dir():
            shutil.rmtree(dest_file)
        else:
            dest_file.unlink()
    if info_file.exists():
        info_file.unlink()
