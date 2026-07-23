"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  ChevronLeft,
  LibraryBig,
  LineChart,
  PanelLeft,
  Plus,
  Search,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { cn, formatRelative } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useSessions } from "@/lib/api/hooks";

const NAV = [
  { href: "/", label: "New session", icon: Plus, exact: true },
  { href: "/library", label: "Knowledge library", icon: LibraryBig },
  { href: "/progress", label: "Progress", icon: LineChart },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar({
  collapsed,
  onToggle,
}: {
  collapsed: boolean;
  onToggle: () => void;
}) {
  const pathname = usePathname();
  const [search, setSearch] = React.useState("");
  const { data } = useSessions({ search: search || undefined });

  return (
    <div className="flex h-full flex-col gap-1 p-3">
      <div className={cn("flex items-center gap-2 px-1 pb-2", collapsed && "justify-center")}>
        <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
          <ShieldCheck className="size-4" />
        </div>
        {!collapsed && <span className="font-semibold tracking-tight">Learner</span>}
        <Button
          variant="ghost"
          size="icon"
          className={cn("ml-auto", collapsed && "hidden")}
          onClick={onToggle}
          aria-label="Collapse navigation"
        >
          <ChevronLeft className="size-4" />
        </Button>
      </div>

      {collapsed && (
        <Button variant="ghost" size="icon" onClick={onToggle} aria-label="Expand navigation">
          <PanelLeft className="size-4" />
        </Button>
      )}

      <nav className="flex flex-col gap-0.5" aria-label="Primary">
        {NAV.map((item) => {
          const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
          const Icon = item.icon;
          return (
            <Button
              key={item.href}
              asChild
              variant={active ? "secondary" : "ghost"}
              size={collapsed ? "icon" : "sm"}
              className={cn(!collapsed && "w-full justify-start")}
            >
              <Link href={item.href} aria-current={active ? "page" : undefined}>
                <Icon className="size-4" />
                {!collapsed && item.label}
              </Link>
            </Button>
          );
        })}
      </nav>

      {!collapsed && (
        <>
          <div className="relative mt-3 px-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 size-3.5 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search sessions"
              aria-label="Search sessions"
              className="h-8 w-full rounded-md border border-input bg-background pl-8 pr-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>

          <div className="mt-2 flex-1 overflow-y-auto scroll-slim px-1">
            <p className="px-2 py-1 text-xs font-medium text-muted-foreground">Recent sessions</p>
            {data?.items.length ? (
              <ul className="flex flex-col gap-0.5">
                {data.items.map((s) => {
                  const active = pathname === `/sessions/${s.id}`;
                  return (
                    <li key={s.id}>
                      <Link
                        href={`/sessions/${s.id}`}
                        className={cn(
                          "flex flex-col gap-1 rounded-md px-2 py-1.5 text-sm hover:bg-muted",
                          active && "bg-muted",
                        )}
                      >
                        <span className="flex items-center gap-1.5">
                          <BookOpen className="size-3.5 shrink-0 text-muted-foreground" />
                          <span className="truncate">{s.title}</span>
                        </span>
                        <span className="pl-5 text-xs text-muted-foreground">
                          {formatRelative(s.updated_at)}
                          {s.saved && " · saved"}
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p className="px-2 py-2 text-xs text-muted-foreground">No sessions yet.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
