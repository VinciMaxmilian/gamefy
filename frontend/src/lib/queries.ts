import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import { useAuth } from "./auth";
import type { GameCard, LibraryEntry } from "./types";

export function useWishlist() {
  const { me } = useAuth();
  return useQuery({ queryKey: ["wishlist"], queryFn: () => api<GameCard[]>("/me/wishlist"), enabled: !!me });
}
export function useLibrary() {
  const { me } = useAuth();
  return useQuery({ queryKey: ["library"], queryFn: () => api<LibraryEntry[]>("/me/library"), enabled: !!me });
}
export function useMyRatings() {
  const { me } = useAuth();
  return useQuery({ queryKey: ["ratings"], queryFn: () => api<Record<string, number>>("/me/ratings"), enabled: !!me });
}

/** Any change to user data invalidates what depends on it (taste profile + recommendations). */
export function useInvalidateUserData() {
  const qc = useQueryClient();
  return () => Promise.all(["wishlist", "library", "ratings", "taste", "for-you"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
}

export function useToggleWishlist() {
  const invalidate = useInvalidateUserData();
  return useMutation({
    mutationFn: ({ slug, on }: { slug: string; on: boolean }) => api(`/me/wishlist/${slug}`, { method: on ? "PUT" : "DELETE" }),
    onSuccess: invalidate,
  });
}
