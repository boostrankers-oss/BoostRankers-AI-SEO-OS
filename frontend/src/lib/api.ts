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
  private refreshRejected = false;
  private readonly refreshLockKey = "boost_auth_refresh_lock";
  private readonly refreshLockOwner =
    typeof window !== "undefined"
      ? `${Date.now()}-${Math.random().toString(36).slice(2)}`
      : "server";
  private readonly refreshLockTtlMs = 15_000;

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

  private async waitForOtherTabRefresh(
    originalRefreshToken: string,
  ): Promise<boolean> {
    const deadline = Date.now() + this.refreshLockTtlMs + 2_000;

    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 150));

      const currentRefreshToken = this.getRefreshToken();

      // Another tab may already have rotated the token successfully.
      if (
        currentRefreshToken &&
        currentRefreshToken !== originalRefreshToken &&
        this.getToken()
      ) {
        return true;
      }

      const lockRaw = localStorage.getItem(this.refreshLockKey);
      if (!lockRaw) {
        return false;
      }

      try {
        const lock = JSON.parse(lockRaw) as {
          owner?: string;
          expiresAt?: number;
        };

        if (!lock.expiresAt || lock.expiresAt <= Date.now()) {
          return false;
        }
      } catch {
        return false;
      }
    }

    return false;
  }

  private acquireRefreshLock(): boolean {
    const now = Date.now();

    try {
      const existingRaw = localStorage.getItem(this.refreshLockKey);

      if (existingRaw) {
        try {
          const existing = JSON.parse(existingRaw) as {
            owner?: string;
            expiresAt?: number;
          };

          if (
            existing.owner &&
            existing.owner !== this.refreshLockOwner &&
            typeof existing.expiresAt === "number" &&
            existing.expiresAt > now
          ) {
            return false;
          }
        } catch {
          // Replace malformed/stale lock.
        }
      }

      localStorage.setItem(
        this.refreshLockKey,
        JSON.stringify({
          owner: this.refreshLockOwner,
          expiresAt: now + this.refreshLockTtlMs,
        }),
      );

      const verifyRaw = localStorage.getItem(this.refreshLockKey);
      if (!verifyRaw) return false;

      const verify = JSON.parse(verifyRaw) as {
        owner?: string;
        expiresAt?: number;
      };

      return verify.owner === this.refreshLockOwner;
    } catch {
      // If localStorage is unavailable, preserve the existing in-tab mutex.
      return true;
    }
  }

  private releaseRefreshLock(): void {
    try {
      const raw = localStorage.getItem(this.refreshLockKey);
      if (!raw) return;

      const lock = JSON.parse(raw) as { owner?: string };
      if (lock.owner === this.refreshLockOwner) {
        localStorage.removeItem(this.refreshLockKey);
      }
    } catch {
      // Nothing to do.
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

    this.refreshRejected = false;

    this.refreshPromise = (async () => {
      let ownsLock = false;

      try {
        ownsLock = this.acquireRefreshLock();

        if (!ownsLock) {
          // Another browser tab is rotating this refresh token. Wait for it
          // and then use the newly stored access/refresh tokens.
          const reused = await this.waitForOtherTabRefresh(refreshToken);
          if (reused) {
            return true;
          }

          // The other tab stopped without rotating the token. Re-read the
          // current token before attempting the refresh ourselves.
          const currentRefreshToken = this.getRefreshToken();
          if (!currentRefreshToken) {
            this.refreshRejected = true;
            return false;
          }
        }

        const tokenForRequest = this.getRefreshToken();
        if (!tokenForRequest) {
          this.refreshRejected = true;
          return false;
        }

        const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            refresh_token: tokenForRequest,
          }),
        });

        if (!response.ok) {
          if (
            response.status === 400 ||
            response.status === 401 ||
            response.status === 403
          ) {
            this.refreshRejected = true;
          }
          return false;
        }

        const data = (await response.json()) as RefreshResponse;
        return this.saveTokens(data);
      } catch (error) {
        console.error("Token refresh failed:", error);
        this.refreshRejected = false;
        return false;
      } finally {
        if (ownsLock) {
          this.releaseRefreshLock();
        }
        this.refreshPromise = null;
      }
    })();

    const refreshed = await this.refreshPromise;

    if (!refreshed && this.refreshRejected) {
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

    let response: Response;

    try {
      response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...rest,
        headers: requestHeaders,
        body,
      });
    } catch (error) {
      const method = String(rest.method || "GET").toUpperCase();
      const canRetryTransport =
        retry &&
        !skipRefresh &&
        (method === "GET" || method === "HEAD" || method === "OPTIONS");

      if (!canRetryTransport) {
        throw error;
      }

      await new Promise((resolve) => setTimeout(resolve, 250));

      response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...rest,
        headers: requestHeaders,
        body,
      });
    }

    if (
      response.status >= 500 &&
      response.status <= 504 &&
      retry &&
      !skipRefresh &&
      String(rest.method || "GET").toUpperCase() === "GET"
    ) {
      await new Promise((resolve) => setTimeout(resolve, 250));

      response = await fetch(`${this.baseUrl}${endpoint}`, {
        ...rest,
        headers: requestHeaders,
        body,
      });
    }

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
