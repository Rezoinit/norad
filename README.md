# Norad

Records eye tracking, nasal breathing and heart signals in sync, with markers, to measure arousal state.

## [⬇ Download for Mac](https://github.com/Rezoinit/norad/archive/refs/heads/main.zip)

**Install (once, ~15 min)**
1. Download, unzip, and move the `norad-main` folder to **Documents** (keep it there).
2. Double-click **Install Norad**. macOS warns it can't verify it: click **Done** (not *Move to Bin*).
3. Open **System Settings → Privacy & Security**, scroll down, click **Open Anyway** next to *"Install Norad.command" was blocked*, enter your Mac password, then **Open**.
4. When it says *Done*, close the window. **Start Norad** and **Norad Results** are now on your Desktop.

*Or, in Terminal:* `xattr -dr com.apple.quarantine ~/Documents/norad-main && open ~/Documents/norad-main/"Install Norad.command"`

**Run**
1. Wet the Polar H10 electrodes and put it on. Plug in the nasal sensor. Join the Tobii WiFi.
2. Double-click **Start Norad**. The browser opens; allow Bluetooth when macOS asks.
3. **Connect devices**. First time only: **Scan** and pick your Polar H10.
4. **Calibrate Tobii**: hold the card ~1 m in front, look at its centre, click.
5. **Open participant screen** and move it to the second monitor (double-click it for full screen).
6. Enter participant and task → **Start**. Markers: **Space** or clicker = mark, **1–9** = your labels, note + **Enter**. **Esc** twice stops.

**Tasks** (PsychoPy, on the participant screen). Each button starts a recording, runs the task and stops when it ends. Use **wired** headphones (Bluetooth adds ~150 ms of variable delay).

| Button | What happens |
|---|---|
| Oddball (5 min) | Low (1000 Hz) and high (1500 Hz) tones; press SPACE for high tones. |
| Oddball graded (12 min) | Three blocks in random order, high tone 1500 / 1100 / 1030 Hz (easy / medium / hard), 30 s rest between. |
| Digit span (4 min) | Hear 3 digits (one per second), type them back, Enter. 16 trials. |
| Digit span graded (8 min) | 3 / 5 / 7 digits (easy / medium / hard), 8 trials each, mixed at random. |

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
                    markers.csv  oddball_markers.csv  digitspan_markers.csv
```

- Every CSV starts with `t_lsl`: seconds on the shared clock. Device samples carry their measurement time; markers and Polar heart-rate reports their arrival time.
- Raw files are never modified. Missing pupil = `nan` (blink or eye lost).
- App messages go to `logs/norad.log` (replaced at each start).

## More

- Next development stage: an assessment battery to build a physiological baseline profile before tasks.
- Design and next steps: [docs/DESIGN.md](docs/DESIGN.md)
- Tests: `.venv/bin/pip install -e ".[dev]"` then `.venv/bin/pytest`
