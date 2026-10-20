import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badge = cva("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium capitalize", {
  variants: {
    tone: {
      neutral: "bg-surface-2 text-fg-2",
      accent: "bg-accent/15 text-accent",
      positive: "bg-positive/15 text-positive",
      warning: "bg-warning/15 text-warning",
      negative: "bg-negative/15 text-negative",
      ai: "bg-ai-from/15 text-ai-from",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export const Badge = ({ className, tone, ...p }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) => (
  <span className={cn(badge({ tone }), className)} {...p} />
);
