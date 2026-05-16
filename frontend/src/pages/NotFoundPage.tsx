import { Fragment, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Compass,
  Home,
  Search,
} from "lucide-react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { NAV_ITEMS, type AppNavItem } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/store/uiStore";

interface RankedRoute {
  item: AppNavItem;
  score: number;
  matchedTerms: string[];
  reasons: string[];
}

export default function NotFoundPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const openCommandPalette = useUIStore((state) => state.openCommandPalette);
  const [query, setQuery] = useState("");

  const pathSegments = useMemo(
    () => tokenizeSearch(location.pathname),
    [location.pathname],
  );

  const suggestedRoutes = useMemo(() => {
    const tokens = tokenizeSearch(query);
    const activeTokens = tokens.length ? tokens : pathSegments;

    const visibleItems = NAV_ITEMS;

    const ranked = visibleItems
      .map((item) => rankRoute(item, activeTokens))
      .filter((entry): entry is RankedRoute => entry !== null)
      .sort((left, right) => {
        if (right.score !== left.score) return right.score - left.score;
        return left.item.label.localeCompare(right.item.label);
      })
      .slice(0, 6);

    if (ranked.length) return ranked;

    return visibleItems
      .filter((item) => item.to !== "/admin")
      .slice(0, 4)
      .map((item) => ({
        item,
        score: 0,
        matchedTerms: [],
        reasons: ["Suggested starting point"],
      }));
  }, [pathSegments, query]);

  const activeTokens = useMemo(() => tokenizeSearch(query), [query]);

  return (
    <div className="flex min-h-[70vh] items-center justify-center">
      <section className="assistant-thread-stage w-full max-w-5xl overflow-hidden rounded-[32px] p-8 lg:p-10">
        <div className="relative z-[1] space-y-8">
          <div className="grid gap-8 xl:grid-cols-[1.05fr_0.95fr] xl:items-end">
            <div className="space-y-4">
              <p className="assistant-section-kicker !text-brand-300/90">
                Route Fault
              </p>
              <div className="flex items-center gap-4">
                <span className="flex h-14 w-14 items-center justify-center rounded-[22px] border border-amber-400/20 bg-amber-500/12 text-amber-200">
                  <AlertTriangle className="h-6 w-6" />
                </span>
                <p className="text-7xl font-semibold tracking-tight text-white sm:text-8xl">404</p>
              </div>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                This route is outside the active command map
              </h1>
              <p className="max-w-2xl text-sm leading-7 text-surface-300">
                The requested address is not part of the live premium operator console, or the surface has moved behind a different route definition.
              </p>
            </div>

            <div className="grid gap-3 text-left sm:grid-cols-3 xl:grid-cols-1">
              <div className="assistant-thread-shell rounded-2xl border border-white/10 px-4 py-4">
                <p className="assistant-section-kicker !text-surface-500">Requested path</p>
                <p className="mt-2 break-all text-sm text-white">{location.pathname}</p>
              </div>
              <div className="assistant-thread-shell rounded-2xl border border-white/10 px-4 py-4">
                <p className="assistant-section-kicker !text-surface-500">Segments</p>
                <p className="mt-2 text-sm text-white">
                  {pathSegments.length ? pathSegments.join(" / ") : "root"}
                </p>
              </div>
              <div className="assistant-thread-shell rounded-2xl border border-white/10 px-4 py-4">
                <p className="assistant-section-kicker !text-surface-500">Safe action</p>
                <p className="mt-2 text-sm text-white">
                  Search a known route below or open the command palette.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
            <div className="assistant-aside-card rounded-[28px] p-5">
              <div className="flex items-center gap-3">
                <Compass className="h-5 w-5 text-sky-200" />
                <div>
                  <p className="text-sm font-medium text-white">Route recovery</p>
                  <p className="mt-1 text-xs text-surface-400">Search likely surfaces or jump into the command palette.</p>
                </div>
              </div>

              <div className="mt-5 space-y-4">
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search routes, sections, or surfaces"
                  leftIcon={<Search className="h-4 w-4" />}
                />

                <div className="flex flex-wrap items-center gap-2 text-xs text-surface-400">
                  <span>
                    {activeTokens.length
                      ? `Ranked by label, route, and keyword overlap for "${query}".`
                      : "Ranked by overlap with the missing route path."}
                  </span>
                  {activeTokens.length ? (
                    <Badge variant="info" size="xs">
                      {activeTokens.length} token{activeTokens.length > 1 ? "s" : ""}
                    </Badge>
                  ) : null}
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {suggestedRoutes.map((entry, index) => (
                    <button
                      key={entry.item.to}
                      type="button"
                      onClick={() => navigate(entry.item.to)}
                      className={cn(
                        "rounded-2xl border px-4 py-4 text-left transition-all duration-200",
                        index === 0
                          ? "border-brand-400/20 bg-brand-500/14 shadow-glow hover:-translate-y-0.5 hover:bg-brand-500/18"
                          : "border-white/10 bg-white/5 hover:-translate-y-0.5 hover:border-white/16 hover:bg-white/10",
                      )}
                    >
                      <div className="flex items-start gap-3 text-white">
                        <span
                          className={cn(
                            "mt-0.5 flex h-10 w-10 items-center justify-center rounded-2xl border",
                            index === 0
                              ? "border-brand-400/20 bg-brand-500/18 text-brand-100"
                              : "border-white/10 bg-white/6",
                          )}
                        >
                          {entry.item.icon}
                        </span>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-medium">
                              <HighlightedText
                                text={entry.item.label}
                                terms={activeTokens}
                              />
                            </p>
                            <Badge variant="neutral" size="xs">
                              {entry.item.section}
                            </Badge>
                            {index === 0 ? (
                              <Badge variant="brand" size="xs">
                                Best match
                              </Badge>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-surface-400">
                            {entry.item.description}
                          </p>
                          <div className="mt-3 flex flex-wrap items-center gap-2">
                            {entry.reasons.slice(0, 2).map((reason) => (
                              <Badge key={reason} variant="info" size="xs">
                                {reason}
                              </Badge>
                            ))}
                            <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-surface-500">
                              {entry.item.to}
                            </span>
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="assistant-aside-card rounded-[28px] p-5">
              <p className="assistant-section-kicker">Immediate actions</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <Button
                  variant="secondary"
                  leftIcon={<ArrowLeft className="h-4 w-4" />}
                  onClick={() => navigate(-1)}
                >
                  Go back
                </Button>
                <Button leftIcon={<Home className="h-4 w-4" />} onClick={() => navigate("/bos")}>
                  Return to assistant
                </Button>
                <Button
                  variant="outline"
                  leftIcon={<Search className="h-4 w-4" />}
                  onClick={openCommandPalette}
                >
                  Open command palette
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function tokenizeSearch(value: string) {
  return value
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(Boolean);
}

function rankRoute(item: AppNavItem, terms: string[]): RankedRoute | null {
  if (!terms.length) return null;

  const matchedTerms = new Set<string>();
  const reasons = new Set<string>();
  let score = 0;

  const label = item.label.toLowerCase();
  const shortLabel = item.shortLabel.toLowerCase();
  const description = item.description.toLowerCase();
  const section = item.section.toLowerCase();
  const path = item.to.toLowerCase();
  const keywords = (item.keywords ?? []).map((keyword) => keyword.toLowerCase());

  for (const term of terms) {
    let matched = false;

    if (label.startsWith(term) || shortLabel.startsWith(term)) {
      score += 9;
      matched = true;
      reasons.add("Label prefix");
    } else if (label.includes(term) || shortLabel.includes(term)) {
      score += 7;
      matched = true;
      reasons.add("Label match");
    }

    if (path.includes(`/${term}`) || path.endsWith(term)) {
      score += 8;
      matched = true;
      reasons.add("Route segment");
    } else if (path.includes(term)) {
      score += 5;
      matched = true;
      reasons.add("Route path");
    }

    if (keywords.some((keyword) => keyword === term || keyword.startsWith(term))) {
      score += 8;
      matched = true;
      reasons.add("Keyword");
    } else if (keywords.some((keyword) => keyword.includes(term))) {
      score += 5;
      matched = true;
      reasons.add("Related keyword");
    }

    if (section.includes(term)) {
      score += 3;
      matched = true;
      reasons.add("Section");
    }

    if (description.includes(term)) {
      score += 2;
      matched = true;
      reasons.add("Description");
    }

    if (matched) matchedTerms.add(term);
  }

  if (!matchedTerms.size) return null;

  if (item.to !== "/admin") score += 0.5;

  return {
    item,
    score,
    matchedTerms: Array.from(matchedTerms),
    reasons: Array.from(reasons),
  };
}

function HighlightedText({
  text,
  terms,
}: {
  text: string;
  terms: string[];
}) {
  const normalizedTerms = Array.from(new Set(terms.filter(Boolean)));
  if (!normalizedTerms.length) return <>{text}</>;

  const pattern = new RegExp(`(${normalizedTerms.map(escapeRegex).join("|")})`, "ig");
  const parts = text.split(pattern);

  return (
    <>
      {parts.map((part, index) => {
        const isMatch = normalizedTerms.some(
          (term) => part.toLowerCase() === term.toLowerCase(),
        );

        return isMatch ? (
          <mark
            key={`${part}-${index}`}
            className="rounded bg-brand-500/18 px-1 py-0.5 text-brand-100"
          >
            {part}
          </mark>
        ) : (
          <Fragment key={`${part}-${index}`}>{part}</Fragment>
        );
      })}
    </>
  );
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
