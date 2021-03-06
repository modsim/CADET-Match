import subprocess
import sys
from pathlib import Path
import shutil

def clear():
    for path in sorted(Path(sys.argv[1]).resolve().rglob("results")):
        print(path)
        shutil.rmtree(path)

if __name__ == "__main__":
    clear()