import { setupServer } from "msw/node";
import { handlers } from "@/testing/msw/handlers";

/**
 * The Node MSW server used by Vitest's jsdom environment. Started and
 * reset in `vitest.setup.ts`.
 */
export const server = setupServer(...handlers);
