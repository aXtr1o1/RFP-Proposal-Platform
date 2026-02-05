import shutil
import os
from pathlib import Path

# Use absolute paths or be very careful with CWD
cw = Path.cwd()
src = cw / "apps/app/templates/arweqah/Background"
dst = cw / "apps/app/templates/arweqah_native/Background"

print(f"Copying from {src} to {dst}...")

if not src.exists():
    print(f"Source does not exist: {src.resolve()}")
    exit(1)

if dst.exists():
    shutil.rmtree(dst)

shutil.copytree(src, dst)
print("Copy complete.")
