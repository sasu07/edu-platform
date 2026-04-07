import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const distDir = new URL("../dist", import.meta.url);
const assetsDir = new URL("../dist/assets", import.meta.url);
const indexPath = new URL("../dist/index.html", import.meta.url);

if (!existsSync(indexPath)) {
  throw new Error("Missing frontend dist/index.html. Run the build first.");
}

if (!existsSync(assetsDir)) {
  throw new Error("Missing frontend dist/assets directory.");
}

const files = readdirSync(assetsDir);
const jsFiles = files.filter((file) => file.endsWith(".js"));
const cssFiles = files.filter((file) => file.endsWith(".css"));
const lazyChunks = jsFiles.filter((file) => file !== "index" && file.includes("-"));

if (jsFiles.length < 3) {
  throw new Error(`Expected at least 3 JavaScript assets after code-splitting, found ${jsFiles.length}.`);
}

if (cssFiles.length < 1) {
  throw new Error("Expected at least one CSS asset in the build output.");
}

if (lazyChunks.length < 2) {
  throw new Error(`Expected at least 2 lazy-loaded JavaScript chunks, found ${lazyChunks.length}.`);
}

const indexHtml = readFileSync(indexPath, "utf8");
if (!indexHtml.includes("/assets/")) {
  throw new Error("Built index.html does not reference bundled assets.");
}

console.log(
  JSON.stringify(
    {
      jsFiles: jsFiles.length,
      cssFiles: cssFiles.length,
      lazyChunks: lazyChunks.length,
      sampleChunks: jsFiles.slice(0, 6),
    },
    null,
    2,
  ),
);
