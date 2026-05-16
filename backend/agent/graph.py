"""BOS Agent LangGraph ``StateGraph`` entry point.

Phase A will implement the actual graph here. Planned nodes (per V5
target architecture):

  router_node        → routes operator intent to the correct compute node
  ser_node           → calls BOS Core /ser/compute via HTTP
  sfi_node           → calls Signal/Forecast Integration
  relay_node         → routes between BOS stages
  cyber_lab_node     → runs simulation lab scenarios
  render_node        → produces operator-facing reports

For now, this module is a placeholder — importing it should not pull in
``langgraph`` so that Phase 0.5 verification does not require installing
heavy dependencies.
"""

# TODO(Phase A): build the StateGraph
