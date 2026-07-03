const API = import.meta.env.VITE_API_URL || "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json();
}

export const api = {
  metrics: () => request<import("./types").Metrics>("/api/metrics"),
  runs: () => request<import("./types").Run[]>("/api/runs"),
  run: (id: string) => request<import("./types").RunDetail>(`/api/runs/${id}`),
  claims: (search = "") => request<{items: import("./types").Claim[]; total: number}>(`/api/claims?page_size=100&search=${encodeURIComponent(search)}`),
  events: () => request<import("./types").Event[]>("/api/schema-events"),
  upload: (file: File) => {
    const form = new FormData(); form.append("file", file);
    return request<{run: import("./types").RunDetail; message: string}>("/api/upload", { method: "POST", body: form });
  },
  approve: (id: string, mapping: Record<string, string>) =>
    request<import("./types").RunDetail>(`/api/runs/${id}/approve-mapping`, {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({mapping}),
    }),
};
