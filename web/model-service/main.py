"""
Workout analysis service — pure computation, no database.
Persistence is handled entirely by the Spring Boot backend.

Endpoints
---------
GET  /health                     — liveness probe
GET  /exercises                  — list supported exercises
POST /process                    — analyse an uploaded video file, return metrics
WS   /ws/live/{exercise_key}     — real-time frame-by-frame feedback

Run with:
    uvicorn main:app --host 0.0.0.0 --port 8081 --reload
"""

import os
import sys
import shutil
import tempfile
import time
import traceback
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

def _resolve_project_root() -> Path:
    """Find the repo root both locally and inside the Docker image.

    Local path:   repo/web/model-service/main.py -> repo
    Docker path:  /app/main.py with /app/taharrak copied beside it
    """
    here = Path(__file__).resolve().parent
    candidates = (here, here.parent.parent, Path.cwd())
    for candidate in candidates:
        if (candidate / "taharrak").is_dir():
            return candidate
    return here


PROJECT_ROOT = _resolve_project_root()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from taharrak.exercises import EXERCISES
from taharrak.eval import replay_video, _load_cfg, _ensure_model
from taharrak.tracker import RepTracker, OneEuroLandmarkSmoother
from taharrak.analysis import det_quality_ex, build_msgs

app = FastAPI(title="Workout Analysis Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_cfg = _load_cfg(None)


def _analysis_cfg() -> dict:
    cfg = dict(_cfg)
    target_fps = os.getenv("TAHARRAK_ANALYSIS_TARGET_FPS")
    max_width = os.getenv("TAHARRAK_ANALYSIS_MAX_WIDTH")
    if target_fps:
        try:
            cfg["analysis_target_fps"] = float(target_fps)
        except ValueError:
            pass
    if max_width:
        try:
            cfg["analysis_max_width"] = int(max_width)
        except ValueError:
            pass
    return cfg

# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
def on_startup() -> None:
    _ensure_model()


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/exercises")
def list_exercises() -> list:
    return [
        {"key": k, "name": ex.name, "bilateral": ex.bilateral}
        for k, ex in EXERCISES.items()
    ]


@app.post("/process")
async def process_video(
    video: UploadFile = File(...),
    exercise_key: str = Form(...),
) -> dict:
    if exercise_key not in EXERCISES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown exercise key '{exercise_key}'. Valid keys: {list(EXERCISES.keys())}",
        )

    tmp_dir = tempfile.mkdtemp()
    suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
    video_path = os.path.join(tmp_dir, f"upload{suffix}")

    try:
        with open(video_path, "wb") as f:
            shutil.copyfileobj(video.file, f)

        metrics = replay_video(video_path, exercise_key=exercise_key, cfg=_analysis_cfg())

        return {
            "success": True,
            "exercise_key": exercise_key,
            "exercise_name": EXERCISES[exercise_key].name,
            "reps_total": metrics.get("reps_total", 0),
            "reps_left": metrics.get("reps_left"),
            "reps_right": metrics.get("reps_right"),
            "signal_quality": round(float(metrics.get("signal_quality", 0)), 3),
            "dropout_rate": round(float(metrics.get("dropout_rate", 0)), 3),
            "mean_reliability": round(float(metrics.get("mean_reliability", 0)), 3),
            "unknown_rate": round(float(metrics.get("unknown_rate", 0)), 3),
            "aborted_reps": int(metrics.get("aborted_reps", 0)),
            "rejected_reps": int(metrics.get("rejected_reps", 0)),
            "frames_total": int(metrics.get("frames_total", 0)),
            "frames_detected": int(metrics.get("frames_detected", 0)),
            "fps_mean": round(float(metrics.get("fps_mean", 0)), 1),
        }

    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Real-time WebSocket session ───────────────────────────────────────────────

def _build_live_session(exercise_key: str) -> dict:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    exercise = EXERCISES[exercise_key]
    cfg = dict(_cfg)
    # The Angular client captures at ~12.5 fps (80 ms interval, one in-flight).
    # Setting the nominal filter frequency to match reduces One Euro Filter lag.
    # Override via TAHARRAK_LIVE_FPS env var if the client capture rate changes.
    try:
        cfg["camera_fps"] = float(os.getenv("TAHARRAK_LIVE_FPS", "15"))
    except ValueError:
        cfg["camera_fps"] = 15.0

    trackers = (
        [RepTracker("left", exercise, cfg), RepTracker("right", exercise, cfg)]
        if exercise.bilateral
        else [RepTracker("center", exercise, cfg)]
    )

    smoother = OneEuroLandmarkSmoother(
        num_landmarks=33,
        freq=30.0,
        min_cutoff=cfg.get("one_euro_min_cutoff", 1.5),
        beta=cfg.get("one_euro_beta", 0.007),
    )

    base_opts = mp_python.BaseOptions(model_asset_path="pose_landmarker_lite.task")
    options = vision.PoseLandmarkerOptions(
        base_options=base_opts,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.48,
        min_pose_presence_confidence=0.48,
        min_tracking_confidence=0.48,
        output_segmentation_masks=False,
    )

    return {
        "exercise": exercise,
        "trackers": trackers,
        "smoother": smoother,
        "landmarker": vision.PoseLandmarker.create_from_options(options),
        "cfg": cfg,
        "frames_total": 0,
        "frames_detected": 0,
        "reliability_sum": 0.0,
        "start_time": time.time(),
        "last_timestamp_ms": -1,
    }


def _processing_path_summary(trackers: list) -> tuple[str, list[str]]:
    paths = [getattr(tracker, "last_processing_path", "unknown") for tracker in trackers]
    unique = {path for path in paths if path}
    if len(unique) == 1:
        return paths[0], paths
    if not unique:
        return "unknown", paths
    return "mixed", paths


def _serialize_landmarks(landmarks) -> list[dict]:
    return [
        {
            "x": round(float(point.x), 6),
            "y": round(float(point.y), 6),
            "z": round(float(getattr(point, "z", 0.0)), 6),
            "visibility": round(float(getattr(point, "visibility", 0.0)), 6),
            "presence": round(float(getattr(point, "presence", 1.0)), 6),
        }
        for point in landmarks
    ]


def _process_landmarks(session: dict, landmarks, frame_size: tuple[int, int]) -> dict:
    exercise = session["exercise"]
    trackers = session["trackers"]
    smoother = session.get("smoother")
    cfg = session["cfg"]
    w, h = frame_size

    session["frames_total"] += 1
    session["frames_detected"] += 1

    # Rep logic benefits from smoothing, but overlay landmarks should remain raw
    # so the skeleton does not visibly trail behind the live camera body.
    lm_raw = landmarks
    lm = smoother.smooth(landmarks) if smoother is not None else landmarks

    from taharrak.analysis import joint_reliability

    key_idx = exercise.key_joints_right or exercise.joints_right
    if exercise.bilateral:
        key_idx = key_idx + (exercise.key_joints_left or exercise.joints_left)
    session["reliability_sum"] += sum(joint_reliability(lm[i]) for i in key_idx) / len(key_idx)

    l_q_raw, r_q_raw = det_quality_ex(lm, exercise, cfg)
    angles, swings, qualities = [], [], []

    if exercise.bilateral:
        l_q = trackers[0].update_quality(l_q_raw)
        qualities.append(l_q)
        if l_q != "LOST":
            a, b, c = exercise.joints_left
            ang, swinging, _, _ = trackers[0].update(
                lm[a], lm[b], lm[c], lm[exercise.swing_joint_left], w, h, landmarks=lm
            )
            angles.append(ang)
            swings.append(swinging)
        else:
            angles.append(None)
            swings.append(False)

        r_q = trackers[1].update_quality(r_q_raw)
        qualities.append(r_q)
        if r_q != "LOST":
            a, b, c = exercise.joints_right
            ang, swinging, _, _ = trackers[1].update(
                lm[a], lm[b], lm[c], lm[exercise.swing_joint_right], w, h, landmarks=lm
            )
            angles.append(ang)
            swings.append(swinging)
        else:
            angles.append(None)
            swings.append(False)
    else:
        r_q = trackers[0].update_quality(r_q_raw)
        qualities.append(r_q)
        if r_q != "LOST":
            a, b, c = exercise.joints_right
            ang, swinging, _, _ = trackers[0].update(
                lm[a], lm[b], lm[c], lm[exercise.swing_joint_right], w, h, landmarks=lm
            )
            angles.append(ang)
            swings.append(swinging)
        else:
            angles.append(None)
            swings.append(False)

    msgs = build_msgs(
        trackers=trackers, angles=angles, swings=swings,
        exercise=exercise, cfg=cfg, lang="en", qualities=qualities,
    )
    processing_path, processing_paths = _processing_path_summary(trackers)

    return {
        "detected": True,
        "reps_total": sum(tr.rep_count for tr in trackers),
        "reps_left": trackers[0].rep_count if exercise.bilateral else None,
        "reps_right": trackers[1].rep_count if exercise.bilateral else None,
        "quality": max(qualities, key=lambda q: {"GOOD": 2, "WEAK": 1, "LOST": 0}.get(q, 0)),
        "feedback": msgs[0][0].strip() if msgs else "",
        "severity": msgs[0][1] if msgs else "ok",
        "angles": [round(a, 1) if a is not None else None for a in angles],
        "processing_path": processing_path,
        "processing_paths": processing_paths,
        "phases": [
            (tracker.last_phase_validation.phase if tracker.last_phase_validation else None)
            for tracker in trackers
        ],
        "faults": [list(tracker.technique_state.get("faults", ())) for tracker in trackers],
        "suppressed_faults": [[
            evaluation.fault
            for evaluation in getattr(tracker, "last_fault_evaluations", ())
            if evaluation.suppressed
        ] for tracker in trackers],
        "landmarks": _serialize_landmarks(lm_raw),
    }


def _process_frame(session: dict, jpeg_bytes: bytes) -> dict:
    import mediapipe as mp

    started = time.time()
    landmarker = session["landmarker"]

    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"error": "could not decode frame"}

    h, w = bgr.shape[:2]
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    timestamp_ms = int((time.time() - session["start_time"]) * 1000)
    if timestamp_ms <= session["last_timestamp_ms"]:
        timestamp_ms = session["last_timestamp_ms"] + 1
    session["last_timestamp_ms"] = timestamp_ms
    result = landmarker.detect_for_video(mp_img, timestamp_ms)

    if not result.pose_landmarks:
        session["frames_total"] += 1
        for tr in session["trackers"]:
            tr.update_quality("LOST")
        return {
            "detected": False,
            "reps_total": sum(tr.rep_count for tr in session["trackers"]),
            "reps_left":  session["trackers"][0].rep_count if session["exercise"].bilateral else None,
            "reps_right": session["trackers"][1].rep_count if session["exercise"].bilateral else None,
            "quality": "LOST",
            "feedback": "Move into frame",
            "severity": "warning",
            "processing_path": "none",
            "processing_paths": [],
            "phases": [],
            "faults": [],
            "suppressed_faults": [],
            "landmarks": [],
            "server_processing_ms": round((time.time() - started) * 1000, 1),
        }
    feedback = _process_landmarks(session, result.pose_landmarks[0], (w, h))
    feedback["server_processing_ms"] = round((time.time() - started) * 1000, 1)
    return feedback


@app.websocket("/ws/live/{exercise_key}")
async def live_session(websocket: WebSocket, exercise_key: str) -> None:
    if exercise_key not in EXERCISES:
        await websocket.close(code=4000)
        return

    await websocket.accept()
    session = _build_live_session(exercise_key)

    try:
        while True:
            jpeg_bytes = await websocket.receive_bytes()
            feedback = _process_frame(session, jpeg_bytes)
            await websocket.send_json(feedback)

    except WebSocketDisconnect:
        pass
    except Exception:
        traceback.print_exc()
    finally:
        session["landmarker"].close()
