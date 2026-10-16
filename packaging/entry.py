"""Entry point of the installed program (PyInstaller): the same as `vision-station`."""

import multiprocessing
import sys

from vision_station.runtime import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
