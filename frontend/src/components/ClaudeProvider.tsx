import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  ReactNode,
} from "react";

import { api, ApiError } from "@/lib/api";

export type ClaudeStatus =
  | "not_configured"
  | "valid"
  | "billing_required"
  | "invalid_api_key"
  | "rate_limited"
  | "forbidden"
  | "provider_unavailable"
  | "provider_request_error"
  | "provider_error"
  | "secret_error";

interface ClaudeStatusResponse {
  provider: string;
  configured: boolean;
  enabled: boolean;
  status: ClaudeStatus | string;
  masked_key: string | null;
  last_checked_at: string | null;
}

interface ClaudeContextType {
  /**
   * This is NEVER the real API key.
   * It is either empty or the backend-provided masked key.
   */
  apiKey: string;

  /**
   * True when an Anthropic credential exists in the backend.
   *
   * billing_required MUST therefore still be true here.
   */
  isConfigured: boolean;

  /**
   * True only when Anthropic has successfully processed
   * a live test request.
   */
  isReady: boolean;

  status: ClaudeStatus | string;

  loading: boolean;

  setApiKey: (key: string) => Promise<void>;

  testConnection: () => Promise<void>;

  refreshStatus: () => Promise<void>;

  generateContent: (prompt: string) => Promise<string>;
}

const ClaudeContext =
  createContext<ClaudeContextType | undefined>(
    undefined
  );

function hasAccessToken(): boolean {
  const token =
    localStorage.getItem("access_token");

  return Boolean(
    token &&
      token.trim() &&
      token !== "null" &&
      token !== "undefined"
  );
}

function extractApiError(
  error: unknown,
  fallback: string
): {
  status: number | null;
  code: string | null;
  message: string;
} {
  if (error instanceof ApiError) {
    const payload = error.data as any;

    const detail = payload?.detail;

    if (
      detail &&
      typeof detail === "object"
    ) {
      return {
        status: error.status,
        code:
          typeof detail.code === "string"
            ? detail.code
            : null,
        message:
          typeof detail.message === "string"
            ? detail.message
            : fallback,
      };
    }

    return {
      status: error.status,
      code: null,
      message:
        typeof detail === "string"
          ? detail
          : fallback,
    };
  }

  if (error instanceof Error) {
    return {
      status: null,
      code: null,
      message:
        error.message || fallback,
    };
  }

  return {
    status: null,
    code: null,
    message: fallback,
  };
}

function hasStoredCredential(
  status: string
): boolean {
  return (
    status !== "not_configured" &&
    status !== "secret_error" &&
    Boolean(status)
  );
}

export function ClaudeProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [apiKey, setApiKeyState] =
    useState("");

  const [status, setStatus] =
    useState<ClaudeStatus | string>(
      "not_configured"
    );

  const [loading, setLoading] =
    useState(true);

  const requestStartedRef =
    useRef(false);

  const isConfigured =
    hasStoredCredential(status);

  const isReady =
    status === "valid";

  const loadStatus =
    async (): Promise<void> => {
      if (!hasAccessToken()) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        const data =
          await api.get<ClaudeStatusResponse>(
            "/api/settings/ai/anthropic"
          );

        setApiKeyState(
          data.masked_key || ""
        );

        setStatus(
          data.status || "not_configured"
        );
      } catch (error) {
        const parsed =
          extractApiError(
            error,
            "Unable to load Anthropic status."
          );

        /*
         * A 401 can happen if the provider mounts
         * before authentication is ready.
         */
        if (parsed.status === 401) {
          setLoading(false);
          return;
        }

        console.error(
          "Failed to load Anthropic status:",
          parsed.message
        );

        setApiKeyState("");

        setStatus(
          "provider_error"
        );
      } finally {
        setLoading(false);
      }
    };

  useEffect(() => {
    if (requestStartedRef.current) {
      return;
    }

    requestStartedRef.current = true;

    let cancelled = false;
    let timer: number | undefined;

    const waitForLogin =
      () => {
        if (cancelled) {
          return;
        }

        if (hasAccessToken()) {
          void loadStatus();
          return;
        }

        timer =
          window.setTimeout(
            waitForLogin,
            500
          );
      };

    waitForLogin();

    return () => {
      cancelled = true;

      if (timer !== undefined) {
        window.clearTimeout(timer);
      }
    };
  }, []);

  const setApiKey =
    async (
      key: string
    ): Promise<void> => {
      const trimmed =
        key.trim();

      if (!trimmed) {
        throw new Error(
          "Please enter your Anthropic API key."
        );
      }

      if (
        !trimmed.startsWith(
          "sk-ant-"
        )
      ) {
        throw new Error(
          "Please enter a valid Anthropic API key starting with sk-ant-."
        );
      }

      if (!hasAccessToken()) {
        throw new Error(
          "Your login session is not ready. Please sign in again."
        );
      }

      try {
        const data =
          await api.put<ClaudeStatusResponse>(
            "/api/settings/ai/anthropic",
            {
              api_key: trimmed,
            }
          );

        setApiKeyState(
          data.masked_key || ""
        );

        setStatus(
          data.status || "not_configured"
        );
      } catch (error) {
        const parsed =
          extractApiError(
            error,
            "Unable to save Anthropic API key."
          );

        /*
         * IMPORTANT:
         *
         * The backend stores the valid credential even when
         * Anthropic billing is required. Therefore a 402 means:
         *
         * credential exists
         * BUT AI is not currently usable.
         */
        if (
          parsed.status === 402 ||
          parsed.code ===
            "billing_required"
        ) {
          setStatus(
            "billing_required"
          );

          /*
           * Refresh the backend state so the masked key
           * and timestamp are reflected immediately.
           */
          try {
            await loadStatus();
          } catch {
            // Preserve billing_required even if refresh fails.
          }

          throw new Error(
            parsed.message ||
              "Your Anthropic credit balance is too low. Please add credits or upgrade your Anthropic plan."
          );
        }

        if (
          parsed.code ===
          "invalid_api_key"
        ) {
          setStatus(
            "invalid_api_key"
          );

          throw new Error(
            parsed.message ||
              "Anthropic API key is invalid."
          );
        }

        if (
          parsed.code ===
          "rate_limited" ||
          parsed.status === 429
        ) {
          setStatus(
            "rate_limited"
          );

          throw new Error(
            parsed.message ||
              "Anthropic usage quota or rate limit was reached."
          );
        }

        if (
          parsed.code ===
          "forbidden"
        ) {
          setStatus(
            "forbidden"
          );

          throw new Error(
            parsed.message ||
              "Anthropic access is restricted."
          );
        }

        setStatus(
          parsed.code ||
            "provider_error"
        );

        throw new Error(
          parsed.message
        );
      }
    };

  const testConnection =
    async (): Promise<void> => {
      if (!hasAccessToken()) {
        throw new Error(
          "Your login session is not ready. Please sign in again."
        );
      }

      try {
        const data =
          await api.post<ClaudeStatusResponse>(
            "/api/settings/ai/anthropic/test"
          );

        setApiKeyState(
          data.masked_key || ""
        );

        setStatus(
          data.status || "not_configured"
        );
      } catch (error) {
        const parsed =
          extractApiError(
            error,
            "Anthropic connection test failed."
          );

        if (
          parsed.status === 402 ||
          parsed.code ===
            "billing_required"
        ) {
          setStatus(
            "billing_required"
          );

          throw new Error(
            parsed.message ||
              "Your Anthropic credit balance is too low. Please add credits or upgrade your Anthropic plan."
          );
        }

        if (
          parsed.code ===
          "invalid_api_key"
        ) {
          setStatus(
            "invalid_api_key"
          );

          throw new Error(
            parsed.message ||
              "Anthropic API key is invalid."
          );
        }

        if (
          parsed.code ===
          "rate_limited"
        ) {
          setStatus(
            "rate_limited"
          );

          throw new Error(
            parsed.message ||
              "Anthropic usage quota or rate limit was reached."
          );
        }

        setStatus(
          parsed.code ||
            "provider_error"
        );

        throw new Error(
          parsed.message
        );
      }
    };

  const refreshStatus =
    async (): Promise<void> => {
      await loadStatus();
    };

  const generateContent =
    async (
      prompt: string
    ): Promise<string> => {
      if (!isConfigured) {
        throw new Error(
          "Claude AI is not configured. Please add your Anthropic API key in Settings."
        );
      }

      if (!isReady) {
        if (
          status ===
          "billing_required"
        ) {
          throw new Error(
            "Anthropic billing is required. Your API key is valid, but your Anthropic credit balance is too low. Please add credits or upgrade your Anthropic plan."
          );
        }

        if (
          status ===
          "invalid_api_key"
        ) {
          throw new Error(
            "Anthropic API key is invalid. Please update it in Settings."
          );
        }

        if (
          status ===
          "rate_limited"
        ) {
          throw new Error(
            "Anthropic usage quota or rate limit was reached. Please try again later."
          );
        }

        if (
          status ===
          "forbidden"
        ) {
          throw new Error(
            "Anthropic access is restricted for this account."
          );
        }

        throw new Error(
          "Claude AI is not currently ready. Please check Settings."
        );
      }

      const response =
        await api.post<{
          content: string;
        }>(
          "/api/ai/generate",
          {
            prompt,
          }
        );

      return response.content;
    };

  return (
    <ClaudeContext.Provider
      value={{
        apiKey,
        isConfigured,
        isReady,
        status,
        loading,
        setApiKey,
        testConnection,
        refreshStatus,
        generateContent,
      }}
    >
      {children}
    </ClaudeContext.Provider>
  );
}

export function useClaude() {
  const context =
    useContext(
      ClaudeContext
    );

  if (!context) {
    throw new Error(
      "useClaude must be used within a ClaudeProvider"
    );
  }

  return context;
}