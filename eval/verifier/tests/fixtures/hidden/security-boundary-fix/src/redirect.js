const TRUSTED_ORIGIN = "https://app.example.com";

export function resolveRedirect(target) {
  if (typeof target !== "string" || /[\s\\]/.test(target)) return "/";
  if (target.startsWith("/") && !target.startsWith("//")) return target;
  if (!URL.canParse(target)) return "/";
  const url = new URL(target);
  return url.origin === TRUSTED_ORIGIN && !url.username && !url.password ? target : "/";
}
