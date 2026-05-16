"""BOS Agent state schema (Phase A target).

The state object carried through the LangGraph ``StateGraph``. Phase A
will define the actual fields. Likely shape (subject to design review):

  AgentState:
    messages: list[BaseMessage]
    intent: Literal["ser", "sfi", "relay", "cyber_lab", "render", "noop"]
    core_responses: dict[str, Any]     # responses from BOS Core HTTP calls
    audit_trail: list[ToolCallRecord]
    requires_human_confirm: bool

Persistence will mirror BOS Core's existing ``brain_runtime`` document
model so operator-visible state is consistent across surfaces.
"""

# TODO(Phase A): define AgentState
