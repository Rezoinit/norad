import os
from pathlib import Path

__version__ = "0.2.0"

# Must be set before pylsl is first used (see lsl_api.cfg).
LSL_CONFIG = Path(__file__).with_name("lsl_api.cfg")
os.environ.setdefault("LSLAPICFG", str(LSL_CONFIG))
