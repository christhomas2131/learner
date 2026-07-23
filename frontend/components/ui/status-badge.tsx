import {
  AlertOctagon,
  CheckCircle2,
  Clock,
  GitCompareArrows,
  HelpCircle,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CLAIM_STATUS, TONE_CLASSES, TOP_LEVEL_STATUS } from "@/lib/verification";
import type { ClaimStatus, TopLevelStatus } from "@/lib/api/schemas";

const ICONS: Record<string, LucideIcon> = {
  check: CheckCircle2,
  help: HelpCircle,
  conflict: GitCompareArrows,
  alert: AlertOctagon,
  clock: Clock,
};

export function StatusBadge({
  status,
  kind = "top",
  size = "md",
  className,
}: {
  status: TopLevelStatus | ClaimStatus;
  kind?: "top" | "claim";
  size?: "sm" | "md";
  className?: string;
}) {
  const style =
    kind === "top"
      ? TOP_LEVEL_STATUS[status as TopLevelStatus]
      : CLAIM_STATUS[status as ClaimStatus];
  const Icon = ICONS[style.icon];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border font-medium",
        TONE_CLASSES[style.tone],
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        className,
      )}
    >
      <Icon className={size === "sm" ? "size-3.5" : "size-4"} aria-hidden />
      {style.label}
    </span>
  );
}
