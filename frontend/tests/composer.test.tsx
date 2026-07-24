import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Composer } from "@/features/ask/composer";

function renderComposer(props: Partial<React.ComponentProps<typeof Composer>> = {}) {
  const onSubmit = vi.fn();
  // Composer reads worker status via React Query, so it needs a client.
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <Composer onSubmit={onSubmit} streaming={false} {...props} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
  return { onSubmit };
}

describe("Composer", () => {
  it("disables Ask with an empty question and enables it after typing", async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderComposer();
    const ask = screen.getByRole("button", { name: /ask/i });
    expect(ask).toBeDisabled();

    await user.type(screen.getByLabelText("Question"), "What is photosynthesis?");
    expect(ask).toBeEnabled();
    await user.click(ask);
    expect(onSubmit).toHaveBeenCalledWith("What is photosynthesis?", "grounded");
  });

  it("shows a character counter", () => {
    renderComposer();
    expect(screen.getByText(/0\/4000/)).toBeInTheDocument();
  });
});
