import argparse
import sys
import uuid
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="DCEmapping API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSIONS: dict = {}
JOBS: dict = {}


class LoadRequest(BaseModel):
    input: str
    mask: Optional[str] = None
    out: Optional[str] = None
    dwi_mask: bool = False
    dwi_pattern: str = "*dwi*"
    dwi_threshold: float = 0.0


class RunRequest(BaseModel):
    session_id: str
    tr: float = 14.0
    slope_method: str = "linear_fit"
    smooth_sigma: float = 0.0
    smooth_window: int = 0
    spatial_smooth_sigma: float = 0.5
    onset_fallback: int = 2
    pattern: Optional[str] = None
    skip_first: bool = False
    skip_frames: int = 0
    resample: int = 1


@app.get("/api/status")
def status():
    return {"ok": True, "version": "1.0.0", "python": sys.version}


@app.post("/api/load")
def load(req: LoadRequest):
    input_path = Path(req.input)
    if not input_path.exists():
        raise HTTPException(404, f"Input not found: {req.input}")

    session_id = str(uuid.uuid4())[:8]

    if input_path.is_dir():
        from src.pipeline import _detect_dyn_series, _scan_dce_files
        detected_sd, detected_frames, excluded = _detect_dyn_series(input_path)
        if detected_frames:
            nifti_count = len(detected_frames)
            for tag, sd, count, _ in excluded:
                nifti_count += count
        else:
            candidates = sorted(input_path.glob("*.nii.gz")) + sorted(input_path.glob("*.nii"))
            nifti_count = 0
            for f in candidates:
                try:
                    import nibabel as nib
                    img = nib.load(str(f))
                    if img.ndim == 4:
                        nifti_count += 1
                except Exception:
                    pass
    else:
        nifti_count = 1

    SESSIONS[session_id] = {
        "input": str(input_path),
        "out_dir": str(req.out) if req.out else None,
        "mask": req.mask,
        "dwi_mask": req.dwi_mask,
        "dwi_pattern": req.dwi_pattern,
        "dwi_threshold": req.dwi_threshold,
        "nifti_count": nifti_count,
    }

    return {"session_id": session_id, "nifti_count": nifti_count}


@app.post("/api/run")
def run_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    job_id = str(uuid.uuid4())[:8]
    JOBS[job_id] = {"status": "queued", "progress_pct": 0, "outputs": [], "error": None}

    background_tasks.add_task(_run_job, job_id, session, req)
    return {"job_id": job_id}


@app.get("/api/run/{job_id}")
def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/nifti")
def get_nifti(path: str):
    p = Path(path)
    if not p.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(p), media_type="application/octet-stream", filename=p.name)


def _make_namespace(session, req):
    input_path = Path(session["input"])
    out_dir = Path(session["out_dir"]) if session["out_dir"] else None

    args_dict = {
        "input": str(input_path),
        "output_dir": str(out_dir) if out_dir else None,
        "tr": req.tr,
        "mask": session.get("mask"),
        "slope_method": req.slope_method,
        "smooth_sigma": req.smooth_sigma,
        "smooth_window": req.smooth_window,
        "spatial_smooth_sigma": req.spatial_smooth_sigma,
        "onset_fallback": req.onset_fallback,
        "pattern": req.pattern,
        "skip_first": req.skip_first,
        "skip_frames": req.skip_frames,
        "resample": req.resample,
        "yes": True,
        "dwi_mask": session.get("dwi_mask", False),
        "dwi_pattern": session.get("dwi_pattern", "*dwi*"),
        "dwi_threshold": session.get("dwi_threshold", 0.0),
    }
    return argparse.Namespace(**args_dict)


def _run_job(job_id, session, req):
    try:
        JOBS[job_id]["status"] = "running"
        JOBS[job_id]["progress_pct"] = 10

        from src.pipeline import run
        args = _make_namespace(session, req)
        run(args)

        input_path = Path(session["input"])
        if session.get("out_dir"):
            out_dir = Path(session["out_dir"])
        else:
            parent = input_path if input_path.is_dir() else input_path.parent
            out_dir = parent / "DCEmapping_output"

        outputs = sorted(str(f) for f in out_dir.glob("*.nii.gz")) if out_dir.exists() else []
        JOBS[job_id]["outputs"] = outputs
        JOBS[job_id]["progress_pct"] = 100
        JOBS[job_id]["status"] = "done"

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)
