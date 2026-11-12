/** Who a route is for: anyone, any signed-in user, or an administrator only. */
export type Audience = "public" | "member" | "admin";

/**
 * What a signed-in member gets on an admin route. The pages render for every signed-in user and
 * the API refuses the admin-only data with 403, so the page shows its load-failure alert; a page
 * that loads nothing before a submit renders as it does for an admin.
 */
export type MemberOutcome =
  { kind: "load-refused"; alert: string } | { kind: "renders"; reason: string };

export interface RouteEntry {
  pattern: string;
  template: string;
  heading: string | RegExp | null;
  audience: Audience;
  /** The URL (path and query) the visit must end on when the route only redirects. */
  redirectsTo?: string;
  /** What a member opening this admin route gets; required on every admin entry. */
  memberOutcome?: MemberOutcome;
}

export interface AllowlistEntry {
  pattern: string;
  reason: string;
}

/** Stands for a seeded user other than the viewer: the member for an admin, the admin for a member. */
export const OTHER_USER_ID = "[userId]";

/** The display name of the user `OTHER_USER_ID` resolves to. */
export const OTHER_USER_NAME = "[userName]";

/** The h1 of the users list, where `/` lands every signed-in user. */
export const USERS_HEADING = "Users";

/** The h1 of the login page. */
export const LOGIN_HEADING = "Sign in";

/** Every route the smoke run visits, with the heading that proves it rendered. */
export const ROUTE_MANIFEST: readonly RouteEntry[] = [
  { pattern: "/login", template: "/login", heading: LOGIN_HEADING, audience: "public" },
  {
    pattern: "/",
    template: "/",
    heading: USERS_HEADING,
    audience: "member",
    redirectsTo: "/users",
  },
  {
    pattern: "/users",
    template: "/users",
    heading: USERS_HEADING,
    audience: "admin",
    memberOutcome: { kind: "load-refused", alert: "Failed to load users" },
  },
  {
    pattern: "/users/new",
    template: "/users/new",
    heading: "New user",
    audience: "admin",
    memberOutcome: {
      kind: "renders",
      reason: "The form loads no data; the API refuses the member's submit with 403.",
    },
  },
  {
    pattern: "/users/[userId]",
    template: `/users/${OTHER_USER_ID}`,
    heading: OTHER_USER_NAME,
    audience: "admin",
    memberOutcome: { kind: "load-refused", alert: "Failed to load user" },
  },
];

/** `page.tsx` routes the smoke run does not visit, each with the reason a reviewer accepted. */
export const ROUTE_ALLOWLIST: readonly AllowlistEntry[] = [];
