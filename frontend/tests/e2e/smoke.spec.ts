import { expect, test } from "@playwright/test";

test("ask a supported question and get a verified, cited answer", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /ask with confidence/i })).toBeVisible();

  await page.getByLabel("Question").fill("What is photosynthesis?");
  await page.getByRole("button", { name: /^ask/i }).click();

  // Verified verdict appears. Target the heading specifically — "Verified" also
  // appears in the sr-only a11y live region, so a bare getByText is ambiguous.
  await expect(page.getByRole("heading", { name: /verified/i })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/photosynthesis/i).first()).toBeVisible();
});

test("unsupported question abstains", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Question").fill("Who won the 2050 World Cup?");
  await page.getByRole("button", { name: /^ask/i }).click();
  await expect(page.getByRole("heading", { name: /insufficient evidence/i })).toBeVisible({ timeout: 30_000 });
});

test("knowledge library lists sources", async ({ page }) => {
  await page.goto("/library");
  await expect(page.getByRole("heading", { name: /knowledge library/i })).toBeVisible();
  await expect(page.getByText(/Introduction to Biology/i)).toBeVisible({ timeout: 15_000 });
});

test("theme can be switched in settings", async ({ page }) => {
  await page.goto("/settings");
  await page.getByRole("button", { name: "dark", exact: true }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);
});
