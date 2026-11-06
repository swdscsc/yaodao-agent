export interface ParsedHTTPURL {
  scheme: "http" | "https";
  authority: string;
  path: string;
  href: string;
}

export function parseAbsoluteHTTPURL(value: string, allowInsecure = false): ParsedHTTPURL | null {
  const source = value.trim();
  if (!source || /[\u0000-\u0020\u007f\\]/.test(source)) return null;
  const match = /^(https?):\/\/([^/?#]+)([^?#]*)(\?[^#]*)?(#.*)?$/i.exec(source);
  if (!match || match[4] || match[5]) return null;
  const scheme = match[1].toLowerCase() as "http" | "https";
  if (scheme !== "https" && !allowInsecure) return null;
  const authority = match[2];
  if (!validAuthority(authority)) return null;
  const path = match[3] || "";
  if (path && !path.startsWith("/")) return null;
  const segments = path.split("/");
  if (segments.some((segment) => segment === "." || segment === "..")) return null;
  return { scheme, authority, path, href: `${scheme}://${authority}${path}` };
}

function validAuthority(authority: string): boolean {
  if (!authority || authority.includes("@") || authority.includes("%")) return false;
  if (authority.startsWith("[")) {
    const match = /^\[([0-9a-f:.]+)\](?::([0-9]{1,5}))?$/i.exec(authority);
    return Boolean(match && validPort(match[2]));
  }
  const match = /^([A-Za-z0-9.-]+)(?::([0-9]{1,5}))?$/.exec(authority);
  if (!match || !match[1] || match[1].startsWith(".") || match[1].endsWith(".")) return false;
  return validPort(match[2]);
}

function validPort(value: string | undefined): boolean {
  if (value === undefined) return true;
  const port = Number(value);
  return Number.isInteger(port) && port >= 1 && port <= 65_535;
}
