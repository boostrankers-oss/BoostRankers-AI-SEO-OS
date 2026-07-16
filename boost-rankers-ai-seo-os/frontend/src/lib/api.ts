const API_BASE_URL = "http://localhost:8000/api";

export interface Client {
  id: number;
  business_name: string;
  website: string;
  industry?: string;
  country?: string;
  city?: string;
  primary_keywords?: string;
  secondary_keywords?: string;
  competitors?: string;
  monthly_goals?: string;
  created_at: string;
}

export interface Audit {
  id: number;
  client_id?: number;
  url: string;
  primary_keyword: string;
  location?: string;
  competitors?: string;
  status: string;
  scores?: string;
  findings?: string;
  content_plan?: string;
  created_at: string;
}

export interface Config {
  is_configured: boolean;
}

async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    throw new Error(`API Error: ${response.statusText}`);
  }
  return response.json();
}

export const api = {
  getClients: () => fetchAPI("/clients/"),
  createClient: (data: Partial<Client>) => fetchAPI("/clients/", { method: "POST", body: JSON.stringify(data) }),
  deleteClient: (id: number) => fetchAPI(`/clients/${id}`, { method: "DELETE" }),

  getAudits: () => fetchAPI("/audits/"),
  createAudit: (data: Partial<Audit>) => fetchAPI("/audits/", { method: "POST", body: JSON.stringify(data) }),

  getConfig: () => fetchAPI("/config/"),
  updateConfig: (key: string) => fetchAPI("/config/", { method: "POST", body: JSON.stringify({ anthropic_api_key: key }) }),
};