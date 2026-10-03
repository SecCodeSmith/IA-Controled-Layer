export const MCP_SERVER_LABELS: Record<string, string> = {
  github: 'GitHub',
  ci: 'CI pipeline',
  'logs-db': 'Logs DB',
  jira: 'Jira',
  'hr-db': 'HR database',
  calendar: 'Calendar',
  mail: 'Mail',
  payments: 'Payments',
  'eu-customers': 'EU customers',
}

export function mcpServerLabel(server: string): string {
  return MCP_SERVER_LABELS[server] ?? server
}
