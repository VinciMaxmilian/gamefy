import { coverTint, safeImageUrl, cn } from "@/lib/utils";

export function Cover({ slug, title, url, className }: { slug: string; title: string; url: string | null; className?: string }) {
  const img = safeImageUrl(url);
  return (
    <div className={cn("relative overflow-hidden bg-surface-2", className)} style={img ? undefined : { backgroundColor: coverTint(slug) }}>
      {img ? (
        <img src={img} alt="" loading="lazy" referrerPolicy="no-referrer" className="absolute inset-0 size-full object-cover" />
      ) : (
        <span aria-hidden className="absolute inset-x-4 bottom-3 line-clamp-2 text-lg font-semibold leading-tight tracking-tight text-fg-2">{title}</span>
      )}
    </div>
  );
}
