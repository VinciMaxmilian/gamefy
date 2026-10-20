import type { ReactNode } from "react";

export function Rail({ title, subtitle, action, children }: { title: ReactNode; subtitle?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h2 className="text-2xl md:text-[1.75rem]">{title}</h2>
          {subtitle && <p className="mt-1 text-fg-2">{subtitle}</p>}
        </div>
        {action}
      </div>
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{children}</div>
    </section>
  );
}
