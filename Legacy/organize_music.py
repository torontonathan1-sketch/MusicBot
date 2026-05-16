import os, shutil
from mutagen.easyid3 import EasyID3

source = r'f:\Music'
dest   = r'f:\Music 2026'
moved = skipped = errors = 0

def sanitize(name):
    bad_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for c in bad_chars:
        name = name.replace(c, '_')
    name = name.replace('...', '___').replace('..', '__')
    return name.strip('. ')

if not os.path.exists(dest):
    os.makedirs(dest)

print(f"Scanning {source}...")

for root, dirs, files in os.walk(source):
    for file in files:
        if not file.lower().endswith('.mp3'):
            continue
        src_path = os.path.join(root, file)
        try:
            tags = EasyID3(src_path)
            artist = sanitize(tags.get('artist', ['Unknown Artist'])[0])
            album  = sanitize(tags.get('album',  ['Unknown Album'])[0])
        except Exception:
            artist, album = 'Unknown Artist', 'Unknown Album'
        
        target_dir  = os.path.join(dest, artist, album)
        target_path = os.path.join(target_dir, file)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        if os.path.exists(target_path):
            skipped += 1
            continue
        try:
            shutil.copy2(src_path, target_path)
            print(f'MOVED: {artist}/{album}/{file}')
            moved += 1
        except Exception as e:
            print(f'ERROR: {src_path} -> {e}')
            errors += 1

print(f'\nDone! Moved: {moved}  Skipped: {skipped}  Errors: {errors}')
