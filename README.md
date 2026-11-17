# Norad

Records eye tracking, nasal breathing and heart signals in sync, with markers, to measure arousal state.

## [⬇ Download for Mac](https://github.com/Rezoinit/norad/archive/refs/heads/main.zip)

**Install (once, ~15 min)**
1. Download, unzip, and move the `norad-main` folder to **Documents** (keep it there).
2. Right-click **Install Norad** → **Open** → **Open**. Enter your Mac password if asked.
3. When it says *Done*, close the window. **Start Norad** and **Norad Results** are now on your Desktop.

**Run**
1. Wet the Polar H10 electrodes and put it on. Plug in the nasal sensor. Join the Tobii WiFi.
2. Double-click **Start Norad**. The browser opens; allow Bluetooth when macOS asks.
3. **Connect devices**. First time only: **Scan** and pick your Polar H10.
4. **Calibrate Tobii**: hold the card ~1 m in front, look at its centre, click.
5. **Open participant screen** and move it to the second monitor (double-click it for full screen).
6. Enter participant and task → **Start**. Markers: **Space** or clicker = mark, **1–9** = your labels, note + **Enter**. **Esc** twice stops.

**Oddball task:** button **Oddball task (5 min)**. Low (1000 Hz) and high (1500 Hz) tones; press SPACE for high tones. Recording starts and stops with the task. Use **wired** headphones (Bluetooth adds ~150 ms of variable delay).

## Devices

| Device | What it gives | Connection |
|---|---|---|
| Tobii Pro Glasses 2 | gaze, pupil L/R (mm), head motion, scene camera | Tobii WiFi |
| Nasal sensor (XIAO nRF52840, 2 mics) | left/right nasal airflow sound | USB |
| Polar H10 | ECG, heart rate + RR, chest motion | Bluetooth |

All devices publish to [LSL](https://labstreaminglayer.org); a missing device is simply left out.

## Data

One folder per recording, in **Norad Results** on the Desktop (stays on your Mac; never uploaded):

```
YYYY-MM-DD_HHMM_<participant>_<task>/
  recording.xdf     all streams (LabRecorder)
  session.json      participant, task, streams, sample counts, software version
  raw/              tobii.csv  tobii_imu.csv  nasal.csv  polar_ecg.csv  polar_acc.csv  polar_hr.csv
                    markers.csv  oddball_markers.csv
```

- Every CSV starts with `t_lsl`: seconds on the shared clock. Device samples carry their measurement time; markers and Polar heart-rate reports their arrival time.
- Raw files are never modified. Missing pupil = `nan` (blink or eye lost).
- App messages go to `logs/norad.log` (replaced at each start).

## More

- Design and next steps: [docs/DESIGN.md](docs/DESIGN.md)
- Tests: `.venv/bin/pip install -e ".[dev]"` then `.venv/bin/pytest`
