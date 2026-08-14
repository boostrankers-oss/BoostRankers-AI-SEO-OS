import React, { createContext, useContext, useState, ReactNode } from 'react';

export interface Agent {
  name: string;
  description: string;
  status: "pending" | "running" | "complete" | "error";
  logs: string[];
  score?: number;
}

const initialAgents: Agent[] = [
  { name: "Technical SEO Agent", description: "Crawlability, indexing, core web vitals", status: "pending", logs: [] },
  { name: "Content SEO Agent", description: "Content quality, keyword density, headings", status: "pending", logs: [] },
  { name: "Local SEO Agent", description: "GMB, citations, local rankings", status: "pending", logs: [] },
  { name: "Schema Agent", description: "Structured data validation", status: "pending", logs: [] },
  { name: "EEAT Agent", description: "Experience, Expertise, Authority, Trust", status: "pending", logs: [] },
  { name: "Internal Linking Agent", description: "Link structure, anchor text, orphan pages", status: "pending", logs: [] },
  { name: "Competitor Agent", description: "Gap analysis, competitor rankings", status: "pending", logs: [] },
  { name: "Backlink Agent", description: "Backlink profile, toxic links, DA", status: "pending", logs: [] },
  { name: "AI Search Agent", description: "LLM visibility, AI snippet optimization", status: "pending", logs: [] },
  { name: "Reporting Agent", description: "Compile findings, generate report", status: "pending", logs: [] },
];

interface AuditContextType {
  running: boolean;
  agents: Agent[];
  progress: number;
  globalLogs: string[];
  setRunning: (running: boolean) => void;
  setAgents: (agents: Agent[] | ((prev: Agent[]) => Agent[])) => void;
  setProgress: (progress: number) => void;
  setGlobalLogs: (logs: string[] | ((prev: string[]) => string[])) => void;
  resetAudit: () => void;
}

const AuditContext = createContext<AuditContextType | undefined>(undefined);

export const AuditProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [running, setRunning] = useState(false);
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [progress, setProgress] = useState(0);
  const [globalLogs, setGlobalLogs] = useState<string[]>([]);

  const resetAudit = () => {
    setRunning(false);
    setAgents(initialAgents);
    setProgress(0);
    setGlobalLogs([]);
  };

  return (
    <AuditContext.Provider
      value={{
        running,
        agents,
        progress,
        globalLogs,
        setRunning,
        setAgents,
        setProgress,
        setGlobalLogs,
        resetAudit,
      }}
    >
      {children}
    </AuditContext.Provider>
  );
};

export const useAudit = () => {
  const context = useContext(AuditContext);
  if (!context) {
    throw new Error('useAudit must be used within an AuditProvider');
  }
  return context;
};