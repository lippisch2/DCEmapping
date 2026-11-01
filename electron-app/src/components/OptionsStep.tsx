import { useStore } from "../store";

export function OptionsStep() {
  const { params, setParams } = useStore();

  return (
    <div className="card">
      <h2>Processing Options</h2>

      <div className="form-row">
        <label>TR (seconds)</label>
        <input
          type="number"
          value={params.tr}
          onChange={(e) => setParams({ tr: parseFloat(e.target.value) || 14 })}
          step={0.1}
        />
      </div>

      <div className="form-row">
        <label>Slope method</label>
        <select
          value={params.slope_method}
          onChange={(e) => setParams({ slope_method: e.target.value as any })}
        >
          <option value="linear_fit">Linear fit</option>
          <option value="two_point">Two point</option>
          <option value="quadratic">Quadratic</option>
        </select>
      </div>

      <div className="form-row">
        <label>Temporal Gaussian sigma</label>
        <input
          type="number"
          value={params.smooth_sigma}
          onChange={(e) => setParams({ smooth_sigma: parseFloat(e.target.value) || 0 })}
          step={0.1}
          min={0}
        />
      </div>

      <div className="form-row">
        <label>Savitzky-Golay window</label>
        <input
          type="number"
          value={params.smooth_window}
          onChange={(e) => setParams({ smooth_window: parseInt(e.target.value) || 0 })}
          min={0}
          step={2}
        />
      </div>

      <div className="form-row">
        <label>Spatial smoothing sigma</label>
        <input
          type="number"
          value={params.spatial_smooth_sigma}
          onChange={(e) => setParams({ spatial_smooth_sigma: parseFloat(e.target.value) || 0 })}
          step={0.1}
          min={0}
        />
      </div>

      <div className="form-row">
        <label>Onset fallback idx</label>
        <input
          type="number"
          value={params.onset_fallback}
          onChange={(e) => setParams({ onset_fallback: parseInt(e.target.value) || 2 })}
          min={0}
        />
      </div>

      <div className="form-row">
        <label>Skip first frame</label>
        <input
          type="checkbox"
          checked={params.skip_first}
          onChange={(e) => setParams({ skip_first: e.target.checked })}
        />
      </div>

      <div className="form-row">
        <label>Skip N frames</label>
        <input
          type="number"
          value={params.skip_frames}
          onChange={(e) => setParams({ skip_frames: parseInt(e.target.value) || 0 })}
          min={0}
        />
      </div>
    </div>
  );
}
