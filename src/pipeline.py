import argparse
import json
import re
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

from .io_utils import (
    load_nifti_4d,
    load_mask,
    save_map,
    load_and_stack_3d_frames,
    load_stack_and_save_4d,
    _extract_frame_number,
    block_downsample_4d,
    block_downsample_3d,
    resample_affine,
)
from .preprocessing import apply_mask, savgol_temporal, check_motion
from .maps import compute_all_maps


def build_parser():
    p = argparse.ArgumentParser(
        description="DCE-MRI Perfusion Mapping Pipeline (semi-quantitative maps)"
    )
    p.add_argument("--input", "-i", required=True,
                   help="Input folder containing DCE NIfTI files, or a single 4D NIfTI")
    p.add_argument("--output_dir", "-o", default=None,
                   help="Output directory (default: <input_parent>/DCEmapping_output)")
    p.add_argument("--tr", type=float, default=14.0,
                   help="Temporal resolution in seconds (default: 14.0)")
    p.add_argument("--mask", "-m", default=None,
                   help="Optional 3D binary mask NIfTI (applied to ALL subjects)")
    p.add_argument("--slope_method", choices=["linear_fit", "two_point", "quadratic"],
                   default="linear_fit",
                   help="Slope computation method (default: linear_fit)")
    p.add_argument("--smooth_sigma", type=float, default=0.0,
                   help="Gaussian temporal smoothing sigma (0 = no smoothing)")
    p.add_argument("--smooth_window", type=int, default=0,
                   help="Savitzky-Golay window length (used if smooth_sigma=0 "
                        "and smooth_window > 2)")
    p.add_argument("--onset_fallback", type=int, default=2,
                   help="Minimum onset index when argmax(d2S/dt2) is too early")
    p.add_argument("--pattern", nargs="?", const="*t1_vibe_tra_dyn*", default=None,
                   help="Glob pattern for 3D frame files (default: *t1_vibe_tra_dyn*)")
    p.add_argument("--skip_first", action="store_true",
                   help="Drop the first frame when loading from --pattern")
    p.add_argument("--skip_frames", type=int, default=0,
                   help="Drop N frames from the start (overrides --skip_first if >0)")
    p.add_argument("--resample", type=int, default=1,
                   help="Spatial downsampling factor (default 1 = no resampling). "
                        "Groups NxNxN voxels and averages them for speed.")
    p.add_argument("--spatial_smooth_sigma", type=float, default=0.5,
                   help="3D Gaussian spatial smoothing sigma per frame (default: 0.5)")
    p.add_argument("--yes", "-y", action="store_true",
                   help="Skip confirmation prompt and process all detected files")

    # DWI-based auto-masking
    p.add_argument("--dwi_mask", action="store_true",
                   help="Auto-build mask from lowest b-value DWI in the input folder")
    p.add_argument("--dwi_pattern", default="*dwi*",
                   help="Glob pattern for DWI files (default: *dwi*)")
    p.add_argument("--dwi_threshold", type=float, default=0.0,
                   help="Threshold for DWI mask (default: 0 = all nonzero voxels)")
    return p


def _scan_dce_files(folder):
    folder = Path(folder)
    candidates = sorted(folder.glob("*.nii.gz")) + sorted(folder.glob("*.nii"))
    dce_files = []
    for f in candidates:
        try:
            img = nib.load(str(f))
            if img.ndim == 4:
                dce_files.append(f)
        except Exception:
            pass
    return dce_files


def _confirm_files(files):
    print(f"Found {len(files)} DCE 4D NIfTI file(s):")
    for f in files:
        print(f"  {f.name}")
    while True:
        answer = input("Process these files? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


_DERIVED_SERIES_SUFFIXES = ("_SUB", "_WI", "_WO", "_MIP", "_ADC", "_PERF", "_TRACE")

_DCE_KEYWORDS = ("dyn", "dce", "perfusion", "contrast", "wash", "dynamic", "t1_vibe_tra_dyn")


def _is_clone_frame(path):
    stem = path.stem.replace(".nii", "")
    return bool(re.search(r"_(\d+)[a-z]$", stem, re.IGNORECASE))


def _is_derived_series(path):
    json_path = Path(str(path).replace(".nii.gz", ".json").replace(".nii", ".json"))
    if not json_path.exists():
        return False
    try:
        meta = json.loads(json_path.read_text())
        sd = meta.get("SeriesDescription", "")
        return any(suf in sd for suf in _DERIVED_SERIES_SUFFIXES)
    except Exception:
        return False


def _get_series_description(nifti_path):
    json_path = Path(str(nifti_path).replace(".nii.gz", ".json").replace(".nii", ".json"))
    if not json_path.exists():
        return None
    try:
        meta = json.loads(json_path.read_text())
        return meta.get("SeriesDescription", None)
    except Exception:
        return None


def _series_is_dce(sd):
    if not sd:
        return False
    lower = sd.lower()
    return any(kw in lower for kw in _DCE_KEYWORDS)


def _get_acquisition_time(nifti_path):
    json_path = Path(str(nifti_path).replace(".nii.gz", ".json").replace(".nii", ".json"))
    if not json_path.exists():
        return None
    try:
        meta = json.loads(json_path.read_text())
        return meta.get("AcquisitionTime", None)
    except Exception:
        return None


def _acq_time_to_seconds(t):
    """Convert HH:MM:SS.ffffff string to seconds from midnight."""
    parts = t.split(":")
    h, m = int(parts[0]), int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s


def _detect_dyn_series(folder):
    """Auto-detect DCE/DYN frame series from JSON sidecars.

    Groups 3D NIfTI files by SeriesDescription, identifies DCE/DYN series,
    excludes derived series, and returns the largest group sorted by frame number.
    Also extracts acquisition times for each frame.
    """
    folder = Path(folder)
    candidates = sorted(folder.glob("*.nii.gz")) + sorted(folder.glob("*.nii"))

    groups = {}
    for f in candidates:
        if not (f.name.endswith(".nii") or f.name.endswith(".nii.gz")):
            continue
        try:
            img = nib.load(str(f))
            if img.ndim != 3:
                continue
        except Exception:
            continue
        if _is_clone_frame(f):
            continue

        sd = _get_series_description(f)
        if sd is None:
            continue

        try:
            idx = _extract_frame_number(f)
        except ValueError:
            continue

        groups.setdefault(sd, []).append((idx, f))

    dce_candidates = []
    for sd, frames in groups.items():
        if _series_is_dce(sd) and len(frames) >= 3:
            dce_candidates.append((sd, frames))

    if not dce_candidates:
        return None, [], [], None

    dce_candidates.sort(key=lambda x: -len(x[1]))
    best_sd, best_frames = dce_candidates[0]
    best_frames.sort(key=lambda x: x[0])

    # Extract acquisition times for the best series
    acq_times = []
    for _, f in best_frames:
        at = _get_acquisition_time(f)
        if at is not None:
            acq_times.append(_acq_time_to_seconds(at))
        else:
            acq_times.append(None)

    # Compute per-frame intervals (seconds) from acquisition times
    frame_times = None
    if all(t is not None for t in acq_times) and len(acq_times) >= 2:
        frame_times = np.array(acq_times, dtype=np.float64)
        frame_times = frame_times - frame_times[0]  # relative to first frame

    # Collect excluded series for reporting
    excluded = []
    for sd, frames in groups.items():
        if sd == best_sd:
            continue
        frames_sorted = sorted(frames, key=lambda x: x[0])
        tag = "derived" if any(suf in sd for suf in _DERIVED_SERIES_SUFFIXES) else "other"
        excluded.append((tag, sd, len(frames_sorted), [f for _, f in frames_sorted]))

    return best_sd, [f for _, f in best_frames], excluded, frame_times


def _scan_frame_series(folder, pattern):
    folder = Path(folder)
    candidates = sorted(folder.glob(pattern))
    if not candidates:
        return []

    frame_map = {}
    n_clones = 0
    n_derived = 0
    n_not_3d = 0

    for f in candidates:
        if not (f.name.endswith(".nii") or f.name.endswith(".nii.gz")):
            continue
        if _is_clone_frame(f):
            n_clones += 1
            continue
        try:
            img = nib.load(str(f))
            if img.ndim != 3:
                n_not_3d += 1
                continue
        except Exception:
            continue
        if _is_derived_series(f):
            n_derived += 1
            continue
        try:
            idx = _extract_frame_number(f)
        except ValueError:
            continue
        frame_map[idx] = f

    excluded = []
    if n_clones:
        excluded.append(f"{n_clones} clones")
    if n_derived:
        excluded.append(f"{n_derived} derived series")
    if excluded:
        print(f"  (excluded {', '.join(excluded)})")

    if not frame_map:
        return []
    sorted_indices = sorted(frame_map)
    return [frame_map[i] for i in sorted_indices]


def _confirm_frames(files, pattern):
    suffixes = []
    for f in files:
        stem = f.stem.replace(".nii", "")
        m = re.search(r"_(\d+)$", stem)
        suffixes.append(m.group(1) if m else "?")
    print(f"Found {len(files)} 3D DCE frames matching '{pattern}':")
    print(f"  Frames: {', '.join(suffixes)}")
    while True:
        answer = input("Stack and process these frames? [Y/n]: ").strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False


def _extract_bvalue(path):
    stem = path.stem.replace(".nii", "")
    for pat in [r"_b(\d+)", r"b[=_](\d+)", r"_BVALUE_(\d+)"]:
        m = re.search(pat, stem, re.IGNORECASE)
        if m:
            return int(m.group(1))
    raise ValueError(f"Cannot extract b-value from filename: {path.name}")


def _find_dwi_files(folder, pattern):
    folder = Path(folder)
    candidates = sorted(folder.glob(pattern)) + sorted(folder.glob(pattern.upper()))
    seen = set()
    unique = []
    for f in candidates:
        if not (f.name.endswith(".nii") or f.name.endswith(".nii.gz")):
            continue
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique.append(f)
    return unique


def _find_lowest_bvalue_dwi(folder, pattern="*dwi*"):
    files = _find_dwi_files(folder, pattern)
    if not files:
        for alt in ["*ep2d_diff*", "*diff*", "*DWI*"]:
            files = _find_dwi_files(folder, alt)
            if files:
                break
    if not files:
        return None
    bvals = [_extract_bvalue(f) for f in files]
    return files[int(np.argmin(bvals))]


def _load_dwi_mask(dwi_path, spatial_shape, threshold=0.0, dce_affine=None):
    img = nib.load(str(dwi_path))
    data = np.asarray(img.get_fdata(), dtype=np.float64)
    if data.ndim == 4:
        data = data[..., 0]
    affine = img.affine

    if data.shape == spatial_shape:
        mask = data > threshold
        n_voxels = np.count_nonzero(mask)
        n_total = np.prod(spatial_shape)
        print(f"  DWI mask covers {n_voxels} / {n_total} voxels (threshold={threshold})")
        return mask

    if dce_affine is None:
        raise ValueError(
            f"DWI shape {data.shape} != DCE shape {spatial_shape}. "
            f"Provide dce_affine for resampling or use matching volumes."
        )

    from scipy.ndimage import affine_transform
    T = np.linalg.inv(affine) @ dce_affine
    matrix = T[:3, :3]
    offset = T[:3, 3]

    print(f"  Resampling DWI ({data.shape}) to DCE ({spatial_shape}) space...")
    resampled = affine_transform(
        data, matrix, offset=offset, output_shape=spatial_shape,
        order=1, mode="constant", cval=0.0,
    )
    mask = resampled > threshold
    n_voxels = np.count_nonzero(mask)
    n_total = np.prod(spatial_shape)
    print(f"  DWI mask covers {n_voxels} / {n_total} voxels (threshold={threshold})")
    return mask


def _process_file(input_path, out_dir, args, dwi_path=None):
    print(f"\n{'='*60}")
    print(f"Processing: {input_path.name}")
    print(f"{'='*60}")

    data_4d, affine, header = load_nifti_4d(str(input_path))

    resample = getattr(args, "resample", 1) or 1
    if resample > 1:
        print(f"  Resampling {resample}x...")
        data_4d = block_downsample_4d(data_4d, resample)
        affine = resample_affine(affine, resample)

    print(f"  Shape: {data_4d.shape}")

    spatial_shape = data_4d.shape[:3]

    mask_3d = None
    if dwi_path is not None:
        print(f"  Building mask from DWI: {dwi_path.name}")
        mask_3d = _load_dwi_mask(dwi_path, spatial_shape, args.dwi_threshold, dce_affine=affine)
    elif args.mask:
        mask_path = Path(args.mask)
        if not mask_path.exists():
            print(f"Error: mask not found: {mask_path}", file=sys.stderr)
            sys.exit(1)
        print(f"  Loading mask: {mask_path}")
        mask_3d, _ = load_mask(str(mask_path), spatial_shape)
        n_voxels = np.count_nonzero(mask_3d)
        n_total = np.prod(spatial_shape)
        print(f"  Mask covers {n_voxels} / {n_total} voxels")

    if args.spatial_smooth_sigma > 0:
        from scipy.ndimage import gaussian_filter
        print(f"  Spatial smoothing (sigma={args.spatial_smooth_sigma})")
        data_4d = gaussian_filter(data_4d, sigma=(args.spatial_smooth_sigma,) * 3 + (0,))

    if args.smooth_sigma > 0:
        from scipy.ndimage import gaussian_filter
        print(f"  Temporal Gaussian smoothing (sigma={args.smooth_sigma})")
        data_4d = gaussian_filter(data_4d, sigma=(0, 0, 0, args.smooth_sigma))
    elif args.smooth_window > 2:
        print(f"  Savitzky-Golay smoothing (window={args.smooth_window})")
        data_4d = savgol_temporal(data_4d, args.smooth_window)

    print("  Checking motion...")
    check_motion(data_4d)

    print("  Computing perfusion maps...")
    maps = compute_all_maps(
        data_4d,
        tr=args.tr,
        mask_3d=mask_3d,
        slope_method=args.slope_method,
        onset_fallback_idx=args.onset_fallback,
    )

    stem = input_path.stem.replace(".nii", "").replace(".gz", "")

    naming = {
        "tmax": f"{stem}_tmax.nii.gz",
        "washin": f"{stem}_washin.nii.gz",
        "segment_washin": f"{stem}_segment_washin.nii.gz",
        "washout": f"{stem}_washout.nii.gz",
        "upslope_index": f"{stem}_upslope_index.nii.gz",
        "maxpct_enhancement": f"{stem}_maxpct_enhancement.nii.gz",
    }

    for map_name, filename in naming.items():
        filepath = out_dir / filename
        print(f"    -> {filepath.name}")
        save_map(maps[map_name], affine, str(filepath))

    print(f"  Done.")


def _process_frames(frame_files, out_dir, args, dwi_path=None, s0_3d=None, frame_times=None):
    print(f"\n{'='*60}")
    print(f"Stacking {len(frame_files)} frames into 4D volume")
    print(f"{'='*60}")

    data_4d, affine, _ = load_and_stack_3d_frames(frame_files)

    resample = getattr(args, "resample", 1) or 1
    if resample > 1:
        print(f"  Resampling {resample}x...")
        data_4d = block_downsample_4d(data_4d, resample)
        affine = resample_affine(affine, resample)
        if s0_3d is not None:
            s0_3d = block_downsample_3d(s0_3d, resample)

    print(f"  Shape: {data_4d.shape}")

    spatial_shape = data_4d.shape[:3]

    mask_3d = None
    if dwi_path is not None:
        print(f"  Building mask from DWI: {dwi_path.name}")
        mask_3d = _load_dwi_mask(dwi_path, spatial_shape, args.dwi_threshold, dce_affine=affine)
    elif args.mask:
        mask_path = Path(args.mask)
        if not mask_path.exists():
            print(f"Error: mask not found: {mask_path}", file=sys.stderr)
            sys.exit(1)
        print(f"  Loading mask: {mask_path}")
        mask_3d, _ = load_mask(str(mask_path), spatial_shape)
        n_voxels = np.count_nonzero(mask_3d)
        n_total = np.prod(spatial_shape)
        print(f"  Mask covers {n_voxels} / {n_total} voxels")

    if args.spatial_smooth_sigma > 0:
        from scipy.ndimage import gaussian_filter
        print(f"  Spatial smoothing (sigma={args.spatial_smooth_sigma})")
        data_4d = gaussian_filter(data_4d, sigma=(args.spatial_smooth_sigma,) * 3 + (0,))

    if args.smooth_sigma > 0:
        from scipy.ndimage import gaussian_filter
        print(f"  Temporal Gaussian smoothing (sigma={args.smooth_sigma})")
        data_4d = gaussian_filter(data_4d, sigma=(0, 0, 0, args.smooth_sigma))
    elif args.smooth_window > 2:
        print(f"  Savitzky-Golay smoothing (window={args.smooth_window})")
        data_4d = savgol_temporal(data_4d, args.smooth_window)

    print("  Checking motion...")
    check_motion(data_4d)

    print("  Computing perfusion maps...")
    maps = compute_all_maps(
        data_4d,
        tr=args.tr,
        mask_3d=mask_3d,
        slope_method=args.slope_method,
        onset_fallback_idx=args.onset_fallback,
        s0_volume=s0_3d,
        frame_times=frame_times,
    )

    folder_name = Path(args.input).resolve().stem
    stem = folder_name

    naming = {
        "tmax": f"{stem}_tmax.nii.gz",
        "washin": f"{stem}_washin.nii.gz",
        "segment_washin": f"{stem}_segment_washin.nii.gz",
        "washout": f"{stem}_washout.nii.gz",
        "upslope_index": f"{stem}_upslope_index.nii.gz",
        "maxpct_enhancement": f"{stem}_maxpct_enhancement.nii.gz",
    }

    for map_name, filename in naming.items():
        filepath = out_dir / filename
        print(f"    -> {filepath.name}")
        save_map(maps[map_name], affine, str(filepath))

    print(f"  Done.")


def _resolve_output_dir(input_path, args):
    if args.output_dir is not None:
        return Path(args.output_dir)
    parent = input_path if input_path.is_dir() else input_path.parent
    return parent / "DCEmapping_output"


def run(args):
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: input not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = _resolve_output_dir(input_path, args)

    dwi_path = None
    if args.dwi_mask and input_path.is_dir():
        dwi_path = _find_lowest_bvalue_dwi(input_path, args.dwi_pattern)
        if dwi_path is None:
            print(f"Error: no DWI files found matching '{args.dwi_pattern}' "
                  f"in {input_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Found DWI for auto-mask: {dwi_path.name}")

    if input_path.is_dir():
        if args.pattern:
            frame_files_all = _scan_frame_series(input_path, args.pattern)
            if not frame_files_all:
                print(f"No 3D frames found matching '{args.pattern}' in {input_path}",
                      file=sys.stderr)
                sys.exit(1)

            # Extract timing from JSON sidecars
            all_times = []
            for f in frame_files_all:
                at = _get_acquisition_time(f)
                all_times.append(_acq_time_to_seconds(at) if at else None)

            if all(t is not None for t in all_times) and len(all_times) >= 2:
                all_times = np.array(all_times, dtype=np.float64)
                all_frame_times = all_times - all_times[0]
                intervals = np.diff(all_frame_times)
                print(f"  Timing from JSON: {len(all_times)} frames, intervals {intervals[0]:.1f}–{intervals[-1]:.1f}s (median {np.median(intervals):.1f}s)")
            else:
                all_frame_times = None
                print(f"  No acquisition times in JSON sidecars, using TR={args.tr}s")

            # S0 baseline computed from pre-skip frames
            s0_3d = None
            if len(frame_files_all) >= 3:
                s0_data_4d, _, _ = load_and_stack_3d_frames(frame_files_all[:3])
                s0_3d = s0_data_4d.min(axis=-1)
                print(f"  S0 baseline from first {min(3, len(frame_files_all))} frame(s)")

            n_total = len(frame_files_all)
            skip_n = args.skip_frames if args.skip_frames > 0 else (1 if args.skip_first else 0)
            if skip_n > 0:
                frame_files = frame_files_all[skip_n:]
                skipped_times = all_frame_times[skip_n:] - all_frame_times[skip_n] if all_frame_times is not None else None
            else:
                frame_files = frame_files_all
                skipped_times = all_frame_times

            if not args.yes and not _confirm_frames(frame_files, args.pattern):
                print("Aborted by user.")
                sys.exit(0)

            if skip_n > 0:
                print(f"  ({skip_n} frame(s) skipped — {len(frame_files)} / {n_total} remaining)")

            _process_frames(frame_files, out_dir, args, dwi_path=dwi_path, s0_3d=s0_3d, frame_times=skipped_times)
        else:
            # Try auto-detection from JSON sidecars first
            detected_sd, detected_frames, excluded, frame_times = _detect_dyn_series(input_path)

            if detected_frames:
                print(f"  Auto-detected DCE series: \"{detected_sd}\" ({len(detected_frames)} frames)")
                for tag, sd, count, _ in excluded:
                    print(f"  Ignored {tag} series: \"{sd}\" ({count} frames)")
                if frame_times is not None:
                    intervals = np.diff(frame_times)
                    print(f"  Timing from JSON: {len(frame_times)} frames, intervals {intervals[0]:.1f}–{intervals[-1]:.1f}s (median {np.median(intervals):.1f}s)")
                else:
                    print(f"  No acquisition times in JSON sidecars, using TR={args.tr}s")
                n_total = len(detected_frames)
                skip_n = args.skip_frames if args.skip_frames > 0 else (1 if args.skip_first else 0)
                if skip_n > 0:
                    frame_files = detected_frames[skip_n:]
                    skipped_times = frame_times[skip_n:] - frame_times[skip_n] if frame_times is not None else None
                else:
                    frame_files = detected_frames
                    skipped_times = frame_times

                if not args.yes:
                    suffixes = []
                    for f in frame_files:
                        stem = f.stem.replace(".nii", "")
                        m = re.search(r"_(\d+)$", stem)
                        suffixes.append(m.group(1) if m else "?")
                    print(f"  Frames: {', '.join(suffixes)}")
                    answer = input("Process these frames? [Y/n]: ").strip().lower()
                    if answer in ("n", "no"):
                        print("Aborted by user.")
                        sys.exit(0)

                if skip_n > 0:
                    print(f"  ({skip_n} frame(s) skipped — {len(frame_files)} / {n_total} remaining)")

                s0_3d = None
                if len(detected_frames) >= 3:
                    s0_data_4d, _, _ = load_and_stack_3d_frames(detected_frames[:3])
                    s0_3d = s0_data_4d.min(axis=-1)
                    print(f"  S0 baseline from first {min(3, len(detected_frames))} frame(s)")

                _process_frames(frame_files, out_dir, args, dwi_path=dwi_path, s0_3d=s0_3d, frame_times=skipped_times)
            else:
                # Fallback: scan for 4D NIfTIs
                dce_files = _scan_dce_files(input_path)
                if not dce_files:
                    print(f"No DCE/DYN series auto-detected and no 4D NIfTI files in {input_path}\n"
                          f"Tip: use --pattern to specify a glob for 3D frame files",
                          file=sys.stderr)
                    sys.exit(1)
                if not args.yes and not _confirm_files(dce_files):
                    print("Aborted by user.")
                    sys.exit(0)
                for f in dce_files:
                    _process_file(f, out_dir, args, dwi_path=dwi_path)
    else:
        _process_file(input_path, out_dir, args, dwi_path=dwi_path)

    print("\nAll done.")


def main():
    parser = build_parser()
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
