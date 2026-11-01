import numpy as np
from src.tic_derivatives import (
    compute_tmax_idx,
    compute_onset,
    compute_slopes,
)
from src.maps import compute_all_maps


def _piecewise_linear_tic(T=20):
    t = np.arange(T, dtype=float)
    S = np.zeros(T)
    rise_start, rise_end = 3, 12
    slope_in = 5.0
    S[rise_start:rise_end] = slope_in * (t[rise_start:rise_end] - rise_start)
    S[rise_end:] = S[rise_end - 1] - 1.0 * (t[rise_end:] - rise_end)
    S[S < 0] = 0
    return S, rise_start, rise_end, slope_in


def test_tmax_idx():
    S, _, peak_idx, _ = _piecewise_linear_tic()
    tmax = compute_tmax_idx(S[np.newaxis, :])
    assert tmax[0] == peak_idx - 1, f"Expected {peak_idx - 1}, got {tmax[0]}"


def test_washin_slope_two_point():
    S, onset, peak, slope_in = _piecewise_linear_tic()
    data_2d = S[np.newaxis, :]
    tmax = compute_tmax_idx(data_2d)
    onset_arr = np.array([onset], dtype=np.int32)
    wi, wo = compute_slopes(data_2d, onset_arr, tmax, method="two_point")
    assert np.abs(wi[0] - slope_in) < 1e-6, f"Expected {slope_in}, got {wi[0]}"


def test_washin_slope_linear_fit():
    S, onset, peak, slope_in = _piecewise_linear_tic()
    data_2d = S[np.newaxis, :]
    tmax = compute_tmax_idx(data_2d)
    onset_arr = np.array([onset], dtype=np.int32)
    wi, wo = compute_slopes(data_2d, onset_arr, tmax, method="linear_fit")
    assert np.abs(wi[0] - slope_in) < 0.5, f"Expected ~{slope_in}, got {wi[0]}"


def test_max_pct_enhancement():
    data_4d = np.zeros((2, 2, 1, 10), dtype=np.float64)
    data_4d[0, 0, 0, :] = [100, 110, 130, 160, 200, 190, 170, 150, 130, 110]
    maps = compute_all_maps(data_4d, tr=1.0, mask_3d=None, slope_method="linear_fit")
    pct = maps["maxpct_enhancement"]
    expected = (200 - 100) / 100 * 100
    assert np.abs(pct[0, 0, 0] - expected) < 1e-4, f"Expected {expected}, got {pct[0,0,0]}"


def test_zero_voxel():
    data_4d = np.zeros((2, 2, 1, 10), dtype=np.float64)
    maps = compute_all_maps(data_4d, tr=1.0, mask_3d=None, slope_method="linear_fit")
    for name, vol in maps.items():
        assert np.all(vol == 0), f"{name} should be all zeros for zero input"


def test_no_washout():
    N, T = 1, 15
    data_2d = np.arange(T, dtype=float).reshape(N, T)
    S = data_2d[0]
    tmax = compute_tmax_idx(data_2d)
    assert tmax[0] == T - 1
    onset_arr = compute_onset(data_2d, tmax, fallback_idx=2)
    wi, wo = compute_slopes(data_2d, onset_arr, tmax, method="linear_fit")
    assert np.abs(wo[0]) < 1e-10, f"Wash-out should be ~0 for monotonic, got {wo[0]}"


def test_mask_support():
    data_4d = np.random.rand(4, 4, 2, 8)
    mask = np.zeros((4, 4, 2), dtype=bool)
    mask[1:3, 1:3, :] = True
    maps = compute_all_maps(data_4d, tr=2.0, mask_3d=mask, slope_method="linear_fit")
    for name, vol in maps.items():
        assert vol.shape == (4, 4, 2), f"{name} shape mismatch"
        assert np.all(vol[~mask] == 0), f"{name} should be zero outside mask"
