import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const baseClasses =
  "inline-flex min-h-10 items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-semibold transition active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-600 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-60";

const variantClasses: Record<ButtonVariant, string> = {
  primary: "bg-accent text-white shadow-sm shadow-teal-900/10 hover:bg-teal-800",
  secondary: "border border-line bg-white text-ink shadow-sm hover:border-teal-600 hover:text-teal-700",
  ghost: "text-slate-600 hover:bg-teal-50 hover:text-teal-800",
  danger: "border border-red-200 bg-white text-red-700 shadow-sm hover:border-red-300 hover:bg-red-50",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  isLoading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
};

export function Button({
  variant = "primary",
  isLoading = false,
  leftIcon,
  rightIcon,
  children,
  className,
  disabled,
  ...props
}: ButtonProps) {
  const classes = [baseClasses, variantClasses[variant], className].filter(Boolean).join(" ");

  return (
    <button className={classes} disabled={disabled || isLoading} aria-busy={isLoading || undefined} {...props}>
      {isLoading ? <Loader2 className="docintel-spinner h-4 w-4" aria-hidden="true" /> : leftIcon}
      <span>{children}</span>
      {!isLoading ? rightIcon : null}
    </button>
  );
}
