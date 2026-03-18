import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { bundleApi, type Bundle } from "../api/client";
import FindingCard, { type Finding } from "../components/FindingCard";

const STATUS_COLORS: Record<string, string> = {
  uploaded: "bg-blue-100 text-blue-800",
  processing: "bg-yellow-100 text-yellow-800",
  ready: "bg-green-100 text-green-800",
  error: "bg-red-100 text-red-800",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Placeholder findings — Phase 2+ will populate these from the analysis engine
const PLACEHOLDER_FINDINGS: Finding[] = [];

export default function BundleDetail() {
  const { id } = useParams<{ id: string }>();
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;

    let cancelled = false;

    function poll() {
      if (cancelled) return;
      bundleApi
        .get(id!)
        .then((b) => {
          if (!cancelled) {
            setBundle(b);
            setLoading(false);
            // Keep polling while processing
            if (b.status === "uploaded" || b.status === "processing") {
              setTimeout(poll, 2000);
            }
          }
        })
        .catch((e: unknown) => {
          if (!cancelled) {
            setError(String(e));
            setLoading(false);
          }
        });
    }

    poll();
    return () => {
      cancelled = true;
    };
  }, [id]);

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
            <p className="text-sm text-gray-400 mt-0.5">ID: {bundle.id}</p>
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

        {(bundle.status === "uploaded" || bundle.status === "processing") && (
          <div className="mt-4 flex items-center gap-2 text-sm text-yellow-700 bg-yellow-50 border border-yellow-200 rounded-md p-3">
            <div className="h-4 w-4 rounded-full border-2 border-yellow-400 border-t-yellow-700 animate-spin shrink-0" />
            Analyzing bundle... This page will update automatically.
          </div>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Findings</h2>
        {bundle.status !== "ready" ? (
          <p className="text-sm text-gray-400">
            Findings will appear here once analysis is complete.
          </p>
        ) : PLACEHOLDER_FINDINGS.length === 0 ? (
          <p className="text-sm text-gray-400">No findings yet — analysis engine coming in Phase 2.</p>
        ) : (
          <div className="space-y-3">
            {PLACEHOLDER_FINDINGS.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
