# Norad: design

## Purpose

- **Aim:** a synchronized recording system to measure arousal state. Pupil size is the reference arousal measure.
- **Use:** a psychologist, as both operator and participant, tries tasks to choose one for a later study.
- **What it does:** records eye, nasal-breathing and heart signals in sync, with markers; shows them live; saves raw data.

## Devices and streams

All devices publish to [LSL](https://labstreaminglayer.org). Each sample is stamped with its measurement time on the device, mapped onto the LSL clock by the lowest-delay offset over the last 30 s. A missing device leaves its panels empty; everything else still works.

| LSL stream | Source | Rate | Channels |
|---|---|---|---|
| `norad_tobii` / `_imu` | Tobii Pro Glasses 2 (WiFi) | 50 / ~100 Hz | gaze x/y, pupil L/R (mm), gaze direction L/R; accelerometer, gyroscope |
| `norad_nasal` | XIAO nRF52840, 2 mics (USB) | ~840 Hz | mic1 (L), mic2 (R), temperature; raw ADC |
| `norad_polar_ecg` / `_acc` / `_hr` | Polar H10 (Bluetooth) | 130 / 200 Hz / ~1 Hz | ECG µV; ACC x/y/z mg; HR bpm, RR ms |
| `norad_markers` | keyboard, clicker, notes | event | label, text |
| `oddball_markers` | PsychoPy oddball task | event | `standard`, `deviant`, `response`, … |

- **Tobii:** every packet is read; one row per eye-tracking frame. Values the glasses mark invalid (blinks) are `nan`.
- **LSL traffic stays inside the computer** (`norad/lsl_api.cfg`), so switching to the Tobii WiFi cannot break connections.

## Architecture

```
Devices ──adapters──▶ LSL streams ──┬──▶ LabRecorder ──▶ recording.xdf
PsychoPy task ─────▶ LSL markers ───┤
                                    ├──▶ CSV recorder ──▶ raw/*.csv
                                    └──▶ live view ─────▶ browser (Socket.IO)
```

- One Python app (Flask + Socket.IO), local only. Polar Bluetooth runs in a child process.
- LabRecorder is controlled through its remote-control port (TCP 22345). The CSV recorder is independent of it.
- Live values (envelope, fixations) are display estimates; analysis is done offline from raw files.

## Workflow

1. **Connect devices**; first time, scan and pick the Polar H10; **Calibrate Tobii** with the card.
2. **Free session:** participant and task, **Start**. Space or clicker = mark, 1–9 = labelled marks, note + Enter. Esc twice stops.
3. **Oddball task:** one button; recording starts and stops with the task.
4. **Screens:** operator screen (browser) and participant screen (mid-grey with fixation cross; PsychoPy uses it full screen).

**Oddball:** 120 standard (1000 Hz) and 30 deviant (1500 Hz) tones, 100 ms, onset interval 1.5–2.5 s, no back-to-back deviants, SPACE for deviants, 10 s baseline. Tone markers carry the scheduled sound onset.

## Data

```
Results/YYYY-MM-DD_HHMM_<participant>_<task>/      (local only, git-ignored)
  recording.xdf     all LSL streams
  session.json      participant, task, streams, sample counts, software version, schema_version
  raw/              tobii.csv  tobii_imu.csv  nasal.csv  polar_ecg.csv  polar_acc.csv  polar_hr.csv
                    markers.csv  oddball_markers.csv
```

Every CSV starts with `t_lsl` (seconds, shared clock). Raw files are never modified.

## Next

| Part | Content |
|---|---|
| Analysis | Pupil: blink removal (Hershman 2018; Kret & Sjak-Shie 2019), gaps ≤ 250 ms interpolated, 4 Hz low-pass, baseline 500 ms before each marker (Mathôt 2018). Gaze: I-VT fixations at 30°/s. Breathing: 100 ms RMS envelope → breaths, rate, L/R balance. Heart: R-peaks → HR, HRV. Averages around markers. `norad analyze <folder>`. |
| Validation | Known-answer tests with synthetic signals; cross-check against NeuroKit2 on local recordings. |
| System check | Device rates, headphone leakage, paced-breathing calibration, pupil light reflex, gaze accuracy; optional sync check (3 taps on the glasses' nose bridge + 1 cough). Warns, never blocks. |
| Review | Table comparing recordings. |
