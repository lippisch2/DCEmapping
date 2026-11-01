import { useEffect, useRef } from "react";
import { useStore } from "../store";
import { runPipeline, getJob } from "../api/client";

export function RunStep() {
  const { session, params, job, setJob } = useStore();
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const handleRun = async () => {
    if (!session) return;
    try {
      const res = await runPipeline({
        session_id: session.session_id,
        ...params,
      });
      setJob(res);
    } catch (e: any) {
      alert("Run error: " + e.message);
    }
  };

  useEffect(() => {
    if (job && (job.status === "queued" || job.status === "running")) {
      pollRef.current = setInterval(async () => {
        try {
          const updated = await getJob(job.job_id);
          setJob(updated);
          if (updated.status === "done" || updated.status === "error") {
            clearInterval(pollRef.current!);
          }
        } catch {
          clearInterval(pollRef.current!);
        }
      }, 500);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [job?.status]);

  return (
    <div className="card">
      <h2>Run Pipeline</h2>

      {!job ? (
        <button className="btn btn-primary" onClick={handleRun} disabled={!session}>
          Start Processing
        </button>
      ) : (
        <div>
          <p>Status: <strong>{job.status}</strong></p>
          <div className="progress-bar">
            <div className="fill" style={{ width: `${job.progress_pct}%` }} />
          </div>
          <p>{job.progress_pct}%</p>

          {job.status === "running" && <span className="spinner" />}

          {job.status === "error" && job.error && (
            <div className="error-box">{job.error}</div>
          )}
        </div>
      )}
    </div>
  );
}
