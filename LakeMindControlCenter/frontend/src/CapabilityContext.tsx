import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { api } from './api/client';

interface TenantInfo {
  tenant_id: string;
  name: string;
  role: string;
}

interface MeInfo {
  principal_id: string;
  principal_type: string;
  tenant_id: string;
  roles: string[];
  capabilities: string[];
  effective_permissions: Record<string, boolean>;
  security_version: number;
  active_tenant_id: string;
  available_tenants: TenantInfo[];
  username?: string;
}

interface CapabilityContextValue {
  me: MeInfo | null;
  loading: boolean;
  hasCapability: (cap: string) => boolean;
  refresh: () => Promise<void>;
  switchTenant: (tenantId: string) => Promise<void>;
}

const CapabilityContext = createContext<CapabilityContextValue>({
  me: null,
  loading: true,
  hasCapability: () => false,
  refresh: async () => {},
  switchTenant: async () => {},
});

export function CapabilityProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<MeInfo | null>(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    try {
      const resp = await api.get('/auth/me');
      setMe(resp.data);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }

  async function switchTenant(tenantId: string) {
    await api.post('/auth/switch-tenant', { tenant_id: tenantId });
    await refresh();
  }

  useEffect(() => {
    refresh();
  }, []);

  function hasCapability(cap: string): boolean {
    if (!me) return false;
    return me.capabilities.includes('*') || me.capabilities.includes(cap) || me.capabilities.includes('platform:admin');
  }

  return (
    <CapabilityContext.Provider value={{ me, loading, hasCapability, refresh, switchTenant }}>
      {children}
    </CapabilityContext.Provider>
  );
}

export function useCapabilities() {
  return useContext(CapabilityContext);
}
