"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";

const ORDER = ["system", "light", "dark"] as const;
const ICON = { system: Monitor, light: Sun, dark: Moon };

export function ThemeToggle({ collapsed }: { collapsed?: boolean }) {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const current = (mounted ? theme : "system") as (typeof ORDER)[number];
  const Icon = ICON[current] ?? Monitor;

  return (
    <Button
      variant="ghost"
      size={collapsed ? "icon" : "sm"}
      className={collapsed ? "" : "w-full justify-start"}
      onClick={() => setTheme(ORDER[(ORDER.indexOf(current) + 1) % ORDER.length])}
      aria-label={`Theme: ${current}. Click to change.`}
    >
      <Icon className="size-4" />
      {!collapsed && <span className="capitalize">{current} theme</span>}
    </Button>
  );
}
