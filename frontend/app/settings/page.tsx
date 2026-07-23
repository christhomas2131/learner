"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";

function useLocalFlag(key: string, initial = false) {
  const [value, setValue] = React.useState(initial);
  React.useEffect(() => {
    setValue(localStorage.getItem(key) === "1");
  }, [key]);
  const update = (v: boolean) => {
    setValue(v);
    localStorage.setItem(key, v ? "1" : "0");
  };
  return [value, update] as const;
}

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  const [reducedMotion, setReducedMotion] = useLocalFlag("reduce-motion");
  const [diagnostics, setDiagnostics] = useLocalFlag("dev-diagnostics");
  const [fontSize, setFontSize] = React.useState("md");

  React.useEffect(() => setMounted(true), []);
  const activeTheme = mounted ? theme : undefined;

  React.useEffect(() => {
    document.documentElement.classList.toggle("reduce-motion", reducedMotion);
  }, [reducedMotion]);

  React.useEffect(() => {
    const stored = localStorage.getItem("font-size") ?? "md";
    setFontSize(stored);
  }, []);

  React.useEffect(() => {
    const map: Record<string, string> = { sm: "15px", md: "16px", lg: "18px" };
    document.documentElement.style.fontSize = map[fontSize] ?? "16px";
    localStorage.setItem("font-size", fontSize);
  }, [fontSize]);

  return (
    <div className="mx-auto h-full w-full max-w-2xl space-y-4 overflow-y-auto scroll-slim p-5 md:p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Personal preferences, stored locally.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Appearance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm">Theme</span>
            <div className="flex gap-1">
              {(["system", "light", "dark"] as const).map((t) => (
                <Button
                  key={t}
                  size="sm"
                  variant={activeTheme === t ? "secondary" : "ghost"}
                  onClick={() => setTheme(t)}
                  className="capitalize"
                >
                  {t}
                </Button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Font size</span>
            <div className="flex gap-1">
              {(["sm", "md", "lg"] as const).map((s) => (
                <Button
                  key={s}
                  size="sm"
                  variant={fontSize === s ? "secondary" : "ghost"}
                  onClick={() => setFontSize(s)}
                  className="uppercase"
                >
                  {s}
                </Button>
              ))}
            </div>
          </div>
          <label className="flex items-center justify-between">
            <span className="text-sm">Reduced motion</span>
            <Switch checked={reducedMotion} onCheckedChange={setReducedMotion} />
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Developer</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <label className="flex items-center justify-between">
            <span>
              <span className="block text-sm">Developer diagnostics</span>
              <span className="block text-xs text-muted-foreground">
                Show safe request/audit metadata. Never exposes prompts, keys, or model reasoning.
              </span>
            </span>
            <Switch checked={diagnostics} onCheckedChange={setDiagnostics} />
          </label>
        </CardContent>
      </Card>

      <p className="text-xs text-muted-foreground">
        This is a personal, single-user local deployment. No account, no login.
      </p>
    </div>
  );
}
