import { describe, expect, it } from "vitest";
import { CLAIM_STATUS, TOP_LEVEL_STATUS } from "@/lib/verification";

describe("verification mapping", () => {
  it("maps every top-level status to a label + icon + tone", () => {
    for (const status of ["VERIFIED", "INSUFFICIENT_EVIDENCE", "CONTRADICTION", "ERROR"] as const) {
      const s = TOP_LEVEL_STATUS[status];
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.icon).toBeTruthy();
      expect(s.tone).toBeTruthy();
    }
  });

  it("insufficient evidence explains absence-of-evidence", () => {
    expect(CLAIM_STATUS.INSUFFICIENT_EVIDENCE.description.toLowerCase()).toContain(
      "does not prove",
    );
  });
});
