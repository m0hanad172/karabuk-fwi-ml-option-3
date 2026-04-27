"use client";

import { cn } from "@/lib/utils";

interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}

/**
 * Reusable section header used at the top of every page body. Produces
 * a consistent hierarchy (eyebrow / display heading / description) with
 * optional right-aligned actions — aligned with enterprise-SKILL.md's
 * "strong hierarchy, explicit rhythm" rules.
 *
 * All strings are already localised by the caller (see AppShell).
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 md:flex-row md:items-end md:justify-between pb-5",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow && <p className="ent-eyebrow mb-1">{eyebrow}</p>}
        <h2 className="font-display text-2xl md:text-[28px] font-semibold tracking-tight leading-none">
          {title}
        </h2>
        {description && (
          <p className="mt-2 text-sm text-muted-foreground max-w-2xl">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
