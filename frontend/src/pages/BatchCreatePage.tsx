import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ArrowLeft, Save } from "lucide-react";

import { useFeedstocksCatalog, useSpeciesCatalog } from "@/hooks/useBos";
import { useCreateBatch } from "@/hooks/useBatches";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardFooter, CardHeader } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { BatchCreate } from "@/types/batch";

const batchSchema = z.object({
  batch_id: z.string().min(1, "Batch ID is required").max(50, "Max 50 characters"),
  species: z.string().min(1, "Species is required"),
  substrate: z.string().optional(),
  dm_in: z.coerce.number().positive("Must be positive"),
  dm_out: z.coerce.number().positive("Must be positive"),
  n_in: z.coerce.number().positive().optional().or(z.literal("")),
  n_larvae: z.coerce.number().positive().optional().or(z.literal("")),
  n_frass: z.coerce.number().positive().optional().or(z.literal("")),
  ash_in: z.coerce.number().min(0).optional().or(z.literal("")),
  ash_out: z.coerce.number().min(0).optional().or(z.literal("")),
  fat_in: z.coerce.number().min(0).optional().or(z.literal("")),
  fat_out: z.coerce.number().min(0).optional().or(z.literal("")),
  temperature: z.coerce.number().optional().or(z.literal("")),
  moisture: z.coerce.number().min(0).max(100).optional().or(z.literal("")),
  feed_rate: z.coerce.number().positive().optional().or(z.literal("")),
  density: z.coerce.number().positive().optional().or(z.literal("")),
  operator: z.string().optional(),
  notes: z.string().max(500).optional(),
  batch_date: z.string().optional(),
});

type BatchFormData = z.infer<typeof batchSchema>;

const FALLBACK_SPECIES_OPTIONS = [
  { value: "BSF", label: "BSF (Black Soldier Fly)" },
  { value: "MW", label: "MW (Yellow Mealworm)" },
  { value: "PB", label: "PB (Protaetia grub / chafer larva)" },
  { value: "Cricket", label: "Cricket" },
  { value: "Other", label: "Other" },
];

const OPTIONAL_NUMERIC_FIELDS = [
  "n_in",
  "n_larvae",
  "n_frass",
  "ash_in",
  "ash_out",
  "fat_in",
  "fat_out",
  "temperature",
  "moisture",
  "feed_rate",
  "density",
] as const;

export default function BatchCreatePage() {
  const navigate = useNavigate();
  const createBatch = useCreateBatch();
  const speciesCatalog = useSpeciesCatalog();
  const feedstocksCatalog = useFeedstocksCatalog();

  const speciesOptions =
    speciesCatalog.data?.species?.length
      ? speciesCatalog.data.species.map((item) => ({
          value: item.code,
          label: `${item.code} (${item.common_name})`,
        }))
      : FALLBACK_SPECIES_OPTIONS;
  const feedstockOptions =
    feedstocksCatalog.data?.feedstocks?.length
      ? feedstocksCatalog.data.feedstocks.map((item) => ({
          value: item.key,
          label: item.display_name,
        }))
      : [
          { value: "distillers_grains", label: "Distillers grains" },
          { value: "washed_kitchen_waste", label: "Washed kitchen waste" },
          { value: "straw", label: "Straw / crop residue" },
          { value: "sewage_sludge", label: "Sewage sludge" },
        ];

  const form = useForm<BatchFormData>({
    resolver: zodResolver(batchSchema),
    defaultValues: {
      batch_id: "",
      species: "",
      substrate: "",
      dm_in: "" as unknown as number,
      dm_out: "" as unknown as number,
      operator: "",
      notes: "",
      batch_date: new Date().toISOString().split("T")[0],
    },
  });

  const onSubmit = async (data: BatchFormData) => {
    const payload: BatchCreate = {
      batch_id: data.batch_id,
      species: data.species,
      substrate: data.substrate || undefined,
      dm_in: data.dm_in,
      dm_out: data.dm_out,
    };

    for (const field of OPTIONAL_NUMERIC_FIELDS) {
      const value = data[field];
      if (value !== "" && value !== undefined && value !== null) {
        payload[field] = Number(value);
      }
    }

    if (data.operator) payload.operator = data.operator;
    if (data.notes) payload.notes = data.notes;
    if (data.batch_date) payload.batch_date = data.batch_date;

    await createBatch.mutateAsync(payload);
    navigate("/batches");
  };

  return (
    <div className="space-y-6">
      <div className="assistant-aside-card rounded-[30px] px-6 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="assistant-section-kicker">
              Batch Command
            </p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-white sm:text-[2.55rem]">
              New batch
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-7 text-surface-300">
              Create a new batch record for the command queue.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              leftIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate("/batches")}
            >
              Back
            </Button>
          </div>
        </div>
      </div>

      <form onSubmit={form.handleSubmit(onSubmit)} noValidate>
        <Card className="assistant-aside-card mb-6 rounded-[28px]">
          <CardHeader
            title="Required Information"
            description="Core batch identification and dry-matter values."
          />
          <CardBody className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="Batch ID"
                required
                placeholder="e.g., BSF-2025-001"
                error={form.formState.errors.batch_id?.message}
                className="batch-create-field"
                {...form.register("batch_id")}
              />
              <Select
                label="Species"
                required
                options={speciesOptions}
                placeholder="Select species"
                error={form.formState.errors.species?.message}
                className="batch-create-field"
                {...form.register("species")}
              />
              <Select
                label="Feedstock"
                options={feedstockOptions}
                placeholder="Select feedstock"
                error={form.formState.errors.substrate?.message}
                className="batch-create-field"
                {...form.register("substrate")}
              />
              <Input
                label="DM In (kg)"
                type="number"
                step="0.001"
                required
                placeholder="0.000"
                error={form.formState.errors.dm_in?.message}
                className="batch-create-field"
                {...form.register("dm_in")}
              />
              <Input
                label="DM Out (kg)"
                type="number"
                step="0.001"
                required
                placeholder="0.000"
                error={form.formState.errors.dm_out?.message}
                className="batch-create-field"
                {...form.register("dm_out")}
              />
            </div>
          </CardBody>
        </Card>

        <Card className="assistant-aside-card mb-6 rounded-[28px]">
          <CardHeader
            title="Composition"
            description="Optional nitrogen, ash, and fat values for deeper SER computation."
          />
          <CardBody className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input label="N In (kg)" type="number" step="0.001" placeholder="Optional" className="batch-create-field" {...form.register("n_in")} />
              <Input
                label="N Larvae (kg)"
                type="number"
                step="0.001"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("n_larvae")}
              />
              <Input
                label="N Frass (kg)"
                type="number"
                step="0.001"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("n_frass")}
              />
              <Input
                label="Ash In (kg)"
                type="number"
                step="0.001"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("ash_in")}
              />
              <Input
                label="Ash Out (kg)"
                type="number"
                step="0.001"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("ash_out")}
              />
              <Input
                label="Fat In (kg)"
                type="number"
                step="0.001"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("fat_in")}
              />
              <Input
                label="Fat Out (kg)"
                type="number"
                step="0.001"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("fat_out")}
              />
            </div>
          </CardBody>
        </Card>

        <Card className="assistant-aside-card mb-6 rounded-[28px]">
          <CardHeader
            title="Environment and Metadata"
            description="Optional operating conditions and record annotations."
          />
          <CardBody className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <Input
                label="Temperature (C)"
                type="number"
                step="0.1"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("temperature")}
              />
              <Input
                label="Moisture (%)"
                type="number"
                step="0.1"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("moisture")}
              />
              <Input
                label="Feed Rate (kg/h)"
                type="number"
                step="0.01"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("feed_rate")}
              />
              <Input
                label="Density (kg/m3)"
                type="number"
                step="0.01"
                placeholder="Optional"
                className="batch-create-field"
                {...form.register("density")}
              />
              <Input label="Operator" placeholder="Operator name" className="batch-create-field" {...form.register("operator")} />
              <Input label="Batch Date" type="date" className="batch-create-field" {...form.register("batch_date")} />
            </div>
            <div className="mt-4">
              <Textarea
                label="Notes"
                placeholder="Optional notes about this batch"
                maxLength={500}
                showCount
                className="batch-create-notes"
                {...form.register("notes")}
              />
            </div>
          </CardBody>
          <CardFooter className="border-white/8 pt-5">
            <Button variant="secondary" type="button" onClick={() => navigate("/batches")}>
              Cancel
            </Button>
            <Button type="submit" loading={createBatch.isPending} leftIcon={<Save className="h-4 w-4" />}>
              Create Batch
            </Button>
          </CardFooter>
        </Card>
      </form>
    </div>
  );
}
