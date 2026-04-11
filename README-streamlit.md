# Taharrak — Streamlit Web App

Thin browser wrapper around the main Taharrak runtime.

It reuses the same core exercise registry, rep trackers, trust gate, tracking
guard, correction engine, and feedback selection used by the desktop app.

---

## Run locally

```bash
pip install -r requirements-streamlit.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

On first run it downloads the MediaPipe pose model (`pose_landmarker_lite.task`)
automatically if it is not already present.

For Streamlit Community Cloud deployment:

- add root-level `packages.txt` with `libgl1`
- use Python `3.12` in Streamlit Cloud Advanced settings

---

## What is included

- real webcam streaming through `streamlit-webrtc`
- the same `EXERCISES` registry used by the desktop app
- `RepTracker` counting and scoring
- `LiveTrustGate` and `TrackingGuard`
- `CorrectionEngine` post-rep summaries
- `build_msgs()` one-cue coaching
- optional segmentation toggle
- optional diagnostics panel

---

## What is intentionally omitted

- desktop OpenCV state machine screens (exercise select, weight input, rest screen)
- TTS voice playback
- SQLite history and CSV export
- the full desktop HUD layout

The web version is intentionally simpler: select an exercise, start the stream,
watch the live cue, and review the running summary.

---

## Using the controls

Sidebar controls:

- **Exercise**: pick the movement to track
- **Language**: English or Arabic
- **Segmentation**: apply the same background-mask effect used by the desktop app
- **Diagnostics**: show FPS, frame timing, quality, trust, and recovery details

Important:

- If you change **exercise**, **language**, or **segmentation** while the stream
  is running, the app will warn you to **Stop** and **Start** again.
- Diagnostics are UI-only and can be toggled without restarting.

---

## Diagnostics and segmentation

### Segmentation

Segmentation is configurable from the Streamlit sidebar and is passed directly
into the MediaPipe landmarker at processor startup.

- Default: follows `config.json` → `segmentation_enabled`
- Change requires stream restart

### Diagnostics

When enabled, the diagnostics panel shows:

- current FPS
- moving-average frame time (`dt`)
- frame-time jitter
- current quality state
- trust state (`render`, `count`, `coach`)
- recovery / weak / lost fractions
- segmentation state and runtime mode

Diagnostics are hidden by default so the normal UI stays clean.

---

## MediaPipe runtime mode

The Streamlit app uses **MediaPipe VIDEO mode** with strictly monotonic
timestamps.

Why:

- it better matches the desktop Taharrak runtime
- it preserves tracker continuity frame-to-frame
- it avoids treating the webcam stream as isolated still images

Implementation note:

- `app.py` derives a monotonic millisecond timestamp for each frame
- if the incoming frame timestamp stalls or repeats, it is bumped forward by 1 ms
  so MediaPipe still receives a valid increasing sequence

---

## Validation tips

- use good lighting and keep the full working side in frame
- for bilateral exercises, show both arms clearly before expecting comparison cues
- try segmentation on and off on the same setup to compare visual quality and latency
- turn diagnostics on if counts or coaching feel delayed or inconsistent

---

## WebRTC / NAT note

The app uses public Google STUN servers by default.

If the webcam feed cannot connect behind a strict firewall or symmetric NAT,
you may need to add a TURN server in `_RTC_CONFIG` inside [app.py](./app.py).
