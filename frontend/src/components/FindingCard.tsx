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
import { useToast } from "../context/ToastContext";

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
      if (event.new_value === "open") {
        return `reopened (was: ${event.old_value ?? "?"})`;
      }
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

/** Minimal markdown renderer for AI explanation output */
function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;

  function inlineFormat(line: string, key: string): React.ReactNode {
    // Bold **text** and inline `code`
    const parts = line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return (
      <span key={key}>
        {parts.map((part, j) => {
          if (part.startsWith("**") && part.endsWith("**"))
            return <strong key={j}>{part.slice(2, -2)}</strong>;
          if (part.startsWith("`") && part.endsWith("`"))
            return <code key={j} className="bg-gray-100 px-1 rounded text-xs font-mono">{part.slice(1, -1)}</code>;
          return part;
        })}
      </span>
    );
  }

  while (i < lines.length) {
    const line = lines[i];

    // Fenced code block
    if (line.trim().startsWith("```")) {
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <pre key={i} className="bg-gray-900 text-green-300 text-xs rounded p-3 overflow-x-auto my-2 whitespace-pre">
          {codeLines.join("\n")}
        </pre>
      );
      i++;
      continue;
    }

    // Headings
    const h2 = line.match(/^##\s+(.*)/);
    const h3 = line.match(/^###\s+(.*)/);
    if (h2) {
      nodes.push(<h2 key={i} className="text-sm font-bold text-gray-800 mt-3 mb-1">{h2[1]}</h2>);
      i++; continue;
    }
    if (h3) {
      nodes.push(<h3 key={i} className="text-xs font-semibold text-gray-700 mt-2 mb-0.5">{h3[1]}</h3>);
      i++; continue;
    }

    // Numbered list item
    const li = line.match(/^(\d+)\.\s+(.*)/);
    if (li) {
      nodes.push(
        <div key={i} className="flex gap-2 text-sm text-gray-700 mt-1">
          <span className="shrink-0 font-medium text-gray-500">{li[1]}.</span>
          <span>{inlineFormat(li[2], `li-${i}`)}</span>
        </div>
      );
      i++; continue;
    }

    // Bullet list item
    const bullet = line.match(/^[-*]\s+(.*)/);
    if (bullet) {
      nodes.push(
        <div key={i} className="flex gap-2 text-sm text-gray-700 mt-1 ml-2">
          <span className="shrink-0 text-gray-400">&bull;</span>
          <span>{inlineFormat(bullet[1], `bullet-${i}`)}</span>
        </div>
      );
      i++; continue;
    }

    // Empty line
    if (line.trim() === "") {
      nodes.push(<div key={i} className="h-1" />);
      i++; continue;
    }

    // Normal paragraph
    nodes.push(<p key={i} className="text-sm text-gray-700 mt-1">{inlineFormat(line, `p-${i}`)}</p>);
    i++;
  }

  return nodes;
}

/** Animated expand wrapper using CSS grid trick */
function ExpandSection({ open, children }: { open: boolean; children: React.ReactNode }) {
  return (
    <div
      className={`grid transition-all duration-200 ease-out ${
        open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
      }`}
    >
      <div className="overflow-hidden">{children}</div>
    </div>
  );
}

/** Section toggle button replacing <summary> */
function SectionToggle({
  open,
  onClick,
  label,
}: {
  open: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-1 rounded"
    >
      <svg
        className={`w-3 h-3 transition-transform duration-150 ${open ? "rotate-90" : ""}`}
        fill="currentColor"
        viewBox="0 0 20 20"
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
          clipRule="evenodd"
        />
      </svg>
      {label}
    </button>
  );
}

export default function FindingCard({ finding: initialFinding, onUpdate }: Props) {
  const { user } = useAuth();
  const { showToast } = useToast();
  const isManager = user?.role === "manager" || user?.role === "admin";
  const [finding, setFinding] = useState<Finding>(initialFinding);
  const [explaining, setExplaining] = useState(false);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [updating, setUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceItems, setEvidenceItems] = useState<Record<string, EvidenceRead>>({});
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceFetched, setEvidenceFetched] = useState(false);

  const [historyOpen, setHistoryOpen] = useState(false);
  const [events, setEvents] = useState<FindingEvent[] | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);

  const [commentsOpen, setCommentsOpen] = useState(false);
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);
  const [deletingCommentId, setDeletingCommentId] = useState<string | null>(null);

  const handleStatusChange = async (newStatus: "open" | "acknowledged" | "resolved") => {
    setUpdating(true);
    setUpdateError(null);
    try {
      const update: FindingUpdate = { status: newStatus };
      const updated = await findingApi.update(finding.bundle_id, finding.id, update);
      setFinding(updated);
      onUpdate?.(updated);
      setEvents(null);
      const label =
        newStatus === "resolved"
          ? "Finding marked as resolved"
          : newStatus === "acknowledged"
          ? "Finding acknowledged"
          : "Finding reopened";
      showToast(label, newStatus === "open" ? "info" : "success");
    } catch (e) {
      setUpdateError("Failed to update status. Please try again.");
    } finally {
      setUpdating(false);
    }
  };

  const handleEvidenceToggle = async () => {
    const nextOpen = !evidenceOpen;
    setEvidenceOpen(nextOpen);
    if (!nextOpen || evidenceFetched) return;

    const missing = finding.evidence_ids.filter((eid) => !(eid in evidenceItems));
    if (missing.length === 0) { setEvidenceFetched(true); return; }

    setEvidenceLoading(true);
    try {
      const fetched = await Promise.all(
        missing.map((eid) => evidenceApi.getEvidence(finding.bundle_id, eid))
      );
      setEvidenceItems((prev) => {
        const next = { ...prev };
        for (const item of fetched) next[item.id] = item;
        return next;
      });
      setEvidenceFetched(true);
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
      className={`rounded-lg border-l-4 p-4 shadow-sm hover:shadow-md transition-shadow duration-200 ${
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
            className={`px-2 py-0.5 rounded text-xs font-medium transition-colors duration-150 ${
              STATUS_BADGE[finding.status] ?? "bg-gray-50 text-gray-700 border border-gray-200"
            }`}
          >
            {finding.status}
          </span>
        </div>
      </div>

      {/* Reviewed by */}
      {finding.reviewed_by && finding.status !== "open" && (
        <p className="mt-1 text-xs text-gray-500">
          {finding.status === "resolved" ? "Resolved" : "Acknowledged"} by{" "}
          <span className="font-medium text-gray-600">{finding.reviewed_by}</span>
          {finding.reviewed_at && (
            <> &middot; {new Date(finding.reviewed_at + (finding.reviewed_at.endsWith("Z") ? "" : "Z")).toLocaleString()}</>
          )}
        </p>
      )}

      {/* Summary */}
      <p className="mt-2 text-sm text-gray-600">{finding.summary}</p>

      {/* Status update error */}
      {updateError && (
        <div className="mt-2 rounded bg-red-50 border border-red-200 px-3 py-1.5 text-xs text-red-700">
          {updateError}
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-3 flex flex-wrap gap-2">
        {finding.status !== "acknowledged" && (
          <button
            disabled={updating}
            onClick={() => handleStatusChange("acknowledged")}
            className="px-3 py-1 text-xs rounded border border-yellow-300 text-yellow-700 hover:bg-yellow-100 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-yellow-400 focus-visible:ring-offset-1 transition-colors duration-150"
          >
            Acknowledge
          </button>
        )}
        {isManager && finding.status !== "resolved" && (
          <button
            disabled={updating}
            onClick={() => handleStatusChange("resolved")}
            className="px-3 py-1 text-xs rounded border border-green-300 text-green-700 hover:bg-green-100 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-400 focus-visible:ring-offset-1 transition-colors duration-150"
          >
            Resolve
          </button>
        )}
        {!isManager && finding.status !== "resolved" && (
          <button
            disabled
            title="Manager role required to resolve findings"
            className="px-3 py-1 text-xs rounded border border-gray-200 text-gray-400 cursor-not-allowed flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path
                fillRule="evenodd"
                d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
                clipRule="evenodd"
              />
            </svg>
            Resolve
          </button>
        )}
        {finding.status !== "open" && (
          <button
            disabled={updating}
            onClick={() => handleStatusChange("open")}
            className="px-3 py-1 text-xs rounded border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-1 transition-colors duration-150"
          >
            Reopen
          </button>
        )}
        {!finding.ai_explanation && !explaining && (
          <button
            onClick={handleExplain}
            className="px-3 py-1 text-xs rounded border border-indigo-300 text-indigo-700 hover:bg-indigo-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-1 transition-colors duration-150"
          >
            Get AI Explanation
          </button>
        )}
        {explaining && (
          <span className="px-3 py-1 text-xs text-indigo-500 italic flex items-center gap-1.5">
            <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Getting AI explanation...
          </span>
        )}
      </div>

      {explainError && (
        <p className="mt-2 text-xs text-red-600">{explainError}</p>
      )}

      {/* AI Explanation */}
      {finding.ai_explanation && (
        <div className="mt-3 rounded border border-indigo-100 overflow-hidden">
          <div className="bg-indigo-50 px-3 py-2 text-xs font-medium text-indigo-700">
            AI Explanation
          </div>
          <div className="bg-white p-3 space-y-1">
            {renderMarkdown(finding.ai_explanation)}
            {finding.ai_remediation && (
              <>
                <div className="h-2" />
                {renderMarkdown(finding.ai_remediation)}
              </>
            )}
          </div>
        </div>
      )}

      {/* Evidence */}
      {finding.evidence_ids.length > 0 && (
        <div className="mt-3">
          <SectionToggle
            open={evidenceOpen}
            onClick={handleEvidenceToggle}
            label={`Evidence (${finding.evidence_ids.length} items)`}
          />
          <ExpandSection open={evidenceOpen}>
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
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${kindBadgeClass(item.kind)}`}>
                            {item.kind}
                          </span>
                          <span className="text-xs font-medium text-gray-800">
                            {item.namespace ? `${item.namespace}/${item.name}` : item.name}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-gray-400">{item.source_path}</p>
                        <div className="mt-1">
                          <SectionToggle open={false} onClick={() => {}} label="Raw JSON" />
                          <pre className="text-xs bg-gray-900 text-green-400 p-3 rounded overflow-auto max-h-64 mt-1">
                            {JSON.stringify(item.raw_data, null, 2)}
                          </pre>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </ExpandSection>
        </div>
      )}

      {/* History */}
      <div className="mt-3">
        <SectionToggle
          open={historyOpen}
          onClick={handleHistoryToggle}
          label="History"
        />
        <ExpandSection open={historyOpen}>
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
        </ExpandSection>
      </div>

      {/* Comments */}
      <div className="mt-3">
        <SectionToggle
          open={commentsOpen}
          onClick={handleCommentsToggle}
          label={`Comments${comments !== null ? ` (${comments.length})` : ""}`}
        />
        <ExpandSection open={commentsOpen}>
          <div className="mt-2 space-y-2">
            {commentsLoading ? (
              <p className="text-xs text-gray-400 italic">Loading comments...</p>
            ) : (
              <>
                {(comments ?? []).length === 0 ? (
                  <p className="text-xs text-gray-400 italic">No comments yet. Be the first to comment.</p>
                ) : (
                  <ul className="space-y-2">
                    {(comments ?? []).map((c) => {
                      const isOwn = user?.email === c.actor;
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
                                  className="text-xs text-red-400 hover:text-red-600 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-red-400 rounded"
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
                <div className="mt-2">
                  <textarea
                    rows={2}
                    className="w-full text-xs border border-gray-200 rounded px-2 py-1 text-gray-700 bg-white focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-300 focus-visible:ring-offset-1 resize-none transition-shadow duration-150"
                    placeholder="Add a comment..."
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmitComment();
                    }}
                  />
                  <button
                    onClick={handleSubmitComment}
                    disabled={submittingComment || !newComment.trim()}
                    className="mt-1 px-3 py-1 text-xs rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-1 transition-colors duration-150"
                  >
                    {submittingComment ? "Posting..." : "Add Comment"}
                  </button>
                </div>
              </>
            )}
          </div>
        </ExpandSection>
      </div>
    </div>
  );
}
