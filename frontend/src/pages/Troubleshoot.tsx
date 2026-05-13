import { useState, useEffect } from "react";
import { supportBundleApi, type SupportBundleTask, type TaskStatus } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Troubleshoot() {
  const { isManager } = useAuth();
  const [task, setTask] = useState<SupportBundleTask | null>(null);
  const [status, setStatus] = useState<TaskStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pollInterval, setPollInterval] = useState<number | null>(null);

  const startGeneration = async () => {
    setLoading(true);
    setError(null);
    setTask(null);
    setStatus(null);
    try {
      const t = await supportBundleApi.generate();
      setTask(t);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!task || status?.status === "completed" || status?.status === "failed") {
      if (pollInterval) {
        clearInterval(pollInterval);
        setPollInterval(null);
      }
      return;
    }

    const id = window.setInterval(async () => {
      try {
        const s = await supportBundleApi.getStatus(task.task_id);
        setStatus(s);
      } catch (e) {
        console.error("Poll error", e);
      }
    }, 3000);

    setPollInterval(id);
    return () => clearInterval(id);
  }, [task]);

  if (!isManager) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <p className="text-gray-500">Manager access required to generate support bundles.</p>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto">
      <h1 className="text-xl font-bold text-gray-800 mb-6">Troubleshoot</h1>

      <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm space-y-4">
        <p className="text-sm text-gray-600">
          Generate a support bundle containing cluster state, pod logs, and application diagnostics,
          then upload it directly to the Replicated Vendor Portal for analysis.
        </p>

        <button
          onClick={startGeneration}
          disabled={loading || (status?.status === "in_progress" || status?.status === "pending")}
          className="px-4 py-2 text-sm rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "Starting..." : status?.status === "in_progress" || status?.status === "pending"
            ? "Generating..."
            : "Generate & Upload Support Bundle"}
        </button>

        {error && (
          <div className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">
            {error}
          </div>
        )}

        {task && !status && (
          <div className="text-sm text-gray-600">
            Task queued: <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">{task.task_id}</code>
          </div>
        )}

        {status && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">Status:</span>
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  status.status === "completed"
                    ? "bg-green-100 text-green-700"
                    : status.status === "failed"
                    ? "bg-red-100 text-red-700"
                    : status.status === "in_progress"
                    ? "bg-blue-100 text-blue-700"
                    : "bg-gray-100 text-gray-700"
                }`}
              >
                {status.status}
              </span>
            </div>

            {status.result?.bundle_id && (
              <div className="text-sm text-green-700 bg-green-50 rounded px-3 py-2 space-y-1">
                <p>Support bundle uploaded successfully!</p>
                <p>
                  Bundle ID: <code className="text-xs">{status.result.bundle_id}</code>
                </p>
                <p>
                  View in{" "}
                  <a
                    href="https://vendor.replicated.com"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline font-medium"
                  >
                    Replicated Vendor Portal
                  </a>
                </p>
              </div>
            )}

            {status.result?.error && (
              <div className="text-sm text-red-600 bg-red-50 rounded px-3 py-2">
                {status.result.error}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
