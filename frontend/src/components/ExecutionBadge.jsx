import { executionLabel } from "../api/client";

export default function ExecutionBadge({ status = "pending", compact = false }) {
  const normalized = status || "pending";
  return (
    <span className={`execution-badge execution-${normalized} ${compact ? "compact" : ""}`}>
      <span aria-hidden="true" />
      {executionLabel(normalized)}
    </span>
  );
}
