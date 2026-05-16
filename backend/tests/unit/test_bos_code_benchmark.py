from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "bos_code_benchmark.py"


def _load_module():
    spec = spec_from_file_location("bos_code_benchmark", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_scaffold_creates_toolathlon_style_task_fixture(tmp_path):
    module = _load_module()

    task_dir = module.scaffold_task(tmp_path, "BOS Code Smoke")

    assert task_dir.name == "bos-code-smoke"
    assert (task_dir / "task.json").exists()
    assert (task_dir / "docs" / "task.md").exists()
    assert (task_dir / "initial_workspace").exists()
    assert (task_dir / "preprocess.py").exists()
    assert (task_dir / "evaluate.py").exists()

    config = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
    assert config["name"] == "bos-code-smoke"
    assert isinstance(config["command"], list)
    assert config["command"][0] == "{python}"
    assert config["working_directory"] == "{workspace_dir}"


def test_run_suite_executes_preprocess_and_evaluation_hooks(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    task_dir = task_root / "local-smoke"
    (task_dir / "docs").mkdir(parents=True)
    (task_dir / "initial_workspace").mkdir()
    (task_dir / "initial_workspace" / "seed.txt").write_text("seed\n", encoding="utf-8")
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "name": "local-smoke",
                "description": "Ensure the benchmark harness executes command and evaluator.",
                "command": [
                    "{python}",
                    "-c",
                    "from pathlib import Path; import os; Path(os.environ['BOS_BENCHMARK_WORKSPACE_DIR']).joinpath('artifact.txt').write_text('ok', encoding='utf-8')",
                ],
                "working_directory": "{task_dir}",
                "timeout_sec": 30,
                "env": {"LOCAL_TASK_NAME": "{task_name}"},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "preprocess.py").write_text(
        "from pathlib import Path\n\n"
        "def prepare(context: dict) -> dict:\n"
        "    workspace = Path(context['workspace_dir'])\n"
        "    workspace.joinpath('prepared.txt').write_text('ready', encoding='utf-8')\n"
        "    return {'prepared': True}\n",
        encoding="utf-8",
    )
    (task_dir / "evaluate.py").write_text(
        "from pathlib import Path\n\n"
        "def evaluate(context: dict) -> dict:\n"
        "    workspace = Path(context['workspace_dir'])\n"
        "    passed = (\n"
        "        workspace.joinpath('prepared.txt').read_text(encoding='utf-8') == 'ready'\n"
        "        and workspace.joinpath('artifact.txt').read_text(encoding='utf-8') == 'ok'\n"
        "        and context['command_result']['exit_code'] == 0\n"
        "    )\n"
        "    return {'pass': passed, 'summary': 'hooks and command completed'}\n",
        encoding="utf-8",
    )

    results, summary_path = module.run_suite(
        task_root=task_root,
        output_root=tmp_path / 'reports',
        selected_tasks=["local-smoke"],
        suite=None,
        max_concurrent=1,
    )

    assert len(results) == 1
    assert results[0].passed is True
    assert results[0].summary == "hooks and command completed"
    assert Path(results[0].workspace_dir, "prepared.txt").read_text(encoding="utf-8") == "ready"
    assert Path(results[0].workspace_dir, "artifact.txt").read_text(encoding="utf-8") == "ok"
    assert "local-smoke" in summary_path.read_text(encoding="utf-8")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["totals"]["passed"] == 1
    assert summary["results"][0]["task_name"] == "local-smoke"


def test_discover_tasks_filters_by_suite(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    runtime_dir = task_root / "runtime-smoke"
    operator_dir = task_root / "operator-smoke"
    for directory, suites in ((runtime_dir, ["starter", "runtime"]), (operator_dir, ["starter", "operator"])):
        directory.mkdir(parents=True)
        (directory / "task.json").write_text(
            json.dumps(
                {
                    "name": directory.name,
                    "description": directory.name,
                    "suites": suites,
                    "command": ["{python}", "-c", "print('ok')"],
                    "working_directory": "{workspace_dir}",
                    "timeout_sec": 30,
                    "env": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    runtime_tasks = module.discover_tasks(task_root, suite="runtime")
    operator_tasks = module.discover_tasks(task_root, suite="operator")

    assert [task.task_dir.name for task in runtime_tasks] == ["runtime-smoke"]
    assert [task.task_dir.name for task in operator_tasks] == ["operator-smoke"]


def test_load_suite_catalog_reads_manifest(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    task_root.mkdir(parents=True)
    (task_root / "suites.json").write_text(
        json.dumps(
            {
                "runtime": {
                    "label": "Runtime",
                    "description": "Runtime slices",
                    "ci_enabled": True,
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    catalog = module.load_suite_catalog(task_root)

    assert catalog["runtime"]["label"] == "Runtime"
    assert catalog["runtime"]["description"] == "Runtime slices"
    assert catalog["runtime"]["ci_enabled"] is True


def test_list_suite_names_can_filter_ci_enabled(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    task_root.mkdir(parents=True)
    (task_root / "suites.json").write_text(
        json.dumps(
            {
                "runtime": {"label": "Runtime", "description": "Runtime slices", "ci_enabled": True},
                "custom": {"label": "Custom", "description": "Custom slices", "ci_enabled": False},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    assert module.list_suite_names(task_root) == ["runtime", "custom"]
    assert module.list_suite_names(task_root, ci_only=True) == ["runtime"]


def test_build_task_index_markdown_groups_tasks_by_ci_suite(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    task_root.mkdir(parents=True)
    (task_root / "suites.json").write_text(
        json.dumps(
            {
                "runtime": {"label": "Runtime", "description": "Runtime slices", "ci_enabled": True},
                "protocol": {"label": "Protocol", "description": "Protocol slices", "ci_enabled": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for name, suites, description in (
        ("runtime-smoke", ["starter", "runtime"], "Runtime task"),
        ("protocol-smoke", ["starter", "protocol"], "Protocol task"),
    ):
        directory = task_root / name
        directory.mkdir(parents=True)
        (directory / "task.json").write_text(
            json.dumps(
                {
                    "name": name,
                    "description": description,
                    "suites": suites,
                    "command": ["{python}", "-c", "print('ok')"],
                    "working_directory": "{workspace_dir}",
                    "timeout_sec": 30,
                    "env": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    markdown = module.build_task_index_markdown(task_root)

    assert "### Runtime" in markdown
    assert "### Protocol" in markdown
    assert "- `runtime-smoke`" in markdown
    assert "- `protocol-smoke`" in markdown


def test_build_root_benchmark_section_uses_ci_suites(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    task_root.mkdir(parents=True)
    (task_root / "suites.json").write_text(
        json.dumps(
            {
                "runtime": {"label": "Runtime", "description": "Runtime slices", "ci_enabled": True},
                "operator": {"label": "Operator", "description": "Operator slices", "ci_enabled": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    section = module.build_root_benchmark_section(task_root)

    assert "## BOS Code benchmark harness" in section
    assert "- `make test-benchmarks-runtime`" in section
    assert "- `make test-benchmarks-operator`" in section
    assert "- `runtime`: Runtime" in section
    assert "- `operator`: Operator" in section


def test_verify_generated_docs_accepts_synced_outputs(tmp_path):
    module = _load_module()

    task_root = tmp_path / "benchmark_tasks"
    task_root.mkdir(parents=True)
    (task_root / "suites.json").write_text(
        json.dumps(
            {
                "runtime": {"label": "Runtime", "description": "Runtime slices", "ci_enabled": True},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    task_dir = task_root / "runtime-smoke"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "name": "runtime-smoke",
                "description": "Runtime task",
                "suites": ["starter", "runtime"],
                "command": ["{python}", "-c", "print('ok')"],
                "working_directory": "{workspace_dir}",
                "timeout_sec": 30,
                "env": {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    benchmark_readme = task_root / "README.md"
    benchmark_readme.write_text(module.build_task_index_markdown(task_root) + "\n", encoding="utf-8")
    root_readme = tmp_path / "README.md"
    root_readme.write_text(
        "# Temp\n\n"
        "<!-- BEGIN GENERATED: BOS_BENCHMARKS -->old<!-- END GENERATED: BOS_BENCHMARKS -->\n",
        encoding="utf-8",
    )
    module.sync_root_readme_benchmark_section(task_root, root_readme_path=root_readme)

    module.verify_generated_docs(task_root, benchmark_readme_path=benchmark_readme, root_readme_path=root_readme)
