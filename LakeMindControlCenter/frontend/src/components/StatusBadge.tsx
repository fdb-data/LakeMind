import { Tag, Tooltip } from 'antd';

const STATUS_COLORS: Record<string, string> = {
  success: 'success',
  running: 'processing',
  healthy: 'success',
  active: 'success',
  succeeded: 'success',
  warning: 'warning',
  degraded: 'warning',
  pending: 'default',
  approval_required: 'warning',
  drifted: 'warning',
  failed: 'error',
  down: 'error',
  unhealthy: 'error',
  error: 'error',
  rejected: 'error',
  revoked: 'error',
  archived: 'default',
  suspended: 'warning',
  maintenance: 'warning',
  unknown: 'default',
};

const STATUS_LABELS: Record<string, string> = {
  success: 'Success',
  running: 'Running',
  healthy: 'Healthy',
  active: 'Active',
  succeeded: 'Succeeded',
  warning: 'Warning',
  degraded: 'Degraded',
  pending: 'Pending',
  approval_required: 'Approval Required',
  drifted: 'Drifted',
  failed: 'Failed',
  down: 'Down',
  unhealthy: 'Unhealthy',
  error: 'Error',
  rejected: 'Rejected',
  revoked: 'Revoked',
  archived: 'Archived',
  suspended: 'Suspended',
  maintenance: 'Maintenance',
  unknown: 'Unknown',
};

export default function StatusBadge({ status, size }: { status: string; size?: 'small' | 'default' }) {
  const normalized = status.toLowerCase();
  const color = STATUS_COLORS[normalized] || 'default';
  const label = STATUS_LABELS[normalized] || status;
  return (
    <Tag color={color} style={{ textTransform: 'uppercase', fontSize: size === 'small' ? 10 : 11, fontWeight: 600 }}>
      {label}
    </Tag>
  );
}
