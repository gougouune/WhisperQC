#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Point d'entrée de WhisperQC."""
import sys

if __name__ == "__main__":
    if "--selftest" in sys.argv:
        from whisperqc.selftest import main
        sys.exit(main())
    from whisperqc.gui import run
    run()
