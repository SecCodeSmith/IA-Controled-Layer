const ROLE_LABELS: Record<string, string> = {
  developer: 'Developer',
  hr: 'HR Specialist',
  finance: 'Finance',
}

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role
}

const REGION_NAMES: Record<string, string> = {
  PL: 'Poland',
  US: 'United States',
  DE: 'Germany',
  FR: 'France',
}

export function regionName(region: string): string {
  return REGION_NAMES[region] ?? region
}
