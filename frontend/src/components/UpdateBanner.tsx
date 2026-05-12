import { useEffect, useState } from "react";
import { updateApi, type UpdateStatus } from "../api/client";

export default function UpdateBanner() {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    let mounted = true;
    updateApi
      .getStatus()
      .then((data) => {
        if (mounted) setStatus(data);
      })
      .catch(() => {
        // Silently ignore — update check is non-critical
      });
    return () => {
      mounted = false;
    };
  }, []);

  if (!status?.available || dismissed) return null;

  // If license is invalid, show a muted warning instead of an upgrade link
  const licenseBlocked = status.license_valid === false;

  return (
    <div
      className={`px-4 py-2 text-sm flex items-center justify-between ${
        licenseBlocked
          ? "bg-yellow-50 border-b border-yellow-200 text-yellow-800"
          : "bg-blue-50 border-b border-blue-200 text-blue-800"
      }`}
      role="alert"
    >
      <div className="flex items-center gap-2">
        <span className="font-medium">
          {licenseBlocked ? "License Issue" : "Update Available"}
        </span>
        <span className="hidden sm:inline">
          {licenseBlocked
            ? `Your license is invalid. Please contact support to update to v${status.version}.`
            : `A new release (${status.version}) is available.`}
        </span>
      </div>
      <div className="flex items-center gap-3">
        {!licenseBlocked && status.notes && (
          <button
            onClick={() => alert(status.notes)}
            className="underline hover:no-underline text-xs"
          >
            Release notes
          </button>
        )}
        <button
          onClick={() => setDismissed(true)}
          className="text-xs font-medium hover:opacity-80"
          aria-label="Dismiss update banner"
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
