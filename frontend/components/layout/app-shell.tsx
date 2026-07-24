"use client";

import * as React from "react";
import { Menu, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Sidebar } from "@/components/layout/sidebar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = React.useState(false);
  const [mobileOpen, setMobileOpen] = React.useState(false);

  // Close the mobile drawer when the layout switches to desktop.
  React.useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const onChange = () => mq.matches && setMobileOpen(false);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return (
    <div className="flex h-dvh w-full overflow-hidden">
      {/* Desktop / tablet sidebar */}
      <aside
        className={cn(
          "hidden shrink-0 border-r border-border bg-subtle md:block",
          collapsed ? "w-16" : "w-72",
        )}
      >
        <div className="flex h-full flex-col">
          <div className="flex-1 overflow-hidden">
            <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
          </div>
          <div className="border-t border-border p-3">
            <ThemeToggle collapsed={collapsed} />
          </div>
        </div>
      </aside>

      {/* Mobile drawer — Radix Sheet gives focus trap, Escape, scroll lock, and focus
          restoration that the previous hand-rolled overlay lacked. */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <SheetContent side="left" hideClose className="w-72 bg-subtle p-0">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SheetDescription className="sr-only">
            Sessions, knowledge library, progress, and settings.
          </SheetDescription>
          <div className="flex h-full flex-col">
            <div className="flex-1 overflow-hidden">
              <Sidebar collapsed={false} onToggle={() => setMobileOpen(false)} />
            </div>
            <div className="border-t border-border p-3">
              <ThemeToggle />
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* Mobile top bar */}
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-4 md:hidden">
          <Button variant="ghost" size="icon" onClick={() => setMobileOpen(true)} aria-label="Open navigation">
            <Menu className="size-5" />
          </Button>
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-4 text-primary" />
            <span className="font-semibold">Learner</span>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  );
}
