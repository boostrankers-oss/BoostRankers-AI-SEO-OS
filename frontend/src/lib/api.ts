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
};

class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private getToken(): string | null {
    if (typeof window === "undefined") {
      return null;
    }

    return localStorage.getItem("access_token");
  }

  private buildHeaders(
    headers?: HeadersInit,
    auth = true,
    hasBody = false
  ): Headers {
    const requestHeaders = new Headers(headers);

    if (hasBody && !requestHeaders.has("Content-Type")) {
      requestHeaders.set(
        "Content-Type",
        "application/json"
      );
    }

    if (auth) {
      const token = this.getToken();

      if (token) {
        requestHeaders.set(
          "Authorization",
          `Bearer ${token}`
        );
      }
    }

    return requestHeaders;
  }

  private async parseError(
    response: Response
  ): Promise<unknown> {
    const contentType =
      response.headers.get("content-type") || "";

    try {
      if (contentType.includes("application/json")) {
        return await response.json();
      }

      return await response.text();
    } catch {
      return null;
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestOptions = {}
  ): Promise<T> {
    const {
      auth = true,
      headers,
      body,
      ...rest
    } = options;

    const hasBody =
      body !== undefined &&
      body !== null;

    const requestHeaders =
      this.buildHeaders(
        headers,
        auth,
        hasBody
      );

    const response = await fetch(
      `${this.baseUrl}${endpoint}`,
      {
        ...rest,
        headers: requestHeaders,
        body,
      }
    );

    if (!response.ok) {
      const errorData =
        await this.parseError(response);

      throw new ApiError(
        response.status,
        errorData
      );
    }

    if (response.status === 204) {
      return {} as T;
    }

    const contentType =
      response.headers.get("content-type") || "";

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

    const token = this.getToken();

    const headers = new Headers(
      options.headers
    );

    /*
     * Do NOT set Content-Type manually for FormData.
     * The browser must generate the multipart boundary.
     */
    headers.delete("Content-Type");

    if (token) {
      headers.set(
        "Authorization",
        `Bearer ${token}`
      );
    }

    const response = await fetch(
      `${this.baseUrl}${url}`,
      {
        ...options,
        method: "POST",
        headers,
        body: form,
      }
    );

    if (!response.ok) {
      const errorData =
        await this.parseError(response);

      throw new ApiError(
        response.status,
        errorData
      );
    }

    if (response.status === 204) {
      return {} as T;
    }

    const contentType =
      response.headers.get("content-type") || "";

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

    const requestHeaders =
      this.buildHeaders(
        headers,
        auth,
        false
      );

    const response = await fetch(
      `${this.baseUrl}${url}`,
      {
        ...rest,
        method: "GET",
        headers: requestHeaders,
      }
    );

    if (!response.ok) {
      const errorData =
        await this.parseError(response);

      throw new ApiError(
        response.status,
        errorData
      );
    }

    return response.blob();
  }

  stream(url: string): EventSource {
    return new EventSource(
      `${this.baseUrl}${url}`
    );
  }
}

export const api =
  new ApiClient(API_BASE_URL);

export { ApiError };