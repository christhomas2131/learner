/**
 * Centralized verification-state mapping. The single source of truth for how
 * top-level statuses and claim statuses render. Never communicate status by
 * color alone — every mapping carries a label + icon name.
 */
import type { ClaimStatus, TopLevelStatus } from "@/lib/api/schemas";

export interface StatusStyle {
  label: string;
  icon: "check" | "help" | "conflict" | "alert" | "clock";
  /** token color family used for text/border/subtle-bg */
  tone: "verified" | "insufficient" | "contradiction" | "error";
  description: string;
}

export const TOP_LEVEL_STATUS: Record<TopLevelStatus, StatusStyle> = {
  VERIFIED: {
    label: "Verified",
    icon: "check",
    tone: "verified",
    description: "Every material claim is supported by an approved source.",
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient Evidence",
    icon: "help",
    tone: "insufficient",
    description:
      "The approved materials do not contain enough evidence to answer reliably. Absence of evidence does not prove any claim false.",
  },
  CONTRADICTION: {
    label: "Contradiction Detected",
    icon: "conflict",
    tone: "contradiction",
    description: "Approved sources conflict. No single answer was selected.",
  },
  ERROR: {
    label: "Error",
    icon: "alert",
    tone: "error",
    description: "Verification could not complete safely.",
  },
  NEEDS_SOURCES: {
    label: "Sources to Review",
    icon: "help",
    tone: "insufficient",
    description:
      "Not in your approved materials yet — but candidate web sources were found for you to validate. Approve the ones you trust to add them and get a verified answer.",
  },
};

export const CLAIM_STATUS: Record<ClaimStatus, StatusStyle> = {
  SUPPORTED: {
    label: "Supported",
    icon: "check",
    tone: "verified",
    description: "A cited approved passage supports this claim.",
  },
  INSUFFICIENT_EVIDENCE: {
    label: "Insufficient Evidence",
    icon: "help",
    tone: "insufficient",
    description:
      "No approved passage supports this claim. Absence of evidence does not prove it false.",
  },
  CONTRADICTED: {
    label: "Contradicted",
    icon: "conflict",
    tone: "contradiction",
    description: "A cited approved passage contradicts this claim.",
  },
};

/** Tailwind classes per tone (text, border, subtle background). */
export const TONE_CLASSES: Record<StatusStyle["tone"], string> = {
  verified: "text-verified border-verified/30 bg-verified-subtle",
  insufficient: "text-insufficient border-insufficient/30 bg-insufficient-subtle",
  contradiction: "text-contradiction border-contradiction/30 bg-contradiction-subtle",
  error: "text-error border-error/30 bg-error-subtle",
};
