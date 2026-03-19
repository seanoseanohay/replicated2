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

export interface Finding {
  id: string;
  bundle_id: string;
  rule_id: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  summary: string;
  evidence_ids: string[];
  status: "open" | "acknowledged" | "resolved";
  reviewer_notes: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  ai_explanation: string | null;
  ai_remediation: string | null;
  ai_explained_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface FindingListResponse {
  items: Finding[];
  total: number;
}

export interface FindingUpdate {
  status?: "open" | "acknowledged" | "resolved";
  reviewer_notes?: string;
  reviewed_by?: string;
}

export interface EvidenceRead {
  id: string;
  bundle_id: string;
  kind: string;
  name: string;
  namespace: string | null;
  source_path: string;
  raw_data: Record<string, unknown>;
  created_at: string;
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

async function requestText(
  path: string,
  options: RequestInit = {},
  tenantId = "default"
): Promise<string> {
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
  return res.text();
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

  uploadWithProgress(
    file: File,
    tenantId = "default",
    onProgress?: (pct: number) => void
  ): Promise<Bundle> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const form = new FormData();
      form.append("file", file);

      xhr.open("POST", `${API_BASE}/api/v1/bundles`);
      xhr.setRequestHeader("X-Tenant-ID", tenantId);

      if (onProgress) {
        xhr.upload.addEventListener("progress", (e) => {
          if (e.lengthComputable) {
            onProgress(Math.round((e.loaded / e.total) * 100));
          }
        });
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(`Upload failed: ${xhr.status} ${xhr.responseText}`));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(form);
    });
  },

  delete(id: string, tenantId = "default"): Promise<void> {
    return request<void>(`/api/v1/bundles/${id}`, { method: "DELETE" }, tenantId);
  },
};

export const findingApi = {
  list(
    bundleId: string,
    params?: { severity?: string; status?: string },
    tenantId = "default"
  ): Promise<FindingListResponse> {
    const qs = new URLSearchParams();
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.status) qs.set("finding_status", params.status);
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return request<FindingListResponse>(
      `/api/v1/bundles/${bundleId}/findings${query}`,
      {},
      tenantId
    );
  },

  update(
    bundleId: string,
    findingId: string,
    update: FindingUpdate,
    tenantId = "default"
  ): Promise<Finding> {
    return request<Finding>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(update),
      },
      tenantId
    );
  },

  explain(bundleId: string, findingId: string, tenantId = "default"): Promise<Finding> {
    return request<Finding>(
      `/api/v1/bundles/${bundleId}/findings/${findingId}/explain`,
      { method: "POST" },
      tenantId
    );
  },

  downloadReport(bundleId: string, tenantId = "default"): Promise<string> {
    return requestText(`/api/v1/bundles/${bundleId}/report.md`, {}, tenantId);
  },
};

export const evidenceApi = {
  getEvidence(bundleId: string, evidenceId: string, tenantId = "default"): Promise<EvidenceRead> {
    return request<EvidenceRead>(
      `/api/v1/bundles/${bundleId}/evidence/${evidenceId}`,
      {},
      tenantId
    );
  },
};
