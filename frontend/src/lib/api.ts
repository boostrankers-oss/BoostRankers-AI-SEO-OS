const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    super(`API Error: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

type RequestOptions = RequestInit & {
  auth?: boolean;
  skipRefresh?: boolean;
};

interface RefreshResponse {
  access_token?: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  refresh_expires_in?: number;
  tokens?: {
    access_token?: string;
    refresh_token?: string;
    token_type?: string;
    expires_in?: number;
    refresh_expires_in?: number;
  };
}

class ApiClient {
  private readonly baseUrl: string;
  private refreshPromise: Promise<boolean> | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private getRefreshToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("refresh_token");
  }

  private clearAuthStorage(): void {
    if (typeof window === "undefined") return;

    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("boost_user");

    window.dispatchEvent(new CustomEvent("auth:expired"));
  }

  private saveTokens(data: RefreshResponse): boolean {
    const tokens = data.tokens ?? data;
    const accessToken = tokens.access_token;
    const refreshToken = tokens.refresh_token;

    if (!accessToken || !refreshToken) {
      return false;
    }

    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    return true;
  }

  private buildHeaders(
    headers?: HeadersInit,
    auth = true,
    hasBody = false
  ): Headers {
    const requestHeaders = new Headers(headers);

    if (hasBody && !requestHeaders.has("Content-Type")) {
      requestHeaders.set("Content-Type", "application/json");
    }

    if (auth) {
      const token = this.getToken();

      if (token) {
        requestHeaders.set("Authorization", `Bearer ${token}`);
      }
    }

    return requestHeaders;
  }

  private async parseError(response: Response): Promise<unknown> {
    const contentType = response.headers.get("content-type") || "";

    try {
      if (contentType.includes("application/json")) {
        return await response.json();
      }

      return await response.text();
    } catch {
      return null;
    }
  }

  private async refreshAccessToken(): Promise<boolean> {
    const refreshToken = this.getRefreshToken();

    if (!refreshToken) {
      this.clearAuthStorage();
      return false;
    }

    if (this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshPromise = (async () => {
      try {
        const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            refresh_token: refreshToken,
          }),
        });

        if (!response.ok) {
          return false;
        }

        const data = (await response.json()) as RefreshResponse;
        return this.saveTokens(data);
      } catch (error) {
        console.error("Token refresh failed:", error);
        return false;
      } finally {
        this.refreshPromise = null;
      }
    })();

    const refreshed = await this.refreshPromise;

    if (!refreshed) {
      this.clearAuthStorage();
    }

    return refreshed;
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {},
    retry = true
  ): Promise<T> {
    const {
      auth = true,
      skipRefresh = false,
      headers,
      body,
      ...rest
    } = options;

    const hasBody = body !== undefined && body !== null;

    const requestHeaders = this.buildHeaders(
      headers,
      auth,
      hasBody
    );

    const response = await fetch(`${this.baseUrl}${endpoint}`, {
      ...rest,
      headers: requestHeaders,
      body,
    });

    if (response.status === 401 && auth && retry && !skipRefresh) {
      const refreshed = await this.refreshAccessToken();

      if (refreshed) {
        return this.request<T>(
          endpoint,
          {
            ...options,
            skipRefresh: true,
          },
          false
        );
      }
    }

    if (!response.ok) {
      const errorData = await this.parseError(response);

      throw new ApiError(response.status, errorData);
    }

    if (response.status === 204) {
      return {} as T;
    }

    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }

    return (await response.text()) as T;
  }

  async get<T>(
    url: string,
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: "GET",
    });
  }

  async post<T>(
    url: string,
    body?: unknown,
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: "POST",
      body:
        body === undefined
          ? undefined
          : JSON.stringify(body),
    });
  }

  async put<T>(
    url: string,
    body?: unknown,
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: "PUT",
      body:
        body === undefined
          ? undefined
          : JSON.stringify(body),
    });
  }

  async patch<T>(
    url: string,
    body?: unknown,
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: "PATCH",
      body:
        body === undefined
          ? undefined
          : JSON.stringify(body),
    });
  }

  async delete<T>(
    url: string,
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: "DELETE",
    });
  }

  async upload<T>(
    url: string,
    file: File,
    field = "file",
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<T> {
    const form = new FormData();
    form.append(field, file);

    const headers = new Headers(options.headers);
    headers.delete("Content-Type");

    const token = this.getToken();

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(`${this.baseUrl}${url}`, {
      ...options,
      method: "POST",
      headers,
      body: form,
    });

    if (response.status === 401 && options.auth !== false) {
      const refreshed = await this.refreshAccessToken();

      if (refreshed) {
        const retryHeaders = new Headers(options.headers);
        retryHeaders.delete("Content-Type");

        const newToken = this.getToken();
        if (newToken) {
          retryHeaders.set("Authorization", `Bearer ${newToken}`);
        }

        return this.upload<T>(url, file, field, {
          ...options,
          headers: retryHeaders,
          auth: true,
        });
      }
    }

    if (!response.ok) {
      const errorData = await this.parseError(response);
      throw new ApiError(response.status, errorData);
    }

    if (response.status === 204) {
      return {} as T;
    }

    const contentType = response.headers.get("content-type") || "";

    if (contentType.includes("application/json")) {
      return (await response.json()) as T;
    }

    return (await response.text()) as T;
  }

  async download(
    url: string,
    options: Omit<RequestOptions, "method" | "body"> = {}
  ): Promise<Blob> {
    const {
      auth = true,
      headers,
      ...rest
    } = options;

    const requestHeaders = this.buildHeaders(
      headers,
      auth,
      false
    );

    let response = await fetch(`${this.baseUrl}${url}`, {
      ...rest,
      method: "GET",
      headers: requestHeaders,
    });

    if (response.status === 401 && auth) {
      const refreshed = await this.refreshAccessToken();

      if (refreshed) {
        response = await fetch(`${this.baseUrl}${url}`, {
          ...rest,
          method: "GET",
          headers: this.buildHeaders(headers, true, false),
        });
      }
    }

    if (!response.ok) {
      const errorData = await this.parseError(response);
      throw new ApiError(response.status, errorData);
    }

    return response.blob();
  }

  stream(url: string): EventSource {
    return new EventSource(`${this.baseUrl}${url}`);
  }
}

export const api = new ApiClient(API_BASE_URL);

export { ApiError };
