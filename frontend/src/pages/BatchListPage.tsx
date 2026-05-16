import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Plus, Search, X } from "lucide-react";

import { useFeedstocksCatalog, useSpeciesCatalog } from "@/hooks/useBos";
import { useBatchList, useBatchStats, useExportBatches } from "@/hooks/useBatches";
import { useDebounce } from "@/hooks/useDebounce";
import { Badge, GradeBadge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { CardHeader } from "@/components/ui/Card";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { EmptyState, ErrorState, NoResults } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Pagination } from "@/components/ui/Pagination";
import { Select } from "@/components/ui/Select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  TableSkeleton,
} from "@/components/ui/Table";
import { translateText } from "@/lib/i18n";
import { formatDate, formatNumber } from "@/lib/utils";
import type { BatchFilters } from "@/types/batch";
import type { SortConfig } from "@/types/common";

const PAGE_SIZE = 15;

const FALLBACK_SPECIES_OPTIONS = [
  { value: "", label: "All species" },
  { value: "BSF", label: "BSF" },
  { value: "MW", label: "Yellow mealworm" },
  { value: "PB", label: "Protaetia grub" },
  { value: "Cricket", label: "Cricket" },
];

const STATUS_OPTIONS = [
  { value: "", label: "All status" },
  { value: "logged", label: "Logged" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
  { value: "failed", label: "Failed" },
];

export default function BatchListPage() {
  const navigate = useNavigate();
  const speciesCatalog = useSpeciesCatalog();
  const feedstocksCatalog = useFeedstocksCatalog();

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [species, setSpecies] = useState("");
  const [substrate, setSubstrate] = useState("");
  const [status, setStatus] = useState<BatchFilters["status"] | "">("");
  const [sort, setSort] = useState<SortConfig>({
    field: "created_at",
    direction: "desc",
  });

  const debouncedSearch = useDebounce(search, 300);

  const filters: BatchFilters = {
    search: debouncedSearch || undefined,
    species: species || undefined,
    substrate: substrate || undefined,
    status: status || undefined,
    sort_by: sort.field,
    sort_order: sort.direction,
  };

  const { data, isLoading, isError, refetch } = useBatchList(page, PAGE_SIZE, filters);
  const stats = useBatchStats();
  const exportBatches = useExportBatches();

  const handleSort = useCallback((field: string) => {
    setSort((previous) => ({
      field,
      direction:
        previous.field === field && previous.direction === "asc" ? "desc" : "asc",
    }));
    setPage(1);
  }, []);

  const clearFilters = () => {
    setSearch("");
    setSpecies("");
    setSubstrate("");
    setStatus("");
    setPage(1);
  };

  const hasFilters = !!debouncedSearch || !!species || !!substrate || !!status;

  const speciesOptions = useMemo(
    () =>
      speciesCatalog.data?.species?.length
        ? [
            { value: "", label: "All species" },
            ...speciesCatalog.data.species.map((item) => ({
              value: item.code,
              label: item.common_name,
            })),
          ]
        : FALLBACK_SPECIES_OPTIONS,
    [speciesCatalog.data],
  );
  const feedstockOptions = useMemo(
    () =>
      feedstocksCatalog.data?.feedstocks?.length
        ? [
            { value: "", label: "All feedstocks" },
            ...feedstocksCatalog.data.feedstocks.map((item) => ({
              value: item.key,
              label: item.display_name,
            })),
          ]
        : [
            { value: "", label: "All feedstocks" },
            { value: "distillers_grains", label: "Distillers grains" },
            { value: "washed_kitchen_waste", label: "Washed kitchen waste" },
            { value: "sewage_sludge", label: "Sewage sludge" },
          ],
    [feedstocksCatalog.data],
  );

  const statsSummary = useMemo(() => {
    const source = stats.data;
    if (!source) return null;

    const active = source.by_status.active ?? 0;
    const completed = source.by_status.completed ?? 0;
    const speciesCount = Object.keys(source.by_species ?? {}).length;

    return {
      active,
      completed,
      speciesCount,
      avgSer: source.avg_ser,
      total: source.total,
    };
  }, [stats.data]);

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>{translateText("Batch Command")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("Batch command queue")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText("Inspect intake volume, quality posture, and live batch states without falling back to a generic management table.")}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Badge variant="brand">{translateText("Command-center mode")}</Badge>
              <Badge variant="neutral">{translateText(hasFilters ? "Filtered view" : "Full portfolio")}</Badge>
              <Button
                variant="secondary"
                leftIcon={<Download className="h-4 w-4" />}
                onClick={() => exportBatches.mutate({ format: "csv", filters })}
                loading={exportBatches.isPending}
              >
                {translateText("Export queue")}
              </Button>
              <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate("/batches/new")}>
                {translateText("New batch")}
              </Button>
            </div>
          </div>

          {statsSummary ? (
            <CockpitGrid className="md:grid-cols-3">
              <CockpitMetric
                label={translateText("Average SER")}
                value={formatNumber(statsSummary.avgSer, 4)}
                hint={translateText("Portfolio-level qualified performance")}
                accent="cyan"
              />
              <CockpitMetric
                label={translateText("Queue pressure")}
                value={translateText(statsSummary.active > statsSummary.completed ? "Live queue elevated" : "Balanced")}
                hint={translateText(`${statsSummary.active} active / ${statsSummary.completed} completed`)}
                accent={statsSummary.active > statsSummary.completed ? "amber" : "violet"}
              />
              <CockpitMetric
                label={translateText("Portfolio state")}
                value={`${statsSummary.total}`}
                hint={translateText(`${statsSummary.speciesCount} species represented`)}
                accent="neutral"
              />
            </CockpitGrid>
          ) : null}
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-5 lg:p-6">
        <div className="space-y-4">
          <div>
            <CockpitSectionLabel>{translateText("Filter and route batches")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Search by batch ID, narrow the queue, or jump straight into a command center detail page.")}
            </p>
          </div>
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_200px_220px_200px_auto]">
            <Input
              placeholder={translateText("Search batch ID or operator")}
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              leftIcon={<Search className="h-4 w-4" />}
              rightIcon={
                search ? (
                  <button
                    onClick={() => {
                      setSearch("");
                      setPage(1);
                    }}
                    className="text-surface-400 transition-colors hover:text-white"
                    type="button"
                  >
                    <X className="h-4 w-4" />
                  </button>
                ) : undefined
              }
            />

            <Select
              options={speciesOptions}
              value={species}
              onChange={(event) => {
                setSpecies(event.target.value);
                setPage(1);
              }}
            />

            <Select
              options={feedstockOptions}
              value={substrate}
              onChange={(event) => {
                setSubstrate(event.target.value);
                setPage(1);
              }}
            />

            <Select
              options={STATUS_OPTIONS}
              value={status}
              onChange={(event) => {
                setStatus(event.target.value as BatchFilters["status"] | "");
                setPage(1);
              }}
            />

            <Button variant="outline" onClick={clearFilters}>
              {translateText("Clear")}
            </Button>
          </div>
        </div>
      </CockpitPanel>

      <CockpitPanel className="p-0 overflow-hidden">
        <div className="border-b border-white/8 px-6 py-5">
          <CardHeader
            title={translateText("Batch queue")}
            description={translateText("High-readability operational table with direct access into each batch command surface.")}
          />
        </div>

        <div className="px-4 pb-4 pt-4">
          {isLoading ? (
            <TableSkeleton rows={8} cols={7} />
          ) : isError ? (
            <ErrorState onRetry={() => refetch()} />
          ) : !data?.items?.length ? (
            hasFilters ? (
              <NoResults query={debouncedSearch} onClear={clearFilters} />
            ) : (
              <EmptyState
                title={translateText("No batches yet")}
                description={translateText("Create the first batch to establish a command queue.")}
                actionLabel={translateText("Create batch")}
                onAction={() => navigate("/batches/new")}
              />
            )
          ) : (
            <>
              <Table className="batch-queue-table">
                <TableHead className="batch-queue-head">
                  <tr>
                    <TableHeaderCell
                      sortable
                      sortField="batch_id"
                      currentSort={sort}
                      onSort={handleSort}
                      className="batch-queue-header"
                    >
                      {translateText("Batch")}
                    </TableHeaderCell>
                    <TableHeaderCell className="batch-queue-header">{translateText("Species")}</TableHeaderCell>
                    <TableHeaderCell
                      sortable
                      sortField="dm_in"
                      currentSort={sort}
                      onSort={handleSort}
                      align="right"
                      className="batch-queue-header"
                    >
                      {translateText("DM In")}
                    </TableHeaderCell>
                    <TableHeaderCell align="right" className="batch-queue-header">{translateText("SER")}</TableHeaderCell>
                    <TableHeaderCell align="center" className="batch-queue-header">{translateText("Grade")}</TableHeaderCell>
                    <TableHeaderCell align="center" className="batch-queue-header">{translateText("Status")}</TableHeaderCell>
                    <TableHeaderCell
                      sortable
                      sortField="created_at"
                      currentSort={sort}
                      onSort={handleSort}
                      className="batch-queue-header"
                    >
                      {translateText("Updated")}
                    </TableHeaderCell>
                  </tr>
                </TableHead>
                <TableBody className="batch-queue-body">
                  {data.items.map((batch) => (
                    <TableRow key={batch.id} onClick={() => navigate(`/batches/${batch.id}`)} className="batch-queue-row">
                      <TableCell className="batch-queue-cell">
                        <div className="space-y-1">
                          <p className="font-medium text-white">{batch.batch_id}</p>
                          <p className="text-xs text-surface-500">
                            {batch.substrate
                              ? `${batch.operator ?? translateText("Unassigned operator")} · ${batch.substrate}`
                              : batch.operator ?? translateText("Unassigned operator")}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell className="batch-queue-cell">{batch.species}</TableCell>
                      <TableCell align="right" mono className="batch-queue-cell">
                        {formatNumber(batch.dm_in, 3)}
                      </TableCell>
                      <TableCell align="right" mono className="batch-queue-cell">
                        {formatNumber(batch.ser_value, 4)}
                      </TableCell>
                      <TableCell align="center" className="batch-queue-cell">
                        {batch.grade ? <GradeBadge grade={batch.grade} /> : <Badge>{translateText("N/A")}</Badge>}
                      </TableCell>
                      <TableCell align="center" className="batch-queue-cell">
                        <StatusBadge status={batch.status} />
                      </TableCell>
                      <TableCell className="batch-queue-cell">{formatDate(batch.updated_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="px-2 pt-4">
                <Pagination
                  page={page}
                  totalPages={data.total_pages}
                  total={data.total}
                  pageSize={PAGE_SIZE}
                  onPageChange={setPage}
                />
              </div>
            </>
          )}
        </div>
      </CockpitPanel>
    </div>
  );
}
