import numpy as np

from .tic_derivatives import (
    compute_tmax_idx,
    compute_onset,
    compute_slopes,
)


def _reshape_4d_to_2d(data_4d, mask_3d=None):
    x, y, z, t = data_4d.shape
    if mask_3d is not None:
        valid = mask_3d > 0
        flat = data_4d[valid, :]
        return flat, valid
    flat = data_4d.reshape(-1, t)
    return flat, None


def _reshape_2d_to_4d(map_1d, orig_shape_3d, valid_mask):
    x, y, z = orig_shape_3d
    out = np.zeros((x, y, z), dtype=np.float32)
    out[valid_mask] = map_1d.astype(np.float32)
    return out


def compute_all_maps(data_4d, tr=1.0, mask_3d=None, slope_method="linear_fit",
                     onset_fallback_idx=2, s0_volume=None, frame_times=None):
    orig_shape_3d = data_4d.shape[:3]
    data_2d, valid_mask = _reshape_4d_to_2d(data_4d, mask_3d)

    T = data_2d.shape[1]

    # Build per-frame timing: intervals[i] = time between frame i and frame i+1
    if frame_times is not None and len(frame_times) >= T:
        frame_intervals = np.diff(frame_times[:T]).astype(np.float64)
        frame_intervals = np.maximum(frame_intervals, 1e-6)
        # Absolute time of each frame relative to first
        abs_times = (frame_times[:T] - frame_times[0]).astype(np.float64)
    else:
        frame_intervals = np.full(T - 1, tr, dtype=np.float64)
        abs_times = np.arange(T, dtype=np.float64) * tr

    tmax_idx = compute_tmax_idx(data_2d)
    tmax_sec = abs_times[tmax_idx]

    onset_idx = compute_onset(data_2d, tmax_idx, onset_fallback_idx)

    segment_washin, washout = compute_slopes(
        data_2d, onset_idx, tmax_idx, method=slope_method,
        frame_times=abs_times,
    )

    # Washin = max positive frame-to-frame upslope (signal/sec)
    diffs = np.diff(data_2d, axis=1)
    safe_intervals = np.where(frame_intervals > 1e-6, frame_intervals, 1e-6)
    # Only keep positive diffs (actual enhancement)
    pos_diffs = np.where(diffs > 0, diffs, 0.0)
    # Per-voxel: find the interval where the max positive diff occurs
    max_diff_idx = np.argmax(pos_diffs, axis=1)
    N_vox = data_2d.shape[0]
    per_voxel_intervals = safe_intervals[max_diff_idx]
    per_voxel_max_diff = pos_diffs[np.arange(N_vox), max_diff_idx]
    washin = (per_voxel_max_diff / per_voxel_intervals).astype(np.float32)
    upslope_idx = np.argmax(diffs, axis=1).astype(np.int16)

    # S0: use pre-computed volume (before skip) or compute from first 3 frames
    if s0_volume is not None:
        if valid_mask is not None:
            s0 = s0_volume[valid_mask].astype(np.float64)
        else:
            s0 = s0_volume.ravel().astype(np.float64)
    else:
        n_base = min(3, data_2d.shape[1])
        s0 = np.min(data_2d[:, :n_base], axis=1)

    s0_safe = np.where(np.abs(s0) < 1e-12, np.nan, s0)
    peak = np.max(data_2d, axis=1)
    max_pct = (peak - s0) / s0_safe * 100.0
    max_pct = np.nan_to_num(max_pct, nan=0.0, posinf=0.0, neginf=0.0)

    maps_1d = {
        "tmax": tmax_sec,
        "washin": washin,
        "segment_washin": segment_washin,
        "washout": washout,
        "upslope_index": upslope_idx,
        "maxpct_enhancement": max_pct,
    }

    if valid_mask is not None:
        maps_3d = {}
        for name, arr in maps_1d.items():
            maps_3d[name] = _reshape_2d_to_4d(arr, orig_shape_3d, valid_mask)
        return maps_3d

    x, y, z = orig_shape_3d
    maps_3d = {}
    for name, arr in maps_1d.items():
        if name == "upslope_index":
            maps_3d[name] = arr.reshape(x, y, z).astype(np.int16)
        else:
            maps_3d[name] = arr.reshape(x, y, z).astype(np.float32)
    return maps_3d
