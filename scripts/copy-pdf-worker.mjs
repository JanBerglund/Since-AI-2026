import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(root, "node_modules/pdfjs-dist/build/pdf.worker.min.mjs");
const destination = resolve(root, "public/pdf.worker.min.mjs");

mkdirSync(dirname(destination), { recursive: true });
copyFileSync(source, destination);
