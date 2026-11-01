import { useEffect } from "react";
import { useStore } from "./store";
import { fetchStatus } from "./api/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { InputStep } from "./components/InputStep";
import { OptionsStep } from "./components/OptionsStep";
import { RunStep } from "./components/RunStep";
import { ResultsPanel } from "./components/ResultsPanel";

const STEPS = ["Input", "Options", "Run", "Results"];

function App() {
  const { step, setStep, backendOk, setBackendOk, session, job } = useStore();

  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetchStatus();
        setBackendOk(res.ok === true);
      } catch {
        setBackendOk(false);
      }
    };
    check();
    const id = setInterval(check, 3000);
    return () => clearInterval(id);
  }, []);

  const canNext = () => {
    if (step === 0) return !!session;
    if (step === 1) return true;
    if (step === 2) return job?.status === "done";
    return false;
  };

  return (
    <ErrorBoundary>
      <div className="app">
        <header>
          <h1>DCEMapping</h1>
          <div className={`status-dot ${backendOk ? "ok" : ""}`} title={backendOk ? "Backend connected" : "Backend offline"} />
        </header>

        <div className="stepper">
          {STEPS.map((label, i) => (
            <div
              key={i}
              className={`step-indicator ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}
              title={label}
              onClick={() => i <= step && setStep(i)}
              style={{ cursor: i <= step ? "pointer" : "default" }}
            />
          ))}
        </div>

        <div className="content">
          {step === 0 && <InputStep />}
          {step === 1 && <OptionsStep />}
          {step === 2 && <RunStep />}
          {step === 3 && <ResultsPanel />}
        </div>

        <div className="nav-bar">
          <button
            className="btn btn-secondary"
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
          >
            Back
          </button>
          <span style={{ color: "var(--text-dim)", fontSize: 13 }}>
            {STEPS[step]}
          </span>
          {step < 3 ? (
            <button
              className="btn btn-primary"
              onClick={() => setStep(step + 1)}
              disabled={!canNext()}
            >
              Next
            </button>
          ) : (
            <button
              className="btn btn-secondary"
              onClick={() => {
                setStep(0);
                useStore.setState({ session: null, job: null });
              }}
            >
              New Session
            </button>
          )}
        </div>
      </div>
    </ErrorBoundary>
  );
}

export default App;
