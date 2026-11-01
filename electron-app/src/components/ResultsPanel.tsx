import { useState } from "react";
import { useStore } from "../store";
import { NiftiViewer } from "./NiftiViewer";

const MAP_LABELS: Record<string, string> = {
  tmax: "Time to Max (Tmax)",
  washin: "Wash-in Rate",
  segment_washin: "Segment Wash-in Slope",
  washout: "Wash-out Slope",
  upslope_index: "Upslope Frame Index",
  maxpct_enhancement: "Max % Enhancement",
};

export function ResultsPanel() {
  const { job } = useStore();
  const [selectedMap, setSelectedMap] = useState<string | null>(null);

  if (!job || job.status !== "done") return null;

  if (job.outputs.length === 0) {
    return (
      <div className="card">
        <h2>Results</h2>
        <p>No output files generated.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Results</h2>
      <ul className="output-list">
        {job.outputs.map((path: string) => {
          const filename = path.split("/").pop() || path.split("\\").pop() || "";
          const key = Object.keys(MAP_LABELS).find((k) => filename.includes(k)) || filename;
          return (
            <li key={path}>
              <span>{MAP_LABELS[key] || filename} — {filename}</span>
              <button className="btn btn-ghost" onClick={() => setSelectedMap(path)}>
                View
              </button>
            </li>
          );
        })}
      </ul>

      {selectedMap && (
        <div className="viewer-container">
          <NiftiViewer path={selectedMap} />
          <button
            className="btn btn-secondary"
            style={{ marginTop: 8 }}
            onClick={() => setSelectedMap(null)}
          >
            Close Viewer
          </button>
        </div>
      )}
    </div>
  );
}
