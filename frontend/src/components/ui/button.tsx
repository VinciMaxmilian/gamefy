import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium select-none transition-all duration-[var(--dur-fast)] ease-[var(--ease-spring)] active:scale-[0.97] disabled:pointer-events-none disabled:opacity-40",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent-hover",
        secondary: "bg-surface-2 text-fg hover:bg-surface-3",
        ghost: "text-fg-2 hover:bg-surface-2 hover:text-fg",
        ai: "bg-gradient-to-r from-ai-from to-ai-to text-white hover:brightness-110",
        danger: "bg-negative/15 text-negative hover:bg-negative/25",
      },
      size: { sm: "h-8 rounded-full px-3.5 text-sm", md: "h-10 rounded-full px-5 text-[15px]", lg: "h-12 rounded-full px-7 text-base", icon: "size-10 rounded-full" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof button> { asChild?: boolean }

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp ref={ref} className={cn(button({ variant, size }), className)} {...props} />;
});
Button.displayName = "Button";
