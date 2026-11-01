import re
from pathlib import Path

import nibabel as nib
import numpy as np


def load_nifti_4d(path):
    path = Path(path)
    img = nib.load(str(path))
    data = np.asarray(img.get_fdata(), dtype=np.float64)
    if data.ndim != 4:
        raise ValueError(
            f"Expected 4D NIfTI (X x Y x Z x T), got shape {data.shape} "
            f"with ndim={data.ndim}"
        )
    return data, img.affine, img.header


def load_nifti_3d(path):
    path = Path(path)
    img = nib.load(str(path))
    data = np.asarray(img.get_fdata(), dtype=np.float64)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D NIfTI, got shape {data.shape}")
    return data, img.affine, img.header


def _extract_frame_number(path):
    stem = path.stem.replace(".nii", "")
    m = re.search(r"_(\d+)$", stem)
    if m:
        return int(m.group(1))
    raise ValueError(f"Cannot extract frame number from: {path.name}")


def load_and_stack_3d_frames(file_paths):
    file_paths = list(file_paths)
    if not file_paths:
        raise ValueError("No frame files provided")

    frames = []
    ref_shape = None
    ref_affine = None
    for fp in file_paths:
        data, affine, _ = load_nifti_3d(str(fp))
        if ref_shape is None:
            ref_shape = data.shape
            ref_affine = affine
        elif data.shape != ref_shape:
            raise ValueError(
                f"Frame shape mismatch: {fp} has {data.shape}, "
                f"expected {ref_shape}"
            )
        frames.append(data)

    data_4d = np.stack(frames, axis=-1)
    return data_4d, ref_affine, None


def load_stack_and_save_4d(file_paths, output_path):
    data, affine, _ = load_and_stack_3d_frames(file_paths)
    save_map(data, affine, output_path)
    return data, affine


def load_mask(path, expected_3d_shape):
    mask_data, mask_affine, _ = load_nifti_3d(path)
    if mask_data.shape != expected_3d_shape:
        raise ValueError(
            f"Mask shape {mask_data.shape} does not match "
            f"expected spatial shape {expected_3d_shape}"
        )
    mask_bool = mask_data > 0
    return mask_bool, mask_affine


def save_map(data, affine, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    img = nib.Nifti1Image(data, affine)
    nib.save(img, str(path))


def block_downsample_3d(data_3d, factor):
    x, y, z = data_3d.shape
    fx = fy = fz = factor
    tx = (x // fx) * fx
    ty = (y // fy) * fy
    tz = (z // fz) * fz
    cropped = data_3d[:tx, :ty, :tz]
    return cropped.reshape(tx // fx, fx, ty // fy, fy, tz // fz, fz).mean(axis=(1, 3, 5))


def block_downsample_4d(data_4d, factor):
    x, y, z, t = data_4d.shape
    fx = fy = fz = factor
    tx = (x // fx) * fx
    ty = (y // fy) * fy
    tz = (z // fz) * fz
    cropped = data_4d[:tx, :ty, :tz, :]
    return cropped.reshape(tx // fx, fx, ty // fy, fy, tz // fz, fz, t).mean(axis=(1, 3, 5))


def resample_affine(affine, factor):
    new_affine = affine.copy()
    new_affine[:3, :3] *= factor
    return new_affine
