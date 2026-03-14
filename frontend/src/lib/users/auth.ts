export function mapFrontendRoleToBackend(role: string): string {
  if (!role) return "ROLE_USER";
  const r = role.toLowerCase();
  if (r.includes("admin")) return "ROLE_ADMIN";
  if (r.includes("manager")) return "ROLE_MANAGER";
  return "ROLE_USER";
}

export function mapFrontendTeamToBackend(team: string): string {
  if (!team) return "RESEARCH";
  return team.toUpperCase();
}

export function mapFrontendTypeToBackend(type: string): string {
  if (!type) return "CLC";
  return type.toUpperCase();
}