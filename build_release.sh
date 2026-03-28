#!/bin/bash
pyinstaller \
  --clean \
  --onefile \
  --noconsole \
  --name="TrackLyrics-V1.0.0" \
  --icon=../assets/icon.ico \
  --add-data "../assets;assets" \
  --distpath release \
  --workpath build \
  --specpath release \
  src/main.py