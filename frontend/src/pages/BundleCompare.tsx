import { useEffect, useState } from "react";
import { bundleApi, comparisonApi, type Bundle, type ComparisonResult, type FindingSummary } from "../api/client";

const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-blue-100 text-blue-800",
  info: "bg-gray-100 text-gray-700",
};

function FindingRow({ f }: { f: FindingSummary }) {
  return (
    <div className="flex items-center gap-2 py-1 border-b border-gray-100 last:border-0">
      <span
        className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase flex-shrink-0 ${
          SEVERITY_BADGE[f.severity] ?? SEVERITY_BADGE.info
        }`}
      >
        {f.severity}
      </span>
      <span className="text-sm text-gray-700 truncate">{f.title}</span>
    </div>
  );
}

export default function BundleCompare() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [bundlesLoading, setBundlesLoading] = useState(true);
  const [bundleA, setBundleA] = useState("");
  const [bundleB, setBundleB] = useState("");
  const [comparing, setComparing] = useState(false);
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    bundleApi
      .list()
      .then((res) => setBundles(res.items.filter((b) => b.status === "ready")))
      .catch((e) => console.error("Failed to load bundles", e))
      .finally(() => setBundlesLoading(false));
  }, []);

  const handleCompare = async () => {
    if (!bundleA || !bundleB) return;
    setComparing(true);
    setError(null);
    setResult(null);
    try {
      const res = await comparisonApi.compare(bundleA, bundleB);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setComparing(false);
    }
  };

  return (
    <div>
      <h1 className="text-xl font-bold text-gray-800 mb-6">Bundle Comparison</h1>

      {/* Selection */}
      <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Bundle A (baseline)</label>
            <select
              className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              value={bundleA}
              onChange={(e) => setBundleA(e.target.value)}
              disabled={bundlesLoading}
            >
              <option value="">Select bundle...</option>
              {bundles.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.original_filename}
                </option>
              ))}
            </select>
          </div>

          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs text-gray-500 mb-1">Bundle B (newer)</label>
            <select
              className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              value={bundleB}
              onChange={(e) => setBundleB(e.target.value)}
              disabled={bundlesLoading}
            >
              <option value="">Select bundle...</option>
              {bundles.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.original_filename}
                </option>
              ))}
            </select>
          </div>

          <button
            onClick={handleCompare}
            disabled={comparing || !bundleA || !bundleB}
            className="px-4 py-2 text-sm rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {comparing ? "Comparing..." : "Compare"}
          </button>
        </div>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      </div>

      {/* Results */}
      {result && (
        <div>
          {/* Summary bar */}
          <div className="mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200 text-sm text-gray-700">
            Comparing{" "}
            <span className="font-semibold">{result.bundle_a_filename}</span> vs{" "}
            <span className="font-semibold">{result.bundle_b_filename}</span>:{" "}
            <span className="text-red-600 font-semibold">{result.summary.new} new</span>,{" "}
            <span className="text-green-600 font-semibold">{result.summary.resolved} resolved</span>,{" "}
            <span className="text-yellow-600 font-semibold">{result.summary.persisting} persisting</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* New Issues */}
            <div className="bg-white rounded-lg border-2 border-red-200 shadow-sm overflow-hidden">
              <div className="bg-red-50 px-4 py-3 border-b border-red-200">
                <h2 className="font-semibold text-red-700 text-sm">
                  New Issues ({result.summary.new})
                </h2>
                <p className="text-xs text-red-500">In Bundle B, not in Bundle A</p>
              </div>
              <div className="p-4">
                {result.new_findings.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">None</p>
                ) : (
                  result.new_findings.map((f) => <FindingRow key={f.rule_id} f={f} />)
                )}
              </div>
            </div>

            {/* Resolved */}
            <div className="bg-white rounded-lg border-2 border-green-200 shadow-sm overflow-hidden">
              <div className="bg-green-50 px-4 py-3 border-b border-green-200">
                <h2 className="font-semibold text-green-700 text-sm">
                  Resolved ({result.summary.resolved})
                </h2>
                <p className="text-xs text-green-500">In Bundle A, not in Bundle B</p>
              </div>
              <div className="p-4">
                {result.resolved_findings.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">None</p>
                ) : (
                  result.resolved_findings.map((f) => <FindingRow key={f.rule_id} f={f} />)
                )}
              </div>
            </div>

            {/* Persisting */}
            <div className="bg-white rounded-lg border-2 border-yellow-200 shadow-sm overflow-hidden">
              <div className="bg-yellow-50 px-4 py-3 border-b border-yellow-200">
                <h2 className="font-semibold text-yellow-700 text-sm">
                  Persisting ({result.summary.persisting})
                </h2>
                <p className="text-xs text-yellow-600">In both bundles</p>
              </div>
              <div className="p-4">
                {result.persisting_findings.length === 0 ? (
                  <p className="text-xs text-gray-400 italic">None</p>
                ) : (
                  result.persisting_findings.map((f) => <FindingRow key={f.rule_id} f={f} />)
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
