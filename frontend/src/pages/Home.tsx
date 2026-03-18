import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { bundleApi, type Bundle } from "../api/client";
import BundleList from "../components/BundleList";

export default function Home() {
  const [bundles, setBundles] = useState<Bundle[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    bundleApi
      .list()
      .then((res) => {
        setBundles(res.items);
        setTotal(res.total);
      })
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Support Bundles</h1>
          {!loading && (
            <p className="text-sm text-gray-500 mt-0.5">{total} bundle{total !== 1 ? "s" : ""}</p>
          )}
        </div>
        <Link
          to="/upload"
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors"
        >
          Upload Bundle
        </Link>
      </div>

      {loading && (
        <div className="text-center py-16 text-gray-400">Loading bundles...</div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-4 text-sm text-red-700">
          Failed to load bundles: {error}
        </div>
      )}

      {!loading && !error && <BundleList bundles={bundles} />}
    </div>
  );
}
