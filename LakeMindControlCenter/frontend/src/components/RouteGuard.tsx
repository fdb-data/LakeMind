import { ReactNode } from 'react';
import { Result, Spin } from 'antd';
import { useCapabilities } from '../CapabilityContext';

export default function RouteGuard({ capability, children }: { capability: string; children: ReactNode }) {
  const { hasCapability, loading } = useCapabilities();

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: 48 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!hasCapability(capability)) {
    return (
      <Result
        status="403"
        title="No Permission"
        subTitle={`You do not have the required capability: ${capability}`}
      />
    );
  }

  return <>{children}</>;
}
