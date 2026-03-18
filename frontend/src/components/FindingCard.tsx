export interface Finding {
  id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  summary: string;
  evidence: string[];
}

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

interface Props {
  finding: Finding;
}

export default function FindingCard({ finding }: Props) {
  return (
    <div
      className={`rounded-lg border-l-4 p-4 shadow-sm ${
        SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.info
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold text-gray-800">{finding.title}</h3>
        <span
          className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-medium uppercase ${
            SEVERITY_BADGE[finding.severity] ?? SEVERITY_BADGE.info
          }`}
        >
          {finding.severity}
        </span>
      </div>
      <p className="mt-2 text-sm text-gray-600">{finding.summary}</p>
      {finding.evidence.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
            Evidence ({finding.evidence.length} items)
          </summary>
          <ul className="mt-2 space-y-1">
            {finding.evidence.map((e, i) => (
              <li
                key={i}
                className="text-xs font-mono bg-white rounded border border-gray-200 px-2 py-1 text-gray-700"
              >
                {e}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
