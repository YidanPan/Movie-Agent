/** Crew Assembly read helpers; event payloads, not decorative copy, drive state. */
export const agentLabel = (agent = "system") => String(agent || "system").replaceAll("_", " ").toUpperCase();

export function crewEventSummary(event = {}) {
  const type = String(event.type || "signal").toUpperCase();
  const agent = agentLabel(event.agent || event.from);
  return `${agent} · ${type}`;
}

export function moduleCrew() {
  return { agentLabel, crewEventSummary };
}

