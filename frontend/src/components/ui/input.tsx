import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn("h-11 w-full rounded-md bg-surface-2 px-4 text-[15px] text-fg placeholder:text-fg-3 outline-none ring-1 ring-transparent transition focus:ring-accent", className)} {...props} />
));
Input.displayName = "Input";

export const Label = ({ children, htmlFor }: { children: React.ReactNode; htmlFor?: string }) => (
  <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-fg-2">{children}</label>
);
