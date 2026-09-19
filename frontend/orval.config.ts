import { defineConfig } from "orval";

export default defineConfig({
  api: {
    input: {
      target: "../backend/openapi.json",
    },
    output: {
      mode: "tags-split",
      target: "src/lib/api/generated/endpoints",
      schemas: "src/lib/api/generated/model",
      client: "react-query",
      httpClient: "fetch",
      mock: false,
      override: {
        mutator: {
          path: "src/lib/api/mutator.ts",
          name: "apiMutator",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
        fetch: {
          includeHttpResponseReturnType: false,
        },
      },
    },
  },
  apiZod: {
    input: {
      target: "../backend/openapi.json",
    },
    output: {
      mode: "tags-split",
      target: "src/lib/api/generated/zod",
      client: "zod",
      fileExtension: ".zod.ts",
    },
  },
});
