import { create } from "zustand";
import type { Session, Job, RunParams } from "./types";

interface AppState {
  step: number;
  setStep: (s: number) => void;

  inputPath: string;
  setInputPath: (p: string) => void;
  maskPath: string;
  setMaskPath: (p: string) => void;
  outputPath: string;
  setOutputPath: (p: string) => void;
  pattern: string;
  setPattern: (p: string) => void;

  session: Session | null;
  setSession: (s: Session) => void;

  params: RunParams;
  setParams: (p: Partial<RunParams>) => void;

  job: Job | null;
  setJob: (j: Job) => void;

  backendOk: boolean;
  setBackendOk: (v: boolean) => void;
}

export const useStore = create<AppState>((set) => ({
  step: 0,
  setStep: (step) => set({ step }),

  inputPath: "",
  setInputPath: (inputPath) => set({ inputPath }),
  maskPath: "",
  setMaskPath: (maskPath) => set({ maskPath }),
  outputPath: "",
  setOutputPath: (outputPath) => set({ outputPath }),
  pattern: "*t1_vibe_tra_dyn*",
  setPattern: (pattern) => set({ pattern }),

  session: null,
  setSession: (session) => set({ session }),

  params: {
    tr: 14.0,
    slope_method: "linear_fit",
    smooth_sigma: 0.0,
    smooth_window: 0,
    spatial_smooth_sigma: 0.5,
    onset_fallback: 2,
    pattern: "*t1_vibe_tra_dyn*",
    skip_first: false,
    skip_frames: 0,
  },
  setParams: (p) => set((s) => ({ params: { ...s.params, ...p } })),

  job: null,
  setJob: (job) => set({ job }),

  backendOk: false,
  setBackendOk: (backendOk) => set({ backendOk }),
}));
