import { useState, useEffect, createContext, useContext } from "react";
import { api, type Client, type Audit, type Config } from "./api";

interface StoreContextType {
  clients: Client[];
  audits: Audit[];
  config: Config | null;
  loading: boolean;
  refreshClients: () => Promise<void>;
  addClient: (data: Partial<Client>) => Promise<void>;
  deleteClient: (id: number) => Promise<void>;
  refreshAudits: () => Promise<void>;
  addAudit: (data: Partial<Audit>) => Promise<void>;
  refreshConfig: () => Promise<void>;
  saveConfig: (key: string) => Promise<void>;
}

const StoreContext = createContext<StoreContextType | null>(null);

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [clients, setClients] = useState<Client[]>([]);
  const [audits, setAudits] = useState<Audit[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshClients = async () => {
    try {
      const data = await api.getClients();
      setClients(data);
    } catch (e) {
      console.error("Failed to fetch clients", e);
    }
  };

  const addClient = async (data: Partial<Client>) => {
    await api.createClient(data);
    await refreshClients();
  };

  const deleteClient = async (id: number) => {
    await api.deleteClient(id);
    await refreshClients();
  };

  const refreshAudits = async () => {
    try {
      const data = await api.getAudits();
      setAudits(data);
    } catch (e) {
      console.error("Failed to fetch audits", e);
    }
  };

  const addAudit = async (data: Partial<Audit>) => {
    await api.createAudit(data);
    await refreshAudits();
  };

  const refreshConfig = async () => {
    try {
      const data = await api.getConfig();
      setConfig(data);
    } catch (e) {
      console.error("Failed to fetch config", e);
    }
  };

  const saveConfig = async (key: string) => {
    await api.updateConfig(key);
    await refreshConfig();
  };

  useEffect(() => {
    const init = async () => {
      await Promise.all([refreshClients(), refreshAudits(), refreshConfig()]);
      setLoading(false);
    };
    init();
  }, []);

  return (
    <StoreContext.Provider
      value={{
        clients,
        audits,
        config,
        loading,
        refreshClients,
        addClient,
        deleteClient,
        refreshAudits,
        addAudit,
        refreshConfig,
        saveConfig,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used within StoreProvider");
  return ctx;
}