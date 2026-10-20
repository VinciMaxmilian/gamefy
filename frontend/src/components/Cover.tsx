import { coverGradient, safeImageUrl, cn } from "@/lib/utils";

export function Cover({ slug, title, url, className }: { slug: string; title: string; url: string | null; className?: string }) {
  const img = safeImageUrl(url);
  return (
    <div className={cn("relative overflow-hidden", className)} style={{ background: coverGradient(slug) }}>
      {img ? (
        <img src={img} alt="" loading="lazy" referrerPolicy="no-referrer" className="absolute inset-0 size-full object-cover" />
      ) : (
        <>
          <div className="absolute inset-0 bg-[radial-gradient(120%_80%_at_20%_0%,rgba(255,255,255,0.22),transparent_60%)]" />
          <span aria-hidden className="absolute bottom-3 left-4 right-4 line-clamp-2 text-[1.35rem] font-bold leading-tight tracking-tight text-white/90 drop-shadow">{title}</span>
        </>
      )}
    </div>
  );
}
