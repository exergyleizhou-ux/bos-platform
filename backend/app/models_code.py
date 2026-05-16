"""
BOS Code v9.0 ORM models.

This module defines the BOS Code persistence layer as a first-class
tenant-scoped subdomain inside the canonical BOS repository.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SQLITE_BIGINT_PK = BigInteger().with_variant(Integer, "sqlite")


class CodeWorkspace(Base):
    __tablename__ = "code_workspaces"
    __table_args__ = (UniqueConstraint("tenant_id", name="uq_code_workspaces_tenant_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    repo_root: Mapped[str] = mapped_column(String(500), nullable=False)
    worktree_root: Mapped[str] = mapped_column(String(500), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    active_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    workspace_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="ready", index=True)
    base_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dirty_state: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["CodeSession"]] = relationship(
        "CodeSession", back_populates="workspace", cascade="all, delete-orphan"
    )
    lease: Mapped[Optional["CodeWorkspaceLease"]] = relationship(
        "CodeWorkspaceLease", back_populates="workspace", uselist=False, cascade="all, delete-orphan"
    )
    branch_states: Mapped[list["CodeBranchState"]] = relationship(
        "CodeBranchState", back_populates="workspace", cascade="all, delete-orphan"
    )
    mcp_servers: Mapped[list["CodeMcpServer"]] = relationship(
        "CodeMcpServer", back_populates="workspace", cascade="all, delete-orphan"
    )
    lsp_sessions: Mapped[list["CodeLspSession"]] = relationship(
        "CodeLspSession", back_populates="workspace", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["CodeTask"]] = relationship(
        "CodeTask", back_populates="workspace", cascade="all, delete-orphan"
    )
    workers: Mapped[list["CodeWorker"]] = relationship(
        "CodeWorker", back_populates="workspace", cascade="all, delete-orphan"
    )
    worker_events: Mapped[list["CodeWorkerEvent"]] = relationship(
        "CodeWorkerEvent", back_populates="workspace", cascade="all, delete-orphan"
    )
    automation_jobs: Mapped[list["CodeAutomationJob"]] = relationship(
        "CodeAutomationJob", back_populates="workspace", cascade="all, delete-orphan"
    )
    runtime_state: Mapped[Optional["CodeAgentRuntimeState"]] = relationship(
        "CodeAgentRuntimeState", back_populates="workspace", uselist=False, cascade="all, delete-orphan"
    )
    memory_snapshots: Mapped[list["CodeMemorySnapshot"]] = relationship(
        "CodeMemorySnapshot", back_populates="workspace", cascade="all, delete-orphan"
    )
    subagent_runs: Mapped[list["CodeSubagentRun"]] = relationship(
        "CodeSubagentRun", back_populates="workspace", cascade="all, delete-orphan"
    )
    reflection_runs: Mapped[list["CodeReflectionRun"]] = relationship(
        "CodeReflectionRun", back_populates="workspace", cascade="all, delete-orphan"
    )
    skills: Mapped[list["CodeSkill"]] = relationship(
        "CodeSkill", back_populates="workspace", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CodeWorkspace(id={self.id}, tenant_id={self.tenant_id}, status='{self.workspace_status}')>"


class CodeSession(Base):
    __tablename__ = "code_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(150), nullable=False)
    permission_mode: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    session_branch: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    session_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="created", index=True)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="sessions")
    lease: Mapped[Optional["CodeWorkspaceLease"]] = relationship(
        "CodeWorkspaceLease", back_populates="active_session", uselist=False
    )
    turns: Mapped[list["CodeTurn"]] = relationship("CodeTurn", back_populates="session", cascade="all, delete-orphan")
    tool_calls: Mapped[list["CodeToolCall"]] = relationship(
        "CodeToolCall", back_populates="session", cascade="all, delete-orphan"
    )
    events: Mapped[list["CodeEvent"]] = relationship("CodeEvent", back_populates="session", cascade="all, delete-orphan")
    artifacts: Mapped[list["CodeArtifact"]] = relationship(
        "CodeArtifact", back_populates="session", cascade="all, delete-orphan"
    )
    verification_runs: Mapped[list["CodeVerificationRun"]] = relationship(
        "CodeVerificationRun", back_populates="session", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["CodeTask"]] = relationship("CodeTask", back_populates="session", cascade="all, delete-orphan")
    memory_snapshots: Mapped[list["CodeMemorySnapshot"]] = relationship(
        "CodeMemorySnapshot", back_populates="session", cascade="all, delete-orphan"
    )
    subagent_runs: Mapped[list["CodeSubagentRun"]] = relationship(
        "CodeSubagentRun", back_populates="session", cascade="all, delete-orphan"
    )
    reflection_runs: Mapped[list["CodeReflectionRun"]] = relationship(
        "CodeReflectionRun", back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CodeSession(id={self.id}, tenant_id={self.tenant_id}, status='{self.session_status}')>"


class CodeWorkspaceLease(Base):
    __tablename__ = "code_workspace_leases"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_code_workspace_leases_workspace_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    active_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lease_owner_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lease_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="available", index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="lease")
    active_session: Mapped[Optional["CodeSession"]] = relationship("CodeSession", back_populates="lease")

    def __repr__(self) -> str:
        return f"<CodeWorkspaceLease(id={self.id}, workspace_id={self.workspace_id}, status='{self.lease_status}')>"


class CodeTurn(Base):
    __tablename__ = "code_turns"
    __table_args__ = (UniqueConstraint("session_id", "turn_index", name="uq_code_turns_session_turn_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="created", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="turns")
    tool_calls: Mapped[list["CodeToolCall"]] = relationship(
        "CodeToolCall", back_populates="turn", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CodeTurn(id={self.id}, session_id={self.session_id}, turn_index={self.turn_index})>"


class CodeToolCall(Base):
    __tablename__ = "code_tool_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_turns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tool_class: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    was_denied: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    denial_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="tool_calls")
    turn: Mapped[Optional["CodeTurn"]] = relationship("CodeTurn", back_populates="tool_calls")

    def __repr__(self) -> str:
        return f"<CodeToolCall(id={self.id}, tool_name='{self.tool_name}', denied={self.was_denied})>"


class CodeEvent(Base):
    __tablename__ = "code_events"
    __table_args__ = (
        UniqueConstraint("session_id", "seq_no", name="uq_code_events_session_seq_no"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_code_events_session_idempotency_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="events")

    def __repr__(self) -> str:
        return f"<CodeEvent(id={self.id}, session_id={self.session_id}, seq_no={self.seq_no})>"


class CodeArtifact(Base):
    __tablename__ = "code_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    base_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    export_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="artifacts")

    def __repr__(self) -> str:
        return f"<CodeArtifact(id={self.id}, session_id={self.session_id}, type='{self.artifact_type}')>"


class CodeVerificationRun(Base):
    __tablename__ = "code_verification_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    verification_stage: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    log_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="verification_runs")

    def __repr__(self) -> str:
        return (
            f"<CodeVerificationRun(id={self.id}, session_id={self.session_id}, "
            f"stage='{self.verification_stage}', status='{self.verification_status}')>"
        )


class CodeBranchState(Base):
    __tablename__ = "code_branch_states"
    __table_args__ = (UniqueConstraint("workspace_id", "branch_name", name="uq_code_branch_states_workspace_branch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    merge_base_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_dirty: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    is_stale_against_base: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false", index=True)
    ahead_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    behind_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    branch_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="clean", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="branch_states")

    def __repr__(self) -> str:
        return (
            f"<CodeBranchState(id={self.id}, workspace_id={self.workspace_id}, "
            f"branch='{self.branch_name}', status='{self.branch_status}')>"
        )


class CodeMcpServer(Base):
    __tablename__ = "code_mcp_servers"
    __table_args__ = (UniqueConstraint("workspace_id", "server_name", name="uq_code_mcp_servers_workspace_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    server_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    transport: Mapped[str] = mapped_column(String(50), nullable=False, server_default="stub")
    connection_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="disconnected", index=True)
    capabilities: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="mcp_servers")

    def __repr__(self) -> str:
        return (
            f"<CodeMcpServer(id={self.id}, workspace_id={self.workspace_id}, "
            f"name='{self.server_name}', status='{self.connection_status}')>"
        )


class CodeLspSession(Base):
    __tablename__ = "code_lsp_sessions"
    __table_args__ = (UniqueConstraint("workspace_id", "language", name="uq_code_lsp_sessions_workspace_language"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    language: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    server_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="idle", index=True)
    root_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="lsp_sessions")

    def __repr__(self) -> str:
        return (
            f"<CodeLspSession(id={self.id}, workspace_id={self.workspace_id}, "
            f"language='{self.language}', status='{self.status}')>"
        )


class CodeTask(Base):
    __tablename__ = "code_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_packet: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    task_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="created", index=True)
    priority: Mapped[str] = mapped_column(String(50), nullable=False, server_default="normal", index=True)
    acceptance_criteria: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="tasks")
    session: Mapped[Optional["CodeSession"]] = relationship("CodeSession", back_populates="tasks")
    workers: Mapped[list["CodeWorker"]] = relationship("CodeWorker", back_populates="task")
    events: Mapped[list["CodeWorkerEvent"]] = relationship("CodeWorkerEvent", back_populates="task")
    subagent_runs: Mapped[list["CodeSubagentRun"]] = relationship("CodeSubagentRun", back_populates="task")
    reflection_runs: Mapped[list["CodeReflectionRun"]] = relationship("CodeReflectionRun", back_populates="task")
    skills: Mapped[list["CodeSkill"]] = relationship("CodeSkill", back_populates="origin_task")

    def __repr__(self) -> str:
        return (
            f"<CodeTask(id={self.id}, workspace_id={self.workspace_id}, "
            f"title='{self.title}', status='{self.task_status}')>"
        )


class CodeWorker(Base):
    __tablename__ = "code_workers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    worker_name: Mapped[str] = mapped_column(String(150), nullable=False)
    worker_role: Mapped[str] = mapped_column(String(100), nullable=False)
    worker_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="spawning", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_event_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="workers")
    task: Mapped[Optional["CodeTask"]] = relationship("CodeTask", back_populates="workers")
    events: Mapped[list["CodeWorkerEvent"]] = relationship("CodeWorkerEvent", back_populates="worker")
    subagent_runs: Mapped[list["CodeSubagentRun"]] = relationship("CodeSubagentRun", back_populates="worker")

    def __repr__(self) -> str:
        return (
            f"<CodeWorker(id={self.id}, workspace_id={self.workspace_id}, "
            f"name='{self.worker_name}', status='{self.worker_status}')>"
        )


class CodeWorkerEvent(Base):
    __tablename__ = "code_worker_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    worker_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_workers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    lane: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="worker_events")
    task: Mapped[Optional["CodeTask"]] = relationship("CodeTask", back_populates="events")
    worker: Mapped[Optional["CodeWorker"]] = relationship("CodeWorker", back_populates="events")

    def __repr__(self) -> str:
        return (
            f"<CodeWorkerEvent(id={self.id}, workspace_id={self.workspace_id}, lane='{self.lane}', "
            f"event_name='{self.event_name}', status='{self.status}')>"
        )


class CodeAutomationJob(Base):
    __tablename__ = "code_automation_jobs"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_code_automation_jobs_workspace_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="cron", index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", index=True)
    schedule_kind: Mapped[str] = mapped_column(String(50), nullable=False, server_default="manual")
    cron_expr: Mapped[str | None] = mapped_column(String(120), nullable=True)
    interval_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_scope: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="automation_jobs")


class CodeAgentRuntimeState(Base):
    __tablename__ = "code_agent_runtime_states"
    __table_args__ = (UniqueConstraint("workspace_id", name="uq_code_agent_runtime_states_workspace_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    heartbeat_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    memory_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    reflections_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    last_heartbeat_decision: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_memory_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reflection_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_compressed_turn_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    runtime_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="runtime_state")


class CodeMemorySnapshot(Base):
    __tablename__ = "code_memory_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    snapshot_kind: Mapped[str] = mapped_column(String(50), nullable=False, server_default="summary", index=True)
    source_turn_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_turn_end: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    history_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="memory_snapshots")
    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="memory_snapshots")


class CodeSubagentRun(Base):
    __tablename__ = "code_subagent_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    worker_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_workers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    run_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="subagent_runs")
    session: Mapped[Optional["CodeSession"]] = relationship("CodeSession", back_populates="subagent_runs")
    task: Mapped[Optional["CodeTask"]] = relationship("CodeTask", back_populates="subagent_runs")
    worker: Mapped[Optional["CodeWorker"]] = relationship("CodeWorker", back_populates="subagent_runs")


class CodeSkill(Base):
    __tablename__ = "code_skills"
    __table_args__ = (UniqueConstraint("workspace_id", "slug", name="uq_code_skills_workspace_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    origin_task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="draft", index=True)
    directory_path: Mapped[str] = mapped_column(String(500), nullable=False)
    latest_revision_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    positive_feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    negative_feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="skills")
    origin_task: Mapped[Optional["CodeTask"]] = relationship("CodeTask", back_populates="skills")
    revisions: Mapped[list["CodeSkillRevision"]] = relationship(
        "CodeSkillRevision", back_populates="skill", cascade="all, delete-orphan"
    )
    reflection_runs: Mapped[list["CodeReflectionRun"]] = relationship("CodeReflectionRun", back_populates="skill")


class CodeReflectionRun(Base):
    __tablename__ = "code_reflection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_skills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trigger_source: Mapped[str] = mapped_column(String(50), nullable=False, server_default="manual", index=True)
    reflection_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="pending", index=True)
    output_kind: Mapped[str] = mapped_column(String(50), nullable=False, server_default="memory_update", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    workspace: Mapped["CodeWorkspace"] = relationship("CodeWorkspace", back_populates="reflection_runs")
    session: Mapped["CodeSession"] = relationship("CodeSession", back_populates="reflection_runs")
    task: Mapped[Optional["CodeTask"]] = relationship("CodeTask", back_populates="reflection_runs")
    skill: Mapped[Optional["CodeSkill"]] = relationship("CodeSkill", back_populates="reflection_runs")


class CodeSkillRevision(Base):
    __tablename__ = "code_skill_revisions"
    __table_args__ = (UniqueConstraint("skill_id", "revision_number", name="uq_code_skill_revisions_skill_revision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    skill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("code_skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reflection_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("code_reflection_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision_status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="draft", index=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    skill: Mapped["CodeSkill"] = relationship("CodeSkill", back_populates="revisions")
