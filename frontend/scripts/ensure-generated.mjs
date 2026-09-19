import { existsSync } from "node:fs";
import { execSync } from "node:child_process";

const generatedDir = new URL("../src/lib/api/generated/", import.meta.url);

if (!existsSync(generatedDir)) {
  execSync("npm run generate:api", { stdio: "inherit" });
}
