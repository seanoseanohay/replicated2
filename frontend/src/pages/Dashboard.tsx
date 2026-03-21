import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { bundleApi, dashboardApi, type BundleHealthSummary, type DashboardStats } from "../api/client";
import { useAuth } from "../context/AuthContext";
import HealthBar from "../components/HealthBar";

const HEALTH_COLOR: Record<string, string> = {
  green: "text-green-600",
  yellow: "text-yellow-600",
  orange: "text-orange-500",
  red: "text-red-600",
};

const STATUS_BADGE: Record<string, string> = {
  ready: "bg-green-100 text-green-800",
  processing: "bg-blue-100 text-blue-800",
  uploaded: "bg-gray-100 text-gray-700",
  error: "bg-red-100 text-red-800",
};

function SummaryCard({
  label,
  value,
  colorClass,
}: {
  label: string;
  value: number;
  colorClass: string;
}) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-sm">
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${colorClass}`}>{value}</p>
    </div>
  );
}

export default function Dashboard() {
  const { isManager } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<BundleHealthSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  function loadStats() {
    dashboardApi
      .getStats()
      .then(setStats)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadStats();
  }, []);

  async function handleDelete() {
    if (!confirmTarget) return;
    setDeleting(true);
    try {
      await bundleApi.delete(confirmTarget.bundle_id);
      setConfirmTarget(null);
      setError(null);
      setLoading(true);
      await dashboardApi.getStats().then(setStats).finally(() => setLoading(false));
    } catch (e) {
      setConfirmTarget(null);
      setError(String(e));
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="text-center py-16 text-gray-400">
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">
        Failed to load dashboard: {error}
      </div>
    );
  }

  if (!stats) return null;

  const openCriticals = stats.findings_by_severity["critical"] ?? 0;
  const openHighs = stats.findings_by_severity["high"] ?? 0;
  const bundlesWithIssues = stats.bundles.filter(
    (b) => b.health_score < 80
  ).length;

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Health overview across all bundles
          </p>
        </div>
        <Link
          to="/upload"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
        >
          Upload Bundle
        </Link>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <SummaryCard
          label="Total Bundles"
          value={stats.total_bundles}
          colorClass="text-blue-600"
        />
        <SummaryCard
          label="Open Criticals"
          value={openCriticals}
          colorClass="text-red-600"
        />
        <SummaryCard
          label="Open Highs"
          value={openHighs}
          colorClass="text-orange-500"
        />
        <SummaryCard
          label="Bundles with Issues"
          value={bundlesWithIssues}
          colorClass="text-yellow-600"
        />
      </div>

      {/* Bundle Table */}
      <div className="bg-white rounded-lg border border-gray-200 shadow-sm mb-8">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="text-base font-semibold text-gray-800">
            Bundle Health
          </h2>
        </div>
        {stats.bundles.length === 0 ? (
          <div className="text-center py-12 text-gray-400 text-sm">
            No bundles yet.{" "}
            <Link to="/upload" className="text-indigo-600 hover:underline">
              Upload one
            </Link>{" "}
            to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 font-medium">Filename</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium min-w-[160px]">
                    Health Bar
                  </th>
                  <th className="px-5 py-3 font-medium">Score</th>
                  <th className="px-5 py-3 font-medium">Open</th>
                  <th className="px-5 py-3 font-medium">Uploaded</th>
                  <th className="px-5 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {stats.bundles.map((b) => (
                  <tr
                    key={b.bundle_id}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-5 py-3 font-medium text-gray-900 max-w-[200px] truncate">
                      {b.filename}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`px-2 py-0.5 rounded text-xs font-medium ${
                          STATUS_BADGE[b.status] ?? "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {b.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 min-w-[160px]">
                      <HealthBar findingsBySeverity={b.findings_by_severity} />
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`font-semibold ${
                          HEALTH_COLOR[b.health_color] ?? "text-gray-700"
                        }`}
                      >
                        {b.health_score}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-600">
                      {b.open_findings}
                    </td>
                    <td className="px-5 py-3 text-gray-500">
                      {new Date(b.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3">
                        <button
                          onClick={() => navigate(`/bundles/${b.bundle_id}`)}
                          className="text-indigo-600 hover:text-indigo-500 text-xs font-medium"
                        >
                          View
                        </button>
                        {isManager && (
                          <button
                            onClick={() => setConfirmTarget(b)}
                            className="text-red-400 hover:text-red-600 text-xs font-medium"
                          >
                            Delete
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Delete confirmation modal */}
      {confirmTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl border border-gray-200 p-6 max-w-md w-full mx-4">
            <h3 className="text-base font-semibold text-gray-900 mb-1">Delete bundle?</h3>
            <p className="text-sm text-gray-600 mb-1">
              You're about to permanently delete:
            </p>
            <p className="text-sm font-medium text-gray-900 bg-gray-50 border border-gray-200 rounded px-3 py-2 mb-4 break-all">
              {confirmTarget.filename}
            </p>
            <p className="text-sm text-red-600 mb-5">
              This will remove the bundle file, all parsed evidence, all findings, comments, and history. <strong>This cannot be undone.</strong>
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmTarget(null)}
                disabled={deleting}
                className="px-4 py-2 text-sm rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="px-4 py-2 text-sm rounded-md bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? "Deleting..." : "Yes, delete it"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Most Recent Critical Findings — manager only */}
      {isManager && stats.most_recent_critical.length > 0 && (
        <div className="bg-white rounded-lg border border-red-200 shadow-sm">
          <div className="px-5 py-4 border-b border-red-100 bg-red-50 rounded-t-lg">
            <h2 className="text-base font-semibold text-red-800">
              Most Recent Critical Findings
            </h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 uppercase border-b border-gray-100">
                  <th className="px-5 py-3 font-medium">Bundle</th>
                  <th className="px-5 py-3 font-medium">Finding</th>
                  <th className="px-5 py-3 font-medium">Rule</th>
                  <th className="px-5 py-3 font-medium">When</th>
                </tr>
              </thead>
              <tbody>
                {stats.most_recent_critical.map((c, i) => (
                  <tr
                    key={i}
                    className="border-b border-gray-50 hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-5 py-3">
                      <Link
                        to={`/bundles/${c.bundle_id}`}
                        className="text-indigo-600 hover:underline font-medium"
                      >
                        {c.filename}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-gray-800">
                      {c.finding_title}
                    </td>
                    <td className="px-5 py-3">
                      <span className="font-mono text-xs bg-gray-100 px-1.5 py-0.5 rounded">
                        {c.rule_id}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-500">
                      {new Date(c.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
