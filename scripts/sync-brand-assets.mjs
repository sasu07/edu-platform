import { copyFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, resolve } from "node:path";

const rootDir = resolve(new URL("..", import.meta.url).pathname);
const frontendLogo = resolve(rootDir, "frontend/public/logo_etox.png");
const backendLogo = resolve(rootDir, "edu_content_api/assets/logo_etox.png");

function sha1(path) {
  return createHash("sha1").update(readFileSync(path)).digest("hex");
}

if (!existsSync(frontendLogo)) {
  throw new Error(`Missing frontend source logo: ${frontendLogo}`);
}

mkdirSync(dirname(backendLogo), { recursive: true });
copyFileSync(frontendLogo, backendLogo);

const sourceHash = sha1(frontendLogo);
const targetHash = sha1(backendLogo);

if (sourceHash !== targetHash) {
  throw new Error("Logo sync failed: backend asset hash does not match frontend source.");
}

console.log(
  JSON.stringify(
    {
      synced: true,
      source: frontendLogo,
      target: backendLogo,
      sha1: sourceHash,
    },
    null,
    2,
  ),
);
