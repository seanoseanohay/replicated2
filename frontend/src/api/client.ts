const API_BASE = import.meta.env.VITE_API_URL ?? "";

export interface Bundle {
  id: string;
  filename: string;
  original_filename: string;
  size_bytes: number;
  status: "uploaded" | "processing" | "ready" | "error";
  tenant_id: string;
  s3_key: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface BundleListResponse {
  items: Bundle[];
  total: number;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  tenantId = "default"
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "X-Tenant-ID": tenantId,
      ...options.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const bundleApi = {
  list(tenantId = "default"): Promise<BundleListResponse> {
    return request<BundleListResponse>("/api/v1/bundles", {}, tenantId);
  },

  get(id: string, tenantId = "default"): Promise<Bundle> {
    return request<Bundle>(`/api/v1/bundles/${id}`, {}, tenantId);
  },

  upload(file: File, tenantId = "default"): Promise<Bundle> {
    const form = new FormData();
    form.append("file", file);
    return request<Bundle>(
      "/api/v1/bundles",
      { method: "POST", body: form },
      tenantId
    );
  },
};
