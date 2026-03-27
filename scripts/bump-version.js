#!/usr/bin/env node
/**
 * Bump version across all files: package.json, manifest.json, const.py
 * Usage: node scripts/bump-version.js [major|minor|patch]
 */

const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const FILES = {
  package: path.join(ROOT, "package.json"),
  manifest: path.join(ROOT, "custom_components", "tesla_solar_charging", "manifest.json"),
  const: path.join(ROOT, "custom_components", "tesla_solar_charging", "const.py"),
};

const bump = process.argv[2] || "patch";
if (!["major", "minor", "patch"].includes(bump)) {
  console.error(`Usage: node bump-version.js [major|minor|patch]\nGot: "${bump}"`);
  process.exit(1);
}

// Read current version from package.json
const pkg = JSON.parse(fs.readFileSync(FILES.package, "utf8"));
const current = pkg.version;
const [major, minor, patch] = current.split(".").map(Number);

let next;
if (bump === "major") next = `${major + 1}.0.0`;
else if (bump === "minor") next = `${major}.${minor + 1}.0`;
else next = `${major}.${minor}.${patch + 1}`;

// Update package.json
pkg.version = next;
fs.writeFileSync(FILES.package, JSON.stringify(pkg, null, 2) + "\n", "utf8");

// Update manifest.json
let manifest = fs.readFileSync(FILES.manifest, "utf8");
manifest = manifest.replace(`"version": "${current}"`, `"version": "${next}"`);
fs.writeFileSync(FILES.manifest, manifest, "utf8");

// Update const.py
let constPy = fs.readFileSync(FILES.const, "utf8");
constPy = constPy.replace(`VERSION = "${current}"`, `VERSION = "${next}"`);
fs.writeFileSync(FILES.const, constPy, "utf8");

console.log(`${current} → ${next}`);
console.log(`Updated: package.json, manifest.json, const.py`);
