import { createContext, useContext, useState, ReactNode } from "react";

interface ClaudeContextType {
  isConfigured: boolean;
  apiKey: string;
  setApiKey: (key: string) => void;
  generateContent: (prompt: string) => Promise<string>;
}

const ClaudeContext = createContext<ClaudeContextType | undefined>(undefined);

export function ClaudeProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState<string>(() => {
    return localStorage.getItem("claude_api_key") || "";
  });

  const setApiKey = (key: string) => {
    setApiKeyState(key);
    localStorage.setItem("claude_api_key", key);
  };

  const generateContent = async (prompt: string): Promise<string> => {
    if (!apiKey) {
      throw new Error("Claude API key is not configured.");
    }

    try {
      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey,
          "anthropic-version": "2023-06-01",
          "anthropic-dangerous-direct-browser-access": "true",
        },
        body: JSON.stringify({
          model: "claude-3-5-sonnet-20241022",
          max_tokens: 1024,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData?.error?.message || "Failed to fetch from Claude API");
      }

      const data = await response.json();
      // Extract text from Anthropic's response format
      return data.content.map((block: any) => block.text).join("\n");
    } catch (error: any) {
      console.error("Claude API Error:", error);
      throw new Error(error.message || "Failed to generate content.");
    }
  };

  return (
    <ClaudeContext.Provider value={{ isConfigured: !!apiKey, apiKey, setApiKey, generateContent }}>
      {children}
    </ClaudeContext.Provider>
  );
}

export function useClaude() {
  const context = useContext(ClaudeContext);
  if (context === undefined) {
    throw new Error("useClaude must be used within a ClaudeProvider");
  }
  return context;
}