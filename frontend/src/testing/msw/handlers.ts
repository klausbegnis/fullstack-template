import type { HttpHandler } from "msw";

/**
 * The default MSW handler set the server starts with. A feature's own tests
 * override individual routes with `server.use(...)`; this array stays
 * empty until a later feature adds its handlers here.
 */
export const handlers: HttpHandler[] = [];
