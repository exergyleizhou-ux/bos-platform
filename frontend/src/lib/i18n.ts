import type { ReactNode } from "react";

import { EXACT_TRANSLATIONS, PHRASE_REPLACEMENTS } from "@/lib/i18n-data";
import { useUIStore } from "@/store/uiStore";

export type AppLocale = "en-US" | "zh-CN";

const EXACT_REVERSE_TRANSLATIONS: Record<string, string> = Object.fromEntries(
  Object.entries(EXACT_TRANSLATIONS).map(([source, target]) => [target, source]),
);

const REVERSE_PHRASE_REPLACEMENTS: Array<[string, string]> = PHRASE_REPLACEMENTS.map(
  ([source, target]) => [target, source],
);

const TEXT_NODE_ORIGINAL = new WeakMap<Text, string>();
const ATTRIBUTE_ORIGINAL = new WeakMap<Element, Map<string, string>>();
export const TRANSLATABLE_ATTRIBUTES = ["placeholder", "title", "aria-label"] as const;
const TRANSLATION_SKIP_SELECTOR = "[data-i18n-skip]";

function shouldSkipTranslation(node: Node | null) {
  if (!node) return true;
  if (node instanceof Element) return Boolean(node.closest(TRANSLATION_SKIP_SELECTOR));
  return node.parentElement ? Boolean(node.parentElement.closest(TRANSLATION_SKIP_SELECTOR)) : true;
}

export function getLocale() {
  return useUIStore.getState().locale;
}

export function translateText(input: string, locale: AppLocale = getLocale()): string {
  const leading = input.match(/^\s*/)?.[0] ?? "";
  const trailing = input.match(/\s*$/)?.[0] ?? "";
  const core = input.trim();
  if (!core) return input;

  if (locale === "en-US") {
    const exactReverse = EXACT_REVERSE_TRANSLATIONS[core];
    if (exactReverse) return `${leading}${exactReverse}${trailing}`;

    let reversed = core;
    for (const [source, target] of REVERSE_PHRASE_REPLACEMENTS) {
      reversed = reversed.split(source).join(target);
    }
    return `${leading}${reversed}${trailing}`;
  }

  const exact = EXACT_TRANSLATIONS[core];
  if (exact) return `${leading}${exact}${trailing}`;

  let translated = core;
  for (const [source, target] of PHRASE_REPLACEMENTS) {
    translated = translated.split(source).join(target);
  }

  return `${leading}${translated}${trailing}`;
}

export function translateNodeText(value: ReactNode, locale: AppLocale = getLocale()) {
  return typeof value === "string" ? translateText(value, locale) : value;
}

export function getLocaleToggleLabel(locale: AppLocale = getLocale()) {
  return locale === "zh-CN" ? "English" : "中文";
}

export function getLocaleToggleActionLabel(locale: AppLocale = getLocale()) {
  return translateText(
    locale === "zh-CN" ? "Switch to English" : "Switch to Chinese",
    locale,
  );
}

export function getThemeToggleLabel(
  resolvedTheme: "light" | "dark",
  locale: AppLocale = getLocale(),
) {
  return translateText(resolvedTheme === "dark" ? "Light" : "Dark", locale);
}

function isSkippableTextNode(node: Text) {
  const parent = node.parentElement;
  if (!parent) return true;
  if (!node.nodeValue?.trim()) return true;
  if (shouldSkipTranslation(node)) return true;
  return ["SCRIPT", "STYLE", "NOSCRIPT"].includes(parent.tagName);
}

function getTextNodeOriginal(node: Text, locale: AppLocale) {
  const current = node.nodeValue ?? "";
  const cached = TEXT_NODE_ORIGINAL.get(node);
  if (cached == null) {
    TEXT_NODE_ORIGINAL.set(node, current);
    return current;
  }

  const cachedZh = translateText(cached, "zh-CN");
  const cacheStillOwnsNode =
    current === cached || current === cachedZh || (locale === "en-US" && current === translateText(cachedZh, "en-US"));

  if (cacheStillOwnsNode) return cached;

  TEXT_NODE_ORIGINAL.set(node, current);
  return current;
}

function translateTextNodes(root: ParentNode, locale: AppLocale) {
  if (shouldSkipTranslation(root as Node)) return;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let current = walker.nextNode();
  while (current) {
    const textNode = current as Text;
    if (!isSkippableTextNode(textNode)) {
      const original = getTextNodeOriginal(textNode, locale);
      const next = locale === "zh-CN" ? translateText(original, locale) : original;
      if (textNode.nodeValue !== next) {
        textNode.nodeValue = next;
      }
    }
    current = walker.nextNode();
  }
}

function getAttributeOriginal(
  attribute: (typeof TRANSLATABLE_ATTRIBUTES)[number],
  current: string,
  locale: AppLocale,
  originalMap: Map<string, string>,
) {
  const cached = originalMap.get(attribute);
  if (cached == null) {
    originalMap.set(attribute, current);
    return current;
  }

  const cachedZh = translateText(cached, "zh-CN");
  const cacheStillOwnsAttribute =
    current === cached || current === cachedZh || (locale === "en-US" && current === translateText(cachedZh, "en-US"));

  if (cacheStillOwnsAttribute) return cached;

  originalMap.set(attribute, current);
  return current;
}

function translateAttributes(root: ParentNode, locale: AppLocale) {
  if (shouldSkipTranslation(root as Node)) return;

  const elements =
    root instanceof Element
      ? [root, ...Array.from(root.querySelectorAll(`*:not(${TRANSLATION_SKIP_SELECTOR})`))]
      : Array.from((root as Document).querySelectorAll("*"));

  for (const element of elements) {
    if (shouldSkipTranslation(element)) continue;

    let originalMap = ATTRIBUTE_ORIGINAL.get(element);
    if (!originalMap) {
      originalMap = new Map<string, string>();
      ATTRIBUTE_ORIGINAL.set(element, originalMap);
    }

    for (const attribute of TRANSLATABLE_ATTRIBUTES) {
      const current = element.getAttribute(attribute);
      if (current == null) continue;
      const original = getAttributeOriginal(attribute, current, locale, originalMap);
      const next = locale === "zh-CN" ? translateText(original, locale) : original;
      if (current !== next) {
        element.setAttribute(attribute, next);
      }
    }
  }
}

export function applyDocumentTranslations(root: ParentNode, locale: AppLocale) {
  translateTextNodes(root, locale);
  translateAttributes(root, locale);
}
