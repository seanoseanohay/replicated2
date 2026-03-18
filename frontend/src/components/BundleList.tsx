import { Link } from "react-router-dom";
import type { Bundle } from "../api/client";

interface Props {
  bundles: Bundle[];
}

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

export default function BundleList({ bundles }: Props) {
  if (bundles.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-lg">No bundles yet.</p>
        <p className="text-sm mt-1">Upload a support bundle to get started.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Filename</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Size</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Status</th>
            <th className="px-4 py-3 text-left font-semibold text-gray-600">Uploaded</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {bundles.map((b) => (
            <tr key={b.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <Link
                  to={`/bundles/${b.id}`}
                  className="text-indigo-600 hover:underline font-medium"
                >
                  {b.original_filename}
                </Link>
              </td>
              <td className="px-4 py-3 text-gray-500">{formatBytes(b.size_bytes)}</td>
              <td className="px-4 py-3">
                <span
                  className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                    STATUS_COLORS[b.status] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {b.status}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-500">
                {new Date(b.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
