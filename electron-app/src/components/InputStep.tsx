import { useStore } from "../store";
import { loadInput } from "../api/client";

declare global {
  interface Window {
    dcemapping?: {
      selectDirectory: () => Promise<string | null>;
      selectFile: () => Promise<string | null>;
    };
  }
}

export function InputStep() {
  const {
    inputPath, setInputPath,
    maskPath, setMaskPath,
    outputPath, setOutputPath,
    pattern, setPattern,
    session, setSession,
    backendOk,
  } = useStore();

  const handleBrowse = async (type: "dir" | "file") => {
    if (!window.dcemapping) return;
    const p = type === "dir"
      ? await window.dcemapping.selectDirectory()
      : await window.dcemapping.selectFile();
    if (p) setInputPath(p);
  };

  const handleLoad = async () => {
    if (!inputPath) return;
    try {
      const res = await loadInput({
        input: inputPath,
        mask: maskPath || undefined,
        out: outputPath || undefined,
      });
      setSession(res);
    } catch (e: any) {
      alert("Load error: " + e.message);
    }
  };

  return (
    <div>
      <div className="card">
        <h2>Input</h2>
        <div className="form-row">
          <label>DCE NIfTI path</label>
          <div className="path-row">
            <input
              type="text"
              value={inputPath}
              onChange={(e) => setInputPath(e.target.value)}
              placeholder="/path/to/dce/folder or file.nii.gz"
            />
            <button className="btn btn-secondary" onClick={() => handleBrowse("dir")}>Browse</button>
          </div>
        </div>
        <div className="form-row">
          <label>Mask (optional)</label>
          <div className="path-row">
            <input
              type="text"
              value={maskPath}
              onChange={(e) => setMaskPath(e.target.value)}
              placeholder="/path/to/mask.nii.gz"
            />
            <button className="btn btn-secondary" onClick={() => handleBrowse("file")}>Browse</button>
          </div>
        </div>
        <div className="form-row">
          <label>Output dir</label>
          <input
            type="text"
            value={outputPath}
            onChange={(e) => setOutputPath(e.target.value)}
            placeholder="Default: <input_parent>/DCEmapping_output"
          />
        </div>
        <div className="form-row">
          <label>Frame pattern</label>
          <input
            type="text"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            placeholder="*t1_vibe_tra_dyn*"
          />
        </div>
      </div>

      <div className="card">
        <h2>Status</h2>
        {session ? (
          <p>Session <strong>{session.session_id}</strong> loaded &mdash; {session.nifti_count} file(s) found</p>
        ) : backendOk ? (
          <button className="btn btn-primary" onClick={handleLoad} disabled={!inputPath}>
            Load Input
          </button>
        ) : (
          <p style={{ color: "#f88" }}>Backend not connected...</p>
        )}
      </div>
    </div>
  );
}
