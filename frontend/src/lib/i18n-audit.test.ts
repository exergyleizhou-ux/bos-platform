import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  I18N_AUDIT_FILE_EXACT_ALLOWLIST,
  I18N_AUDIT_FILE_REGEX_ALLOWLIST,
  I18N_AUDIT_GLOBAL_EXACT_ALLOWLIST,
  I18N_AUDIT_SKIP_PREFIX,
  I18N_AUDIT_SKIP_SUBSTRINGS,
} from "@/lib/i18n-audit.allowlist";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SRC_ROOT = resolve(__dirname, "..");
const STRING_LITERAL_PATTERN = /(["'`])([^"'`\\]*(?:\\.[^"'`\\]*)*)\1/g;

function walkFiles(directory: string): string[] {
  const entries = readdirSync(directory);
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = join(directory, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      files.push(...walkFiles(fullPath));
    } else {
      files.push(fullPath);
    }
  }
  return files;
}

function loadTranslationKeys() {
  const translationFiles = [
    "lib/i18n-exact-translations.ts",
    "lib/i18n-exact-translations-bos.ts",
    "lib/i18n-exact-translations-assistant.ts",
    "lib/i18n-exact-translations-media.ts",
  ].map((file) => join(SRC_ROOT, file));

  const keys = new Set<string>();

  for (const file of translationFiles) {
    const content = readFileSync(file, "utf8");
    for (const match of content.matchAll(/^[ \t]*["'](.+?)["']\s*:/gm)) {
      keys.add(match[1]);
    }
  }

  const phraseReplacements = readFileSync(join(SRC_ROOT, "lib/i18n-phrase-replacements.ts"), "utf8");
  for (const match of phraseReplacements.matchAll(/\[\s*["'](.+?)["']\s*,/g)) {
    keys.add(match[1]);
  }

  return keys;
}

function decodeLiteral(raw: string) {
  return raw.includes("\\u") ? Buffer.from(raw, "utf8").toString("utf8").replace(/\\u([0-9a-fA-F]{4})/g, (_, code) => String.fromCharCode(parseInt(code, 16))) : raw;
}

function isNaturalLanguageCandidate(value: string) {
  const candidate = value.trim();
  if (candidate.length < 4) return false;
  if (candidate.startsWith("./") || candidate.startsWith("../") || candidate.startsWith("@") || candidate.startsWith("http") || candidate.startsWith("/") || candidate.startsWith("#")) return false;
  if (/[{}[\]=;]/.test(candidate)) return false;
  if (/^[,:?()[\]\\]+$/.test(candidate)) return false;
  if (/^[A-Z0-9_-]{3,}$/.test(candidate)) return false;
  if (/^[a-z0-9_./:-]+$/.test(candidate)) return false;
  if (I18N_AUDIT_SKIP_PREFIX.test(candidate)) return false;
  if (I18N_AUDIT_SKIP_SUBSTRINGS.some((token) => candidate.includes(token))) return false;
  if (!/[A-Za-z\u4e00-\u9fff]/.test(candidate)) return false;
  if (/^\)\s*:/.test(candidate) || /^\)\)\s*return/.test(candidate)) return false;
  if (/^[a-z]+[A-Z][A-Za-z]*$/.test(candidate)) return false;
  if (/^[A-Za-z]+\s+[A-Za-z]+\s+[A-Za-z]+\s*:\s*$/.test(candidate)) return false;
  if (/^[A-Za-z]+$/.test(candidate) && candidate.length <= 4 && !["Search", "Open", "Loss"].includes(candidate)) return false;
  return true;
}

function isAllowedByFile(relPath: string, value: string) {
  if (I18N_AUDIT_GLOBAL_EXACT_ALLOWLIST.has(value)) return true;
  if ((I18N_AUDIT_FILE_EXACT_ALLOWLIST[relPath] ?? []).includes(value)) return true;
  return (I18N_AUDIT_FILE_REGEX_ALLOWLIST[relPath] ?? []).some((pattern) => pattern.test(value));
}

function lineAt(content: string, index: number) {
  const lineStart = content.lastIndexOf("\n", index) + 1;
  const lineEndIndex = content.indexOf("\n", index);
  const lineEnd = lineEndIndex === -1 ? content.length : lineEndIndex;
  return content.slice(lineStart, lineEnd);
}

describe("i18n audit", () => {
  it("does not allow visible UI copy to bypass the translation layer", () => {
    const translationKeys = loadTranslationKeys();
    const targetFiles = walkFiles(SRC_ROOT).filter((file) => {
      const rel = relative(SRC_ROOT, file).replace(/\\/g, "/");
      return (
        (rel.startsWith("pages/") || rel.startsWith("components/") || rel === "lib/navigation.tsx") &&
        !rel.includes("i18n-exact-translations") &&
        !rel.endsWith(".test.ts") &&
        !rel.endsWith(".test.tsx") &&
        (rel.endsWith(".ts") || rel.endsWith(".tsx"))
      );
    });

    const findings: string[] = [];

    for (const file of targetFiles) {
      const rel = relative(SRC_ROOT, file).replace(/\\/g, "/");
      const content = readFileSync(file, "utf8");
      const seen = new Set<string>();

      for (const match of content.matchAll(STRING_LITERAL_PATTERN)) {
        const raw = match[2];
        const decoded = decodeLiteral(raw).trim();
        const sourceLine = lineAt(content, match.index ?? 0);

        if (!isNaturalLanguageCandidate(decoded)) continue;
        if (/^\s*import\s+/.test(sourceLine) || /\sfrom\s+["']/.test(sourceLine)) continue;
        if (/className=|stroke=|fill=|border=|placeholder:text-|position:\s*["']|^\s*\/\//.test(sourceLine)) continue;
        if (translationKeys.has(decoded)) continue;
        if (isAllowedByFile(rel, decoded)) continue;
        if (seen.has(decoded)) continue;

        seen.add(decoded);
        const line = content.slice(0, match.index ?? 0).split("\n").length;
        findings.push(`${rel}:${line}: ${decoded}`);
      }
    }

    expect(
      findings,
      `Visible UI copy must be translated or explicitly allowlisted.\n${findings.join("\n")}`,
    ).toEqual([]);
  });
});
