import numpy as np


def compute_tmax_idx(data_2d):
    return np.argmax(data_2d, axis=1).astype(np.int32)


def compute_onset(data_2d, tmax_idx, fallback_idx=2):
    N, T = data_2d.shape
    dS = np.diff(data_2d, n=1, axis=1)
    d2S = np.diff(dS, n=1, axis=1)
    d2S_pad = np.pad(d2S, ((0, 0), (1, 1)), mode="edge")
    onset_raw = np.argmax(d2S_pad, axis=1)
    onset = np.where(onset_raw > tmax_idx, tmax_idx, onset_raw)
    onset = np.clip(onset, fallback_idx, T - 1)
    return onset.astype(np.int32)


def _segment_slopes_vectorized(data_2d, start_idx, end_idx, frame_times=None):
    N, T = data_2d.shape
    L = end_idx - start_idx
    valid = L > 1
    slope = np.zeros(N, dtype=np.float64)

    if not np.any(valid):
        return slope

    if frame_times is not None:
        x_vals = frame_times[:T].astype(np.float64)
    else:
        x_vals = np.arange(T, dtype=np.float64)

    x2 = x_vals * x_vals

    # Cumulative sums for y, x*y, x, x^2
    cum_y = np.zeros((N, T + 1), dtype=np.float64)
    cum_y[:, 1:] = np.cumsum(data_2d, axis=1)

    cum_xy = np.zeros((N, T + 1), dtype=np.float64)
    cum_xy[:, 1:] = np.cumsum(x_vals[np.newaxis, :] * data_2d, axis=1)

    # Precompute cumulative sums of x and x^2 (same for all voxels)
    cum_x = np.zeros(T + 1, dtype=np.float64)
    cum_x[1:] = np.cumsum(x_vals)
    cum_x2 = np.zeros(T + 1, dtype=np.float64)
    cum_x2[1:] = np.cumsum(x2)

    s = start_idx[valid]
    e = end_idx[valid]
    n = (e - s).astype(np.float64)

    sum_y = cum_y[valid, e] - cum_y[valid, s]
    sum_xy = cum_xy[valid, e] - cum_xy[valid, s]
    sum_x = cum_x[e] - cum_x[s]
    sum_x2 = cum_x2[e] - cum_x2[s]

    denom = n * sum_x2 - sum_x * sum_x
    numer = n * sum_xy - sum_x * sum_y

    mask = denom > 1e-12
    result = np.where(mask, numer / denom, 0.0)
    slope[valid] = result
    return slope


def _segment_quadratic_batch(data_2d, start_idx, end_idx, frame_times=None):
    N, T = data_2d.shape
    L_arr = (end_idx - start_idx).astype(np.int32)
    valid = L_arr > 2

    slope_start = np.zeros(N, dtype=np.float64)

    if not np.any(valid):
        return slope_start

    from collections import defaultdict
    pairs = defaultdict(list)
    for i in np.where(valid)[0]:
        pairs[(int(start_idx[i]), int(end_idx[i]))].append(i)

    for (s, e), idx_list in pairs.items():
        L = e - s
        if frame_times is not None:
            t_loc = frame_times[s:e].astype(np.float64)
        else:
            t_loc = np.arange(L, dtype=np.float64)
        X = np.column_stack([t_loc ** 2, t_loc, np.ones(L)])
        XtX_inv_Xt = np.linalg.pinv(X)

        seg = data_2d[idx_list, s:e]
        coeff = seg @ XtX_inv_Xt.T
        slope_start[idx_list] = coeff[:, 1]

    return slope_start


def _compute_post_max_min_idx(data_2d, tmax_idx):
    N, T = data_2d.shape
    post_max_min = tmax_idx.copy()
    for t in range(T):
        mask = (tmax_idx == t) & (t < T - 1)
        if not np.any(mask):
            continue
        segment = data_2d[mask, t:]
        rel_min = np.argmin(segment, axis=1)
        post_max_min[mask] = t + rel_min
    return post_max_min.astype(np.int32)


def compute_slopes(data_2d, onset_idx, tmax_idx, method="linear_fit", frame_times=None):
    N = data_2d.shape[0]
    T = data_2d.shape[1]
    tmax_int = tmax_idx.astype(np.int32)
    onset_int = onset_idx.astype(np.int32)
    wo_end = _compute_post_max_min_idx(data_2d, tmax_int)
    wo_valid = wo_end > tmax_int

    if method == "two_point":
        washin_slope = np.zeros(N, dtype=np.float64)
        washout_slope = np.zeros(N, dtype=np.float64)
        wi_valid = tmax_int > onset_int

        if frame_times is not None:
            abs_t = frame_times[:T].astype(np.float64)
        else:
            abs_t = np.arange(T, dtype=np.float64)

        if np.any(wi_valid):
            dt = abs_t[tmax_int[wi_valid]] - abs_t[onset_int[wi_valid]]
            dt = np.maximum(dt, 1e-6)
            washin_slope[wi_valid] = (
                data_2d[wi_valid, tmax_int[wi_valid]]
                - data_2d[wi_valid, onset_int[wi_valid]]
            ) / dt
        if np.any(wo_valid):
            dt = abs_t[wo_end[wo_valid]] - abs_t[tmax_int[wo_valid]]
            dt = np.maximum(dt, 1e-6)
            washout_slope[wo_valid] = (
                data_2d[wo_valid, wo_end[wo_valid]]
                - data_2d[wo_valid, tmax_int[wo_valid]]
            ) / dt
        washout_slope = np.minimum(washout_slope, 0.0)
        return washin_slope, washout_slope

    if method == "quadratic":
        washin = _segment_quadratic_batch(data_2d, onset_int, tmax_int + 1, frame_times)
        washout = _segment_quadratic_batch(data_2d, tmax_int, wo_end + 1, frame_times)
        washout = np.minimum(washout, 0.0)
        return washin, washout

    washin = _segment_slopes_vectorized(
        data_2d, onset_int, tmax_int + 1, frame_times
    )
    washout = _segment_slopes_vectorized(data_2d, tmax_int, wo_end + 1, frame_times)
    washout = np.minimum(washout, 0.0)
    return washin, washout


def compute_instantaneous_slope(data_2d):
    return np.diff(data_2d, n=1, axis=1)
