import numpy as np
from src.maps import compute_all_maps


def test_tmax_seconds():
    data_4d = np.zeros((3, 3, 1, 20), dtype=np.float64)
    data_4d[:, :, 0, 10] = 100.0
    tr = 3.5
    maps = compute_all_maps(data_4d, tr=tr, mask_3d=None, slope_method="linear_fit")
    expected = 10.0 * tr
    assert np.allclose(maps["tmax"], expected), f"Expected {expected}, got {maps['tmax']}"


def test_upslope_index_map():
    np.random.seed(42)
    data_4d = np.random.rand(5, 5, 3, 12)
    maps = compute_all_maps(data_4d, tr=1.0, mask_3d=None, slope_method="linear_fit")
    idx_map = maps["upslope_index"]
    assert idx_map.dtype == np.int16
    flat = data_4d.reshape(-1, 12)
    diffs = np.diff(flat, axis=1)
    expected_idx = np.argmax(diffs, axis=1).reshape(5, 5, 3).astype(np.int16)
    assert np.array_equal(idx_map, expected_idx), "Upslope index mismatch"


def test_washout_negative_slope():
    y = np.array([0, 5, 15, 28, 40, 48, 52, 50, 45, 38, 30, 22, 15, 10, 5], dtype=float)
    data_4d = y[np.newaxis, np.newaxis, np.newaxis, :]
    maps = compute_all_maps(data_4d, tr=1.0, mask_3d=None, slope_method="linear_fit")
    wo = maps["washout"][0, 0, 0]
    assert wo < 0, f"Wash-out should be negative for descending curve, got {wo}"
    wi = maps["washin"][0, 0, 0]
    assert wi > 0, f"Wash-in should be positive for ascending curve, got {wi}"


def test_maps_output_shapes():
    data_4d = np.random.rand(8, 8, 4, 16)
    maps = compute_all_maps(data_4d, tr=1.5, mask_3d=None, slope_method="linear_fit")
    expected_shape = (8, 8, 4)
    for name in ["tmax", "washin", "segment_washin", "washout", "maxpct_enhancement"]:
        assert maps[name].shape == expected_shape, f"{name}: expected {expected_shape}, got {maps[name].shape}"
    assert maps["upslope_index"].shape == expected_shape
    assert maps["upslope_index"].dtype == np.int16
