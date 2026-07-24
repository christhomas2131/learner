import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle for the Docker runtime image.
  output: "standalone",
  // Hide the Next dev route indicator — its default bottom-left position sat on
  // top of the sidebar theme toggle. Dev-only (compile/runtime errors are still
  // surfaced); production UI was never affected either way.
  devIndicators: false,
};

export default nextConfig;
