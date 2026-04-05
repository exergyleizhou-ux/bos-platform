import { useCallback, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, Plus, Search, X } from "lucide-react";

import { useBatchList, useBatchStats, useExportBatches } from "@/hooks/useBatches";
import { useDebounce } from "@/hooks/useDebounce";
import { Badge, GradeBadge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, ErrorState, NoResults } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
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
import { formatDate, formatNumber } from "@/lib/utils";
import type { BatchFilters } from "@/types/batch";
import type { SortConfig } from "@/types/common";

const PAGE_SIZE = 15;

const SPECIES_OPTIONS = [
  { value: "", label: "All species" },
  { value: "BSF", label: "BSF" },
  { value: "Mealworm", label: "Mealworm" },
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

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [species, setSpecies] = useState("");
  const [status, setStatus] = useState<BatchFilters["status"] | "">("");
  const [sort, setSort] = useState<SortConfig>({
    field: "created_at",
    direction: "desc",
  });

  const debouncedSearch = useDebounce(search, 300);

  const filters: BatchFilters = {
    search: debouncedSearch || undefined,
    species: species || undefined,
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
    setStatus("");
    setPage(1);
  };

  const hasFilters = !!debouncedSearch || !!species || !!status;

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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Batch Command"
        title="Batch command queue"
        description="Inspect intake volume, quality posture, and live batch states without falling back to a generic management table."
        badges={[
          { label: "Command-center mode", variant: "brand" },
          { label: hasFilters ? "Filtered view" : "Full portfolio", variant: "neutral" },
        ]}
        actions={
          <>
            <Button
              variant="secondary"
              leftIcon={<Download className="h-4 w-4" />}
              onClick={() => exportBatches.mutate({ format: "csv", filters })}
              loading={exportBatches.isPending}
            >
              Export queue
            </Button>
            <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => navigate("/batches/new")}>
              New batch
            </Button>
          </>
        }
        stats={[
          {
            label: "Total batches",
            value: statsSummary?.total ?? "Loading",
            hint: "All recorded command surfaces",
          },
          {
            label: "Active",
            value: statsSummary?.active ?? "Loading",
            hint: "Current live queue",
          },
          {
            label: "Completed",
            value: statsSummary?.completed ?? "Loading",
            hint: "Closed command cycles",
          },
          {
            label: "Species mix",
            value: statsSummary?.speciesCount ?? "Loading",
            hint: "Distinct feedstock profiles",
          },
        ]}
      />

      <Card tone="strong">
        <CardHeader
          title="Filter and route batches"
          description="Search by batch ID, narrow the queue, or jump straight into a command center detail page."
        />
        <CardBody className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.4fr)_200px_200px_auto]">
            <Input
              placeholder="Search batch ID or operator"
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
              options={SPECIES_OPTIONS}
              value={species}
              onChange={(event) => {
                setSpecies(event.target.value);
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
              Clear
            </Button>
          </div>

          {statsSummary ? (
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <p className="metric-kicker">Average SER</p>
                <p className="mt-2 text-2xl font-semibold text-white">
                  {formatNumber(statsSummary.avgSer, 4)}
                </p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <p className="metric-kicker">Queue pressure</p>
                <div className="mt-2">
                  <Badge variant={statsSummary.active > statsSummary.completed ? "warning" : "success"}>
                    {statsSummary.active > statsSummary.completed ? "Live queue elevated" : "Balanced"}
                  </Badge>
                </div>
              </div>
              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <p className="metric-kicker">Portfolio state</p>
                <p className="mt-2 text-sm leading-6 text-surface-300">
                  Use this surface to prioritize batches that need compute, requalification, or rapid drill-down.
                </p>
              </div>
            </div>
          ) : null}
        </CardBody>
      </Card>

      <Card noPadding>
        <div className="border-b border-white/8 px-6 py-5">
          <CardHeader
            title="Batch queue"
            description="High-readability operational table with direct access into each batch command surface."
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
                title="No batches yet"
                description="Create the first batch to establish a command queue."
                actionLabel="Create batch"
                onAction={() => navigate("/batches/new")}
              />
            )
          ) : (
            <>
              <Table>
                <TableHead>
                  <tr>
                    <TableHeaderCell
                      sortable
                      sortField="batch_id"
                      currentSort={sort}
                      onSort={handleSort}
                    >
                      Batch
                    </TableHeaderCell>
                    <TableHeaderCell>Species</TableHeaderCell>
                    <TableHeaderCell
                      sortable
                      sortField="dm_in"
                      currentSort={sort}
                      onSort={handleSort}
                      align="right"
                    >
                      DM In
                    </TableHeaderCell>
                    <TableHeaderCell align="right">SER</TableHeaderCell>
                    <TableHeaderCell align="center">Grade</TableHeaderCell>
                    <TableHeaderCell align="center">Status</TableHeaderCell>
                    <TableHeaderCell
                      sortable
                      sortField="created_at"
                      currentSort={sort}
                      onSort={handleSort}
                    >
                      Updated
                    </TableHeaderCell>
                  </tr>
                </TableHead>
                <TableBody>
                  {data.items.map((batch) => (
                    <TableRow key={batch.id} onClick={() => navigate(`/batches/${batch.id}`)}>
                      <TableCell>
                        <div>
                          <p className="font-medium text-white">{batch.batch_id}</p>
                          <p className="mt-1 text-xs text-surface-500">
                            {batch.operator ?? "Unassigned operator"}
                          </p>
                        </div>
                      </TableCell>
                      <TableCell>{batch.species}</TableCell>
                      <TableCell align="right" mono>
                        {formatNumber(batch.dm_in, 3)}
                      </TableCell>
                      <TableCell align="right" mono>
                        {formatNumber(batch.ser_value, 4)}
                      </TableCell>
                      <TableCell align="center">
                        {batch.grade ? <GradeBadge grade={batch.grade} /> : <Badge>N/A</Badge>}
                      </TableCell>
                      <TableCell align="center">
                        <StatusBadge status={batch.status} />
                      </TableCell>
                      <TableCell>{formatDate(batch.updated_at)}</TableCell>
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
      </Card>
    </div>
  );
}
