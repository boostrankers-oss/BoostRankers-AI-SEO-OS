const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(`API Error: ${status}`);
    this.status = status;
    this.data = data;
  }
}

type RequestOptions = RequestInit & {
  auth?: boolean;
};

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private getToken(): string | null {
    return localStorage.getItem("access_token");
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const { auth = true, headers, ...rest } = options;

    const requestHeaders: HeadersInit = {
      "Content-Type": "application/json",
      ...headers,
    };

    if (auth) {
      const token = this.getToken();

      if (token) {
        requestHeaders["Authorization"] = `Bearer ${token}`;
      }
    }

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...rest,
      headers: requestHeaders,
    });

    if (!response.ok) {
      let errorData: unknown = null;

      try {
        errorData = await response.json();
      } catch {
        errorData = await response.text();
      }

      throw new ApiError(response.status, errorData);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  get<T>(url: string) {
    return this.request<T>(url, {
      method: "GET",
    });
  }

  post<T>(url: string, body?: unknown) {
    return this.request<T>(url, {
      method: "POST",
      body: JSON.stringify(body),
    });
  }

  put<T>(url: string, body?: unknown) {
    return this.request<T>(url, {
      method: "PUT",
      body: JSON.stringify(body),
    });
  }

  patch<T>(url: string, body?: unknown) {
    return this.request<T>(url, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }

  delete<T>(url: string) {
    return this.request<T>(url, {
      method: "DELETE",
    });
  }

  upload<T>(url: string, file: File, field = "file") {
    const form = new FormData();

    form.append(field, file);

    const token = this.getToken();

    return fetch(`${this.baseUrl}${url}`, {
      method: "POST",
      headers: token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {},
      body: form,
    }).then(async (res) => {
      if (!res.ok) {
        throw new Error(await res.text());
      }

      return res.json() as Promise<T>;
    });
  }

  stream(url: string): EventSource {
    return new EventSource(`${this.baseUrl}${url}`);
  }
}

export const api = new ApiClient(API_BASE_URL);

export { ApiError };