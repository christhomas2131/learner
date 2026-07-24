import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PipelineProgress } from "@/features/ask/pipeline-progress";

describe("PipelineProgress mode filtering", () => {
  it("hides model stages in grounded mode (deterministic path, no permanently-greyed rows)", () => {
    render(<PipelineProgress reached={new Set()} activeStage={null} done={false} mode="grounded" />);
    expect(screen.getByText("Validating question")).toBeInTheDocument();
    expect(screen.getByText("Applying release gate")).toBeInTheDocument();
    // Model stages never run in Grounded → they must not render at all.
    expect(screen.queryByText("Drafting candidate answer")).toBeNull();
    expect(screen.queryByText("Verifying claims")).toBeNull();
  });

  it("shows model stages and marks each actor (python vs model) in premium mode", () => {
    render(<PipelineProgress reached={new Set()} activeStage={null} done={false} mode="premium" />);
    expect(screen.getByText("Drafting candidate answer")).toBeInTheDocument();
    // The deterministic-gate thesis is visible: stages are tagged by actor.
    expect(screen.getAllByText("model").length).toBeGreaterThan(0);
    expect(screen.getAllByText("python").length).toBeGreaterThan(0);
  });
});
