import "server-only";
import { cookies } from "next/headers";

interface ParsedCookie {
  name: string;
  value: string;
  path?: string;
  domain?: string;
  maxAge?: number;
  expires?: Date;
  httpOnly?: boolean;
  secure?: boolean;
  sameSite?: "lax" | "strict" | "none";
}

function parseSetCookieHeader(header: string): ParsedCookie | null {
  const segments = header.split(";").map((segment) => segment.trim());
  const nameValue = segments[0];
  if (!nameValue) return null;

  const separatorIndex = nameValue.indexOf("=");
  if (separatorIndex === -1) return null;

  const parsed: ParsedCookie = {
    name: nameValue.slice(0, separatorIndex),
    value: decodeURIComponent(nameValue.slice(separatorIndex + 1)),
  };

  for (const attribute of segments.slice(1)) {
    const equalsIndex = attribute.indexOf("=");
    const rawKey = equalsIndex === -1 ? attribute : attribute.slice(0, equalsIndex);
    const rawValue = equalsIndex === -1 ? "" : attribute.slice(equalsIndex + 1);
    const key = rawKey.toLowerCase();
    switch (key) {
      case "path":
        parsed.path = rawValue;
        break;
      case "domain":
        parsed.domain = rawValue;
        break;
      case "max-age":
        parsed.maxAge = Number(rawValue);
        break;
      case "expires":
        parsed.expires = new Date(rawValue);
        break;
      case "httponly":
        parsed.httpOnly = true;
        break;
      case "secure":
        parsed.secure = true;
        break;
      case "samesite":
        parsed.sameSite = rawValue.toLowerCase() as ParsedCookie["sameSite"];
        break;
      default:
        break;
    }
  }

  return parsed;
}

/**
 * Applies every `Set-Cookie` header from a backend response to the current
 * request's outgoing cookie jar, preserving each cookie's own `path`,
 * `httpOnly`, `secure`, `sameSite` and expiry. Used by the login Server
 * Action to forward FastAPI's `app_access`, `app_refresh` and `app_csrf`
 * cookies to the browser — Server Actions are the only place this template
 * can write an httpOnly cookie.
 */
export async function applySetCookieHeaders(setCookieHeaders: readonly string[]): Promise<void> {
  const cookieStore = await cookies();
  for (const header of setCookieHeaders) {
    const parsed = parseSetCookieHeader(header);
    if (!parsed) continue;
    cookieStore.set(parsed.name, parsed.value, {
      path: parsed.path,
      domain: parsed.domain,
      maxAge: parsed.maxAge,
      expires: parsed.expires,
      httpOnly: parsed.httpOnly,
      secure: parsed.secure,
      sameSite: parsed.sameSite,
    });
  }
}
