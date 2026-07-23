import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Legitimate mount-guard / localStorage-sync effects that cannot be lazy-
      // initialized without SSR hydration mismatches. Downgraded to a warning.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
