# DCEmapping

**DCE-MRI perfusion mapping utility** — convert dynamic contrast-enhanced MRI
time-intensity curves into semi-quantitative pharmacokinetic maps:
Tmax, wash-in, wash-out, upslope index, and maximum percent enhancement.

```text
Input:  4D DCE-MRI series (NIfTI)  +  optional brain mask
Output: NIfTI parametric maps + FastAPI backend + Electron/React desktop GUI
```

## What it does

For every voxel inside (optionally) a brain mask, DCEmapping fits the
contrast-agent time-intensity curve and derives:

| Map | Meaning |
|-----|---------|
| `tmax` | Time to peak enhancement (seconds) |
| `washin` | Upslope / enhancement rate during the wash-in phase |
| `washout` | Downslope / wash-out rate after peak |
| `upslope_index` | Frame index of maximum slope (wash-in onset) |
| `maxpct_enhancement` | Maximum percent enhancement relative to baseline |

Slope methods: **linear fit**, **two-point**, **quadratic**.  
Temporal smoothing: Savitzky–Golay or Gaussian.  
Optional spatial downsampling for speed. Motion outlier detection flags
suspicious frame-to-frame jumps.

## Installation

### Python (CLI + FastAPI backend)

```bash
git clone https://github.com/lippisch2/DCEmapping.git
cd DCEmapping
pip install -r requirements.txt
```

Requirements: `nibabel`, `numpy`, `scipy`, `pyyaml`, `fastapi`, `uvicorn`.

### Run from the command line

```bash
python main.py --input /path/to/dce_series --output_dir ./maps \
  --tr 14.0 --slope_method linear_fit --yes
```

See `main.py --help` for all options (mask, smoothing, resampling,
frame pattern, skip first frame, etc.).

### Run the API server

```bash
pip install -r requirements.txt   # includes fastapi + uvicorn
uvicorn src.api:app --reload      # or: python -m src.api
```

The FastAPI app exposes `/api/status`, `/api/load`, `/api/run`, `/api/run/{job_id}`,
and `/api/nifti` for the desktop GUI.

### Desktop GUI (Electron + React)

The `electron-app/` folder is a Vite + React + TypeScript frontend talking to
the FastAPI backend through an Electron main process.

```bash
cd electron-app
npm install
npm run build          # Vite + TypeScript build
npm run build:linux    # also packages AppImage + .deb via electron-builder
```

## Repository layout

```
DCEmapping/
├── main.py                      # Python CLI entry point
├── requirements.txt             # Python dependencies
├── configs/default.yaml         # Pipeline parameter defaults
├── electronGUIplan.txt          # GUI design notes
├── mehub_id                     # Project metadata
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── pipeline.py              # CLI pipeline orchestration
│   ├── maps.py                  # Parametric map computation
│   ├── io_utils.py              # NIfTI I/O, frame stacking, downsampling
│   ├── preprocessing.py         # Masking, Savitzky–Golay, motion check
│   ├── tic_derivatives.py       # Time-intensity curve derivatives
│   └── api.py                   # FastAPI backend for the GUI
├── tests/
│   ├── test_maps.py             # Map computation tests
│   └── test_synthetic_tic.py    # Synthetic time-intensity curve tests
├── electron-app/                # Electron + React desktop GUI
│   ├── src/                     # React + TypeScript source
│   ├── electron/                # Electron main & preload scripts
│   ├── dist-electron/           # Compiled Electron main process
│   └── package.json             # electron-builder config (AppImage + .deb)
└── cmatrix/                     # PowerShell helper + demo
    ├── cmatrix.psm1
    ├── demo.gif
    └── README.md
```

## Testing

```bash
python -m pytest tests -q        # 11 passed
```

## Outputs

Each parametric map is written as a separate NIfTI volume (`.nii.gz`) into
`<output_dir>` (default: `<input_parent>/DCEmapping_output/`), preserving the
input geometry (affine) so the maps overlay directly on the source series in
any viewer.

## References / notes

- DCE-MRI pharmacokinetic modeling is semi-quantitative; absolute contrast
  agent concentration requires an arterial input function (AIF) and a
  compartment model (Tofts, extended Tofts, etc.), which are **not**
  implemented here. The maps are relative perfusion descriptors intended for
  research and comparative analysis.
- This is research software, not a medical device. Not cleared for clinical
  diagnosis.

## Release assets

Convenience binaries are attached to each GitHub release:

| Asset | Platform |
|-------|----------|
| `DCEmapping-<version>-portable.exe` | Windows (portable, no install) |
| `DCEmapping-<version>-x86_64.AppImage` | Linux (AppImage, run anywhere) |

## License

See `mehub_id` / project metadata. Research use only.
