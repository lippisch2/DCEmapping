export interface Session {
  session_id: string;
  nifti_count: number;
}

export interface Job {
  job_id: string;
  status: "queued" | "running" | "done" | "error";
  progress_pct: number;
  outputs: string[];
  error: string | null;
}

export type SlopeMethod = "linear_fit" | "two_point" | "quadratic";

export interface RunParams {
  tr: number;
  slope_method: SlopeMethod;
  smooth_sigma: number;
  smooth_window: number;
  spatial_smooth_sigma: number;
  onset_fallback: number;
  pattern: string;
  skip_first: boolean;
  skip_frames: number;
}
