import os
import sys
from . import cli

if sys.platform == "darwin":
    # MacOS BigSur
    os.environ["QT_MAC_WANTS_LAYER"] = "1"

sys.exit(cli.main())
