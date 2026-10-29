import { apiFetch } from "./api-client";

export async function getDashboardData() {
  return apiFetch("/dashboard/");
}
