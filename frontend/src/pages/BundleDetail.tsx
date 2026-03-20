import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { bundleApi, findingApi, type Bundle, type Finding } from "../api/client";
import FindingCard from "../components/FindingCard";
import { useAuth } from "../context/AuthContext";

const STATUS_COLORS: Record<string, string> = {
  uploaded: "bg-blue-100 text-blue-800",
  processing: "bg-yellow-100 text-yellow-800",
  ready: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
};

const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function groupFindingsBySeverity(findings: Finding[]): Record<string, Finding[]> {
  const groups: Record<string, Finding[]> = {};
  for (const sev of SEVERITY_ORDER) {
    groups[sev] = findings.filter((f) => f.severity === sev);
  }
  return groups;
}

export default function BundleDetail() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const isManager = user?.role === "manager" || user?.role === "admin";
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [findingsLoading, setFindingsLoading] = useState(false);
  const [downloadingReport, setDownloadingReport] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  // Bump this to force the polling effect to restart after reanalysis
  const [pollKey, setPollKey] = useState(0);

  const loadFindings = useCallback((bundleId: string, cancelled: { v: boolean }) => {
    setFindingsLoading(true);
    findingApi
      .list(bundleId)
      .then((resp) => {
        if (!cancelled.v) {
          setFindings(resp.items);
        }
      })
      .catch(() => {
        // silently fail findings load
      })
      .finally(() => {
        if (!cancelled.v) setFindingsLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!id) return;

    const cancelled = { v: false };

    function poll() {
      if (cancelled.v) return;
      bundleApi
        .get(id!)
        .then((b) => {
          if (!cancelled.v) {
            setBundle(b);
            setLoading(false);
            if (b.status === "uploaded" || b.status === "processing") {
              setTimeout(poll, 2000);
            } else if (b.status === "ready") {
              loadFindings(b.id, cancelled);
            }
          }
        })
        .catch((e: unknown) => {
          if (!cancelled.v) {
            setError(String(e));
            setLoading(false);
          }
        });
    }

    poll();
    return () => {
      cancelled.v = true;
    };
  }, [id, pollKey, loadFindings]);

  function handleFindingUpdate(updated: Finding) {
    setFindings((prev) => prev.map((f) => (f.id === updated.id ? updated : f)));
  }

  async function handleReanalyze() {
    if (!id) return;
    setReanalyzing(true);
    setFindings([]);
    try {
      await bundleApi.reanalyze(id);
      // Reset bundle state to processing and start polling again
      setBundle((prev) => prev ? { ...prev, status: "processing" } : prev);
      setPollKey((k) => k + 1);
    } catch (e) {
      console.error("Failed to reanalyze bundle", e);
    } finally {
      setReanalyzing(false);
    }
  }

  async function handleDownloadReport() {
    if (!id) return;
    setDownloadingReport(true);
    try {
      const md = await findingApi.downloadReport(id);
      const blob = new Blob([md], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${id}.md`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Failed to download report", e);
    } finally {
      setDownloadingReport(false);
    }
  }

  if (loading) {
    return <div className="text-center py-16 text-gray-400">Loading bundle...</div>;
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!bundle) return null;

  const grouped = groupFindingsBySeverity(findings);

  return (
    <div>
      <div className="mb-6">
        <Link to="/" className="text-sm text-indigo-600 hover:underline">
          &larr; Back to bundles
        </Link>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6 mb-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{bundle.original_filename}</h1>
          </div>
          <span
            className={`shrink-0 px-3 py-1 rounded-full text-xs font-medium ${
              STATUS_COLORS[bundle.status] ?? "bg-gray-100 text-gray-700"
            }`}
          >
            {bundle.status}
          </span>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-gray-500">Size</dt>
            <dd className="font-medium text-gray-800">{formatBytes(bundle.size_bytes)}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Tenant</dt>
            <dd className="font-medium text-gray-800">{bundle.tenant_id}</dd>
          </div>
          <div>
            <dt className="text-gray-500">Uploaded</dt>
            <dd className="font-medium text-gray-800">
              {new Date(bundle.created_at).toLocaleString()}
            </dd>
          </div>
          <div>
            <dt className="text-gray-500">Updated</dt>
            <dd className="font-medium text-gray-800">
              {new Date(bundle.updated_at).toLocaleString()}
            </dd>
          </div>
        </dl>

        {bundle.error_message && (
          <div className="mt-4 rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
            <strong>Error:</strong> {bundle.error_message}
          </div>
        )}

        {bundle.status === "ready" && isManager && (
          <div className="mt-4">
            <button
              onClick={handleReanalyze}
              disabled={reanalyzing}
              className="px-3 py-1.5 text-sm rounded border border-indigo-300 text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
            >
              {reanalyzing ? "Re-running..." : "Re-run Analysis"}
            </button>
            <span className="ml-2 text-xs text-gray-400">
              Re-runs all detection rules on existing evidence (picks up new rules)
            </span>
          </div>
        )}

        {(bundle.status === "uploaded" || bundle.status === "processing") && (
          <div className="mt-4 flex items-center gap-2 text-sm text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-md p-3">
            <div className="h-4 w-4 rounded-full border-2 border-yellow-400 border-t-yellow-700 animate-spin shrink-0" />
            Analyzing bundle... This page will update automatically.
          </div>
        )}
      </div>

      {/* Findings section */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Findings
            {findings.length > 0 && (
              <span className="ml-2 text-sm font-normal text-gray-500">
                ({findings.length})
              </span>
            )}
          </h2>
          {bundle.status === "ready" && findings.length > 0 && (
            <button
              onClick={handleDownloadReport}
              disabled={downloadingReport}
              className="px-3 py-1.5 text-sm rounded border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
            >
              {downloadingReport ? "Downloading..." : "Download Report (Markdown)"}
            </button>
          )}
        </div>

        {bundle.status !== "ready" ? (
          <p className="text-sm text-gray-400">
            Findings will appear here once analysis is complete.
          </p>
        ) : findingsLoading ? (
          <p className="text-sm text-gray-400">Loading findings...</p>
        ) : findings.length === 0 ? (
          <p className="text-sm text-gray-400">No findings detected for this bundle.</p>
        ) : (
          <div className="space-y-6">
            {SEVERITY_ORDER.map((sev) => {
              const group = grouped[sev];
              if (!group || group.length === 0) return null;
              return (
                <div key={sev}>
                  <h3 className="text-sm font-semibold text-gray-600 uppercase tracking-widest border-b border-gray-200 pb-2 mb-3">
                    {sev} ({group.length})
                  </h3>
                  <div className="space-y-3">
                    {group.map((f) => (
                      <FindingCard
                        key={f.id}
                        finding={f}
                        onUpdate={handleFindingUpdate}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Report section */}
      {bundle.status === "ready" && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Report</h2>
          <p className="text-sm text-gray-500 mb-4">
            Download a full analysis report including all findings and AI explanations in Markdown format.
          </p>
          <button
            onClick={handleDownloadReport}
            disabled={downloadingReport}
            className="px-4 py-2 text-sm rounded-md bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {downloadingReport ? "Downloading..." : "Download Report (Markdown)"}
          </button>
        </div>
      )}
    </div>
  );
}
