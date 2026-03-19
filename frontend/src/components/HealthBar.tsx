interface Props {
  findingsBySeverity: Record<string, number>;
  height?: string; // default "h-3"
  showLabels?: boolean;
}

const SEV_COLORS: Record<string, string> = {
  critical: "bg-red-600",
  high: "bg-orange-500",
  medium: "bg-yellow-400",
  low: "bg-blue-400",
  info: "bg-gray-400",
};

const SEV_ORDER = ["critical", "high", "medium", "low", "info"];

export default function HealthBar({
  findingsBySeverity,
  height = "h-3",
  showLabels = false,
}: Props) {
  const total = SEV_ORDER.reduce(
    (sum, s) => sum + (findingsBySeverity[s] ?? 0),
    0
  );

  if (total === 0) {
    return (
      <div className="flex items-center gap-2">
        <div
          className={`flex-1 ${height} rounded-full bg-green-500`}
          title="All Clear"
        />
        {showLabels && (
          <span className="text-xs text-green-600 font-medium">All Clear</span>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <div className={`flex-1 flex ${height} rounded-full overflow-hidden`}>
        {SEV_ORDER.map((sev) => {
          const count = findingsBySeverity[sev] ?? 0;
          if (count === 0) return null;
          const pct = (count / total) * 100;
          return (
            <div
              key={sev}
              className={`${SEV_COLORS[sev]} transition-all`}
              style={{ width: `${pct}%` }}
              title={`${count} ${sev.charAt(0).toUpperCase() + sev.slice(1)}`}
            />
          );
        })}
      </div>
      {showLabels && (
        <div className="flex items-center gap-1 flex-wrap">
          {SEV_ORDER.map((sev) => {
            const count = findingsBySeverity[sev] ?? 0;
            if (count === 0) return null;
            return (
              <span key={sev} className="text-xs text-gray-500">
                {count} {sev}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
