import clsx from "clsx";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: "sm" | "md" | "lg" | "none";
}

export default function Card({ children, className, padding = "md" }: CardProps) {
  return (
    <div className={clsx(
      "bg-[#1a1f2e] border border-[#252b3b] rounded-xl",
      padding === "sm"  && "p-4",
      padding === "md"  && "p-5",
      padding === "lg"  && "p-6",
      padding === "none" && "",
      className,
    )}>
      {children}
    </div>
  );
}
