import { useState } from "react";
import {
  findingApi,
  evidenceApi,
  eventsApi,
  commentApi,
  type Finding,
  type FindingUpdate,
  type EvidenceRead,
  type FindingEvent,
  type Comment,
} from "../api/client";
import { useAuth } from "../context/AuthContext";

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

const EVENT_DOT: Record<string, string> = {
  status_changed: "bg-blue-500",
  note_added: "bg-gray-400",
  ai_explained: "bg-purple-500",
  created: "bg-green-500",
};

interface Props {
  finding: Finding;
  onUpdate?: (updated: Finding) => void;
}

const KIND_BADGE_COLORS: Record<string, string> = {
  Pod: "bg-blue-100 text-blue-800",
  Node: "bg-purple-100 text-purple-800",
  Event: "bg-yellow-100 text-yellow-800",
  PersistentVolumeClaim: "bg-orange-100 text-orange-800",
};

function kindBadgeClass(kind: string): string {
  return KIND_BADGE_COLORS[kind] ?? "bg-gray-100 text-gray-700";
}

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function eventDescription(event: FindingEvent): string {
  switch (event.event_type) {
    case "status_changed":
      return `changed status: ${event.old_value ?? "?"} → ${event.new_value ?? "?"}`;
    case "note_added":
      return `updated reviewer notes`;
    case "ai_explained":
      return `generated AI explanation`;
    case "created":
      return `finding created`;
    default:
      return event.event_type;
  }
}

export default function FindingCard({ finding: initialFinding, onUpdate }: Props) {
  const { user } = useAuth();
  const [finding, setFinding] = useState<Finding>(initialFinding);
  const [reviewerNotes, setReviewerNotes] = useState(finding.reviewer_notes ?? "");
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceItems, setEvidenceItems] = useState<Record<string, EvidenceRead>>({});
  const [evidenceLoading, setEvidenceLoading] = useState(false);

  // History (events)
  const [historyOpen, setHistoryOpen] = useState(false);
  const [events, setEvents] = useState<FindingEvent[] | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);

  // Comments
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);
  const [deletingCommentId, setDeletingCommentId] = useState<string | null>(null);

  const handleStatusChange = async (newStatus: "open" | "acknowledged" | "resolved") => {
    setUpdating(true);
    try {
      const update: FindingUpdate = { status: newStatus };
      const updated = await findingApi.update(finding.bundle_id, finding.id, update);
      setFinding(updated);
      onUpdate?.(updated);
      // Invalidate events cache so timeline refreshes
      setEvents(null);
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
      setEvents(null);
    } catch (e) {
      console.error("Failed to save reviewer notes", e);
    } finally {
      setUpdating(false);
    }
  };

  const handleEvidenceToggle = async () => {
    const nextOpen = !evidenceOpen;
    setEvidenceOpen(nextOpen);
    if (!nextOpen) return;

    const missing = finding.evidence_ids.filter((eid) => !(eid in evidenceItems));
    if (missing.length === 0) return;

    setEvidenceLoading(true);
    try {
      const fetched = await Promise.all(
        missing.map((eid) => evidenceApi.getEvidence(finding.bundle_id, eid))
      );
      setEvidenceItems((prev) => {
        const next = { ...prev };
        for (const item of fetched) {
          next[item.id] = item;
        }
        return next;
      });
    } catch (e) {
      console.error("Failed to fetch evidence", e);
    } finally {
      setEvidenceLoading(false);
    }
  };

  const handleExplain = async () => {
    setExplaining(true);
    setExplainError(null);
    try {
      const updated = await findingApi.explain(finding.bundle_id, finding.id);
      setFinding(updated);
      onUpdate?.(updated);
      setEvents(null);
    } catch (e: unknown) {
      setExplainError(String(e));
    } finally {
      setExplaining(false);
    }
  };

  const handleHistoryToggle = async () => {
    const nextOpen = !historyOpen;
    setHistoryOpen(nextOpen);
    if (!nextOpen || events !== null) return;

    setEventsLoading(true);
    try {
      const data = await eventsApi.getEvents(finding.bundle_id, finding.id);
      setEvents(data);
    } catch (e) {
      console.error("Failed to fetch events", e);
      setEvents([]);
    } finally {
      setEventsLoading(false);
    }
  };

  const handleCommentsToggle = async () => {
    const nextOpen = !commentsOpen;
    setCommentsOpen(nextOpen);
    if (!nextOpen || comments !== null) return;

    setCommentsLoading(true);
    try {
      const data = await commentApi.list(finding.bundle_id, finding.id);
      setComments(data);
    } catch (e) {
      console.error("Failed to fetch comments", e);
      setComments([]);
    } finally {
      setCommentsLoading(false);
    }
  };

  const handleSubmitComment = async () => {
    if (!newComment.trim()) return;
    setSubmittingComment(true);
    try {
      const created = await commentApi.create(finding.bundle_id, finding.id, newComment.trim());
      setComments((prev) => (prev ? [...prev, created] : [created]));
      setNewComment("");
    } catch (e) {
      console.error("Failed to create comment", e);
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    setDeletingCommentId(commentId);
    try {
      await commentApi.delete(finding.bundle_id, finding.id, commentId);
      setComments((prev) => (prev ? prev.filter((c) => c.id !== commentId) : prev));
    } catch (e) {
      console.error("Failed to delete comment", e);
    } finally {
      setDeletingCommentId(null);
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

      {/* Reviewed by */}
      {finding.reviewed_by && finding.status !== "open" && (
        <p className="mt-1 text-xs text-gray-400">
          {finding.status === "resolved" ? "Resolved" : "Acknowledged"} by{" "}
          <span className="font-medium text-gray-500">{finding.reviewed_by}</span>
          {finding.reviewed_at && (
            <> &middot; {new Date(finding.reviewed_at).toLocaleString()}</>
          )}
        </p>
      )}

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

      {/* Evidence */}
      {finding.evidence_ids.length > 0 && (
        <details
          className="mt-3"
          open={evidenceOpen}
          onToggle={(e) => {
            const target = e.currentTarget as HTMLDetailsElement;
            if (target.open !== evidenceOpen) {
              handleEvidenceToggle();
            }
          }}
        >
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
            Evidence ({finding.evidence_ids.length} items)
          </summary>
          <div className="mt-2">
            {evidenceLoading ? (
              <p className="text-xs text-gray-400 italic">Loading evidence...</p>
            ) : (
              <ul className="space-y-2">
                {finding.evidence_ids.map((eid) => {
                  const item = evidenceItems[eid];
                  if (!item) {
                    return (
                      <li key={eid} className="text-xs font-mono bg-white rounded border border-gray-200 px-2 py-1 text-gray-400">
                        {eid}
                      </li>
                    );
                  }
                  return (
                    <li key={eid} className="bg-white rounded border border-gray-200 p-2">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={`px-2 py-0.5 rounded text-xs font-medium ${kindBadgeClass(item.kind)}`}
                        >
                          {item.kind}
                        </span>
                        <span className="text-xs font-medium text-gray-800">
                          {item.namespace ? `${item.namespace}/${item.name}` : item.name}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-gray-400">{item.source_path}</p>
                      <details className="mt-1">
                        <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
                          Raw JSON
                        </summary>
                        <pre className="text-xs bg-gray-900 text-green-400 p-3 rounded overflow-auto max-h-64 mt-1">
                          {JSON.stringify(item.raw_data, null, 2)}
                        </pre>
                      </details>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
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

      {/* History (Events Timeline) */}
      <details
        className="mt-3"
        open={historyOpen}
        onToggle={(e) => {
          const target = e.currentTarget as HTMLDetailsElement;
          if (target.open !== historyOpen) {
            handleHistoryToggle();
          }
        }}
      >
        <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
          History
        </summary>
        <div className="mt-2">
          {eventsLoading ? (
            <p className="text-xs text-gray-400 italic">Loading history...</p>
          ) : events && events.length === 0 ? (
            <p className="text-xs text-gray-400 italic">No events yet.</p>
          ) : (
            <ul className="space-y-2 pl-1">
              {(events ?? []).map((ev) => (
                <li key={ev.id} className="flex items-start gap-2">
                  <span
                    className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${
                      EVENT_DOT[ev.event_type] ?? "bg-gray-300"
                    }`}
                  />
                  <div className="text-xs text-gray-700">
                    <span className="font-semibold">{ev.actor}</span>{" "}
                    {eventDescription(ev)}{" "}
                    <span className="text-gray-400">{timeAgo(ev.created_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </details>

      {/* Comments */}
      <details
        className="mt-3"
        open={commentsOpen}
        onToggle={(e) => {
          const target = e.currentTarget as HTMLDetailsElement;
          if (target.open !== commentsOpen) {
            handleCommentsToggle();
          }
        }}
      >
        <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
          Comments {comments !== null ? `(${comments.length})` : ""}
        </summary>
        <div className="mt-2 space-y-2">
          {commentsLoading ? (
            <p className="text-xs text-gray-400 italic">Loading comments...</p>
          ) : (
            <>
              {(comments ?? []).length === 0 ? (
                <p className="text-xs text-gray-400 italic">No comments yet.</p>
              ) : (
                <ul className="space-y-2">
                  {(comments ?? []).map((c) => {
                    const isOwn = user?.email === c.actor;
                    const isManager = user?.role === "manager" || user?.role === "admin";
                    const canDelete = isOwn || isManager;
                    return (
                      <li key={c.id} className="bg-white rounded border border-gray-200 p-2">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs font-semibold text-gray-700">{c.actor}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400">{timeAgo(c.created_at)}</span>
                            {canDelete && (
                              <button
                                onClick={() => handleDeleteComment(c.id)}
                                disabled={deletingCommentId === c.id}
                                className="text-xs text-red-400 hover:text-red-600 disabled:opacity-50"
                              >
                                Delete
                              </button>
                            )}
                          </div>
                        </div>
                        <p className="mt-1 text-xs text-gray-600 whitespace-pre-wrap">{c.body}</p>
                      </li>
                    );
                  })}
                </ul>
              )}
              {/* New comment input */}
              <div className="mt-2">
                <textarea
                  rows={2}
                  className="w-full text-xs border border-gray-200 rounded px-2 py-1 text-gray-700 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300 resize-none"
                  placeholder="Add a comment..."
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
                />
                <button
                  onClick={handleSubmitComment}
                  disabled={submittingComment || !newComment.trim()}
                  className="mt-1 px-3 py-1 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
                >
                  {submittingComment ? "Posting..." : "Add Comment"}
                </button>
              </div>
            </>
          )}
        </div>
      </details>
    </div>
  );
}
