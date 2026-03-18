import { useState } from "react";
import { findingApi, type Finding, type FindingUpdate } from "../api/client";

export type { Finding };

const SEVERITY_STYLES: Record<string, string> = {
  critical: "border-red-500 bg-red-50",
  high: "border-orange-400 bg-orange-50",
  medium: "border-yellow-400 bg-yellow-50",
  low: "border-blue-400 bg-blue-50",
  info: "border-gray-300 bg-gray-50",
};

const SEVERITY_BADGE: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-blue-100 text-blue-800",
  info: "bg-gray-100 text-gray-700",
};

const STATUS_BADGE: Record<string, string> = {
  open: "bg-red-50 text-red-700 border border-red-200",
  acknowledged: "bg-yellow-50 text-yellow-700 border border-yellow-200",
  resolved: "bg-green-50 text-green-700 border border-green-200",
};

interface Props {
  finding: Finding;
  onUpdate?: (updated: Finding) => void;
}

export default function FindingCard({ finding: initialFinding, onUpdate }: Props) {
  const [finding, setFinding] = useState<Finding>(initialFinding);
  const [reviewerNotes, setReviewerNotes] = useState(finding.reviewer_notes ?? "");
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);

  const handleStatusChange = async (newStatus: "open" | "acknowledged" | "resolved") => {
    setUpdating(true);
    try {
      const update: FindingUpdate = { status: newStatus };
      const updated = await findingApi.update(finding.bundle_id, finding.id, update);
      setFinding(updated);
      onUpdate?.(updated);
    } catch (e) {
      console.error("Failed to update finding status", e);
    } finally {
      setUpdating(false);
    }
  };

  const handleNotesBlur = async () => {
    if (reviewerNotes === (finding.reviewer_notes ?? "")) return;
    setUpdating(true);
    try {
      const update: FindingUpdate = { reviewer_notes: reviewerNotes };
      const updated = await findingApi.update(finding.bundle_id, finding.id, update);
      setFinding(updated);
      onUpdate?.(updated);
    } catch (e) {
      console.error("Failed to save reviewer notes", e);
    } finally {
      setUpdating(false);
    }
  };

  const handleExplain = async () => {
    setExplaining(true);
    setExplainError(null);
    try {
      const updated = await findingApi.explain(finding.bundle_id, finding.id);
      setFinding(updated);
      onUpdate?.(updated);
    } catch (e: unknown) {
      setExplainError(String(e));
    } finally {
      setExplaining(false);
    }
  };

  return (
    <div
      className={`rounded-lg border-l-4 p-4 shadow-sm ${
        SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.info
      }`}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-2 flex-wrap">
        <h3 className="font-semibold text-gray-800">{finding.title}</h3>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase ${
              SEVERITY_BADGE[finding.severity] ?? SEVERITY_BADGE.info
            }`}
          >
            {finding.severity}
          </span>
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              STATUS_BADGE[finding.status] ?? "bg-gray-50 text-gray-700 border border-gray-200"
            }`}
          >
            {finding.status}
          </span>
        </div>
      </div>

      {/* Summary */}
      <p className="mt-2 text-sm text-gray-600">{finding.summary}</p>

      {/* Action buttons */}
      <div className="mt-3 flex flex-wrap gap-2">
        {finding.status !== "acknowledged" && (
          <button
            disabled={updating}
            onClick={() => handleStatusChange("acknowledged")}
            className="px-3 py-1 text-xs rounded border border-yellow-300 text-yellow-700 hover:bg-yellow-100 disabled:opacity-50"
          >
            Acknowledge
          </button>
        )}
        {finding.status !== "resolved" && (
          <button
            disabled={updating}
            onClick={() => handleStatusChange("resolved")}
            className="px-3 py-1 text-xs rounded border border-green-300 text-green-700 hover:bg-green-100 disabled:opacity-50"
          >
            Resolve
          </button>
        )}
        {finding.status !== "open" && (
          <button
            disabled={updating}
            onClick={() => handleStatusChange("open")}
            className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50"
          >
            Reopen
          </button>
        )}
        {!finding.ai_explanation && !explaining && (
          <button
            onClick={handleExplain}
            className="px-3 py-1 text-xs rounded border border-indigo-300 text-indigo-700 hover:bg-indigo-50"
          >
            Get AI Explanation
          </button>
        )}
        {explaining && (
          <span className="px-3 py-1 text-xs text-indigo-500 italic">
            Getting AI explanation...
          </span>
        )}
      </div>

      {explainError && (
        <p className="mt-2 text-xs text-red-600">{explainError}</p>
      )}

      {/* AI Explanation */}
      {finding.ai_explanation && (
        <details className="mt-3" open>
          <summary className="cursor-pointer text-xs font-medium text-indigo-700 hover:text-indigo-900">
            AI Explanation
          </summary>
          <div className="mt-2 text-sm text-gray-700 bg-white rounded border border-indigo-100 p-3 space-y-2">
            <p>{finding.ai_explanation}</p>
            {finding.ai_remediation && (
              <>
                <p className="font-medium text-gray-800">Remediation Steps</p>
                <p className="whitespace-pre-wrap">{finding.ai_remediation}</p>
              </>
            )}
          </div>
        </details>
      )}

      {/* Evidence IDs */}
      {finding.evidence_ids.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
            Evidence ({finding.evidence_ids.length} items)
          </summary>
          <ul className="mt-2 space-y-1">
            {finding.evidence_ids.map((eid) => (
              <li
                key={eid}
                className="text-xs font-mono bg-white rounded border border-gray-200 px-2 py-1 text-gray-700"
              >
                {eid}
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Reviewer Notes */}
      <div className="mt-3">
        <label className="block text-xs text-gray-500 mb-1">Reviewer Notes</label>
        <textarea
          rows={2}
          className="w-full text-xs border border-gray-200 rounded px-2 py-1 text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300 resize-none"
          placeholder="Add notes..."
          value={reviewerNotes}
          onChange={(e) => setReviewerNotes(e.target.value)}
          onBlur={handleNotesBlur}
        />
      </div>
    </div>
  );
}
