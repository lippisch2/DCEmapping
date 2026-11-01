import numpy as np
from scipy.ndimage import gaussian_filter


def apply_mask(data_4d, mask_3d):
    masked = data_4d * mask_3d[..., np.newaxis].astype(data_4d.dtype)
    return masked


def savgol_temporal(data_4d, window_length=5, polyorder=2):
    from scipy.signal import savgol_filter

    x, y, z, t = data_4d.shape
    flat = data_4d.reshape(-1, t)
    n_voxels = flat.shape[0]
    smoothed = np.empty_like(flat)

    chunk = 100000
    for start in range(0, n_voxels, chunk):
        end = min(start + chunk, n_voxels)
        smoothed[start:end] = savgol_filter(flat[start:end], window_length, polyorder, axis=1)
        print(f"    Smoothed {end:,} / {n_voxels:,} voxels")

    return smoothed.reshape(x, y, z, t)


def check_motion(data_4d, outlier_factor=3.0):
    x, y, z, t = data_4d.shape
    n_voxels = x * y * z

    if n_voxels > 50000:
        rng = np.random.default_rng(0)
        mask = np.zeros(n_voxels, dtype=bool)
        mask[rng.choice(n_voxels, 50000, replace=False)] = True
        flat_sample = data_4d.reshape(-1, t)[mask]
    else:
        flat_sample = data_4d.reshape(-1, t)

    diffs = np.abs(np.diff(flat_sample, axis=1))
    per_frame = np.median(diffs, axis=0)
    median_change = np.median(per_frame)
    flagged = np.where(per_frame > outlier_factor * median_change)[0]

    if len(flagged):
        frame_labels = ", ".join(
            f"{f}→{f+1}" for f in flagged
        )
        print(f"  Motion warning: large change at frame pair(s) {frame_labels}")
        print(f"    (median frame change={median_change:.4f}, outlier threshold={outlier_factor * median_change:.4f})")
