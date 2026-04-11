# Taharrak — Streamlit Web App

Real-time AI fitness coach running entirely in the browser.  
No installation required for end users — just open the URL and allow camera access.

---

## Run locally

```bash
# 1. Install web dependencies (one-time)
pip install -r requirements-streamlit.txt

# 2. Launch
streamlit run app.py
```

The app opens at `http://localhost:8501`.  
On first run it downloads the MediaPipe pose model (~6 MB) automatically.

---

## Deploy free on Streamlit Cloud

1. **Push this repo to GitHub** (public or private).

2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign in with GitHub.

3. Click **New app** and fill in:
   | Field | Value |
   |---|---|
   | Repository | `your-username/your-repo` |
   | Branch | `main` |
   | Main file path | `app.py` |

4. Under **Advanced settings → Python packages**, point to `requirements-streamlit.txt`  
   (or rename it to `requirements.txt` if you're deploying the web version only).

5. Click **Deploy**.  Streamlit Cloud handles the build and gives you a public URL.

> **Note:** Streamlit Cloud runs on Linux servers.  
> `opencv-python-headless` is required instead of `opencv-python` in that environment.

---

## What the web version omits (vs. the CLI app)

| Feature | CLI (`bicep_curl_counter.py`) | Web (`app.py`) |
|---|---|---|
| TTS voice feedback | ✓ | — (browser audio isn't reliable cross-platform) |
| SQLite session history | ✓ | — |
| CSV export | ✓ | — |
| Arabic PIL rendering | ✓ | — (text appears as Latin fallback if `arabic-reshaper` absent) |
| Background segmentation | ✓ | — (saves CPU; can be added later) |
| State machine (sets / rest / summary) | ✓ | — (simplified: select → stream → stop) |

All **form detection, rep counting, CorrectionEngine, and one-cue coaching** are identical  
to the CLI version — same `taharrak/` package, same `config.json` thresholds.

---

## WebRTC / NAT notes

The app uses three public Google STUN servers for NAT traversal:

```
stun:stun.l.google.com:19302
stun:stun1.l.google.com:19302
stun:stun2.l.google.com:19302
```

STUN works for most home and office networks.  
If the webcam feed fails to connect (common behind symmetric NAT or strict firewalls),  
you need a TURN relay server.  Add it to `_RTC_CONFIG` in `app.py`:

```python
_RTC_CONFIG = RTCConfiguration({
    "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
        {
            "urls":       ["turn:your-turn-server:3478"],
            "username":   "user",
            "credential": "password",
        },
    ]
})
```

Free TURN services: [Metered](https://www.metered.ca/tools/openrelay/) · [Xirsys](https://xirsys.com) (free tier).
