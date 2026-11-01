const BASE = "http://127.0.0.1:18923";

export async function fetchStatus() {
  const res = await fetch(`${BASE}/api/status`);
  return res.json();
}

export async function loadInput(payload: {
  input: string;
  mask?: string;
  out?: string;
  dwi_mask?: boolean;
  dwi_pattern?: string;
  dwi_threshold?: number;
}) {
  const res = await fetch(`${BASE}/api/load`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Load failed");
  return res.json();
}

export async function runPipeline(payload: {
  session_id: string;
  tr?: number;
  slope_method?: string;
  smooth_sigma?: number;
  smooth_window?: number;
  spatial_smooth_sigma?: number;
  onset_fallback?: number;
  pattern?: string;
  skip_first?: boolean;
  skip_frames?: number;
}) {
  const res = await fetch(`${BASE}/api/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error((await res.json()).detail || "Run failed");
  return res.json();
}

export async function getJob(jobId: string) {
  const res = await fetch(`${BASE}/api/run/${jobId}`);
  if (!res.ok) throw new Error("Job not found");
  return res.json();
}

export function niftiUrl(path: string) {
  return `${BASE}/api/nifti?path=${encodeURIComponent(path)}`;
}
