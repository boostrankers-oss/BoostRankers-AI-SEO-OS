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
  private readonly proactiveRefreshWindowMs = 60_000;
  private readonly refreshLockTtlMs = 15_000;
  private refreshTimer: number | null = null;
  private refreshChannel: BroadcastChannel | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");

    if (typeof window !== "undefined") {
      if ("BroadcastChannel" in window) {
        this.refreshChannel = new BroadcastChannel("boost-auth");
        this.refreshChannel.addEventListener("message", (event) => {
          const message = event.data as {
            type?: string;
            access_token?: string;
            refresh_token?: string;
            expires_in?: number;
          };

          if (message?.type !== "tokens-updated") return;
          if (!message.access_token || !message.refresh_token) return;

          this.storeTokenMetadata(
            message.access_token,
            message.refresh_token,
            message.expires_in,
          );
        });
      }

      this.scheduleProactiveRefresh();
    }
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
    localStorage.removeItem("boost_access_token_expires_at");
    localStorage.removeItem("boost_refresh_token_expires_at");

    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    window.dispatchEvent(new CustomEvent("auth:expired"));
  }

  private getTokenExpiry(token: string | null): number | null {
    if (!token) return null;

    try {
      const payloadPart = token.split(".")[1];
      if (!payloadPart) return null;

      const normalized = payloadPart
        .replace(/-/g, "+")
        .replace(/_/g, "/")
        .padEnd(Math.ceil(payloadPart.length / 4) * 4, "=");

      const payload = JSON.parse(atob(normalized)) as { exp?: number };
      return typeof payload.exp === "number"
        ? payload.exp * 1000
        : null;
    } catch {
      return null;
    }
  }

  private storeTokenMetadata(
    accessToken: string,
    refreshToken: string,
    expiresIn?: number,
  ): void {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);

    const accessExpiry =
      typeof expiresIn === "number" && expiresIn > 0
        ? Date.now() + expiresIn * 1000
        : this.getTokenExpiry(accessToken);

    const refreshExpiry = this.getTokenExpiry(refreshToken);

    if (accessExpiry) {
      localStorage.setItem(
        "boost_access_token_expires_at",
        String(accessExpiry),
      );
    }

    if (refreshExpiry) {
      localStorage.setItem(
        "boost_refresh_token_expires_at",
        String(refreshExpiry),
      );
    }

    this.scheduleProactiveRefresh();
  }

  private saveTokens(data: RefreshResponse): boolean {
    const tokens = data.tokens ?? data;
    const accessToken = tokens.access_token;
    const refreshToken = tokens.refresh_token;

    if (!accessToken || !refreshToken) {
      return false;
    }

    this.storeTokenMetadata(
      accessToken,
      refreshToken,
      tokens.expires_in,
    );

    try {
      this.refreshChannel?.postMessage({
        type: "tokens-updated",
        access_token: accessToken,
        refresh_token: refreshToken,
        expires_in: tokens.expires_in,
      });
    } catch {
      // Optional browser coordination.
    }

    return true;
  }

  private scheduleProactiveRefresh(): void {
    if (typeof window === "undefined") return;

    if (this.refreshTimer !== null) {
      window.clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    const accessToken = this.getToken();
    const refreshToken = this.getRefreshToken();

    if (!accessToken || !refreshToken) return;

    const storedExpiry = Number(
      localStorage.getItem("boost_access_token_expires_at") || "0",
    );

    const tokenExpiry =
      storedExpiry > 0
        ? storedExpiry
        : this.getTokenExpiry(accessToken);

    if (!tokenExpiry) return;

    const refreshAt = Math.max(
      10_000,
      tokenExpiry - Date.now() - this.proactiveRefreshWindowMs,
    );

    this.refreshTimer = window.setTimeout(() => {
      void this.refreshAccessToken();
    }, refreshAt);
  }

  private async ensureFreshAccessToken(): Promise<void> {
    const accessToken = this.getToken();
    const refreshToken = this.getRefreshToken();

    if (!accessToken || !refreshToken) return;

    const storedExpiry = Number(
      localStorage.getItem("boost_access_token_expires_at") || "0",
    );

    const expiry =
      storedExpiry > 0
        ? storedExpiry
        : this.getTokenExpiry(accessToken);

    if (!expiry) return;

    if (expiry - Date.now() <= this.proactiveRefreshWindowMs) {
      await this.refreshAccessToken();
    }
  }

  private async waitForOtherTabRefresh(
    originalRefreshToken: string,
  ): Promise<boolean> {
    const deadline = Date.now() + this.refreshLockTtlMs + 3_000;

    while (Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 150));

      const currentRefreshToken = this.getRefreshToken();

      if (
        currentRefreshToken &&
        currentRefreshToken !== originalRefreshToken &&
        this.getToken()
      ) {
        return true;
      }
    }

    return false;
  }

  private async runWithBrowserLock(
    task: () => Promise<boolean>,
  ): Promise<boolean> {
    if (
      typeof navigator !== "undefined" &&
      "locks" in navigator &&
      navigator.locks
    ) {
      return navigator.locks.request(
        "boost-auth-refresh",
        { mode: "exclusive" },
        async () => task(),
      );
    }

    return task();
  }

  private async performRefresh(refreshToken: string): Promise<boolean> {
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

    this.refreshRejected = false;

    this.refreshPromise = this.runWithBrowserLock(async () => {
      try {
        const currentRefreshToken = this.getRefreshToken();

        if (!currentRefreshToken) {
          this.refreshRejected = true;
          return false;
        }

        if (currentRefreshToken !== refreshToken) {
          return true;
        }

        const refreshed = await this.performRefresh(currentRefreshToken);

        if (refreshed) {
          return true;
        }

        if (!this.refreshRejected) {
          return false;
        }

        const reused = await this.waitForOtherTabRefresh(
          currentRefreshToken,
        );

        if (reused) {
          this.refreshRejected = false;
          return true;
        }

        return false;
      } catch (error) {
        console.error("Token refresh failed:", error);
        this.refreshRejected = false;
        return false;
      }
    });

    const refreshed = await this.refreshPromise;

    this.refreshPromise = null;
    this.scheduleProactiveRefresh();

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

    if (auth && !skipRefresh) {
      await this.ensureFreshAccessToken();
    }

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
