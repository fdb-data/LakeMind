import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Table, Tag, Button, Space, Input, Select } from "antd";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";

export default function Meetings() {
  const nav = useNavigate();
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [search, setSearch] = useState("");

  useEffect(() => { load(); }, [statusFilter, search]);

  async function load() {
    setLoading(true);
    const params: any = {};
    if (statusFilter) params.status = statusFilter;
    if (search) params.q = search;
    const r = await api.get("/tasks", { params });
    setTasks(r.data.items || []);
    setLoading(false);
  }

  const statusColor: Record<string, string> = {
    DRAFT: "default", READY: "blue", RECORDING: "processing",
    FINALIZING: "orange", REVIEW_REQUIRED: "gold",
    COMPLETED: "green", FAILED: "red", DELETED: "default",
  };

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" onClick={() => nav("/app/meetings/new")}>+ 新建会议</Button>
        <Select
          placeholder="状态筛选"
          allowClear
          style={{ width: 150 }}
          onChange={(v) => setStatusFilter(v || "")}
          options={[
            { value: "RECORDING", label: "录音中" },
            { value: "FINALIZING", label: "处理中" },
            { value: "REVIEW_REQUIRED", label: "待审核" },
            { value: "COMPLETED", label: "已完成" },
            { value: "FAILED", label: "失败" },
          ]}
        />
        <Input.Search placeholder="搜索会议" onSearch={setSearch} style={{ width: 200 }} />
      </Space>

      <Table
        loading={loading}
        dataSource={tasks}
        rowKey="task_id"
        onRow={(r) => ({ onClick: () => nav(`/app/meetings/${r.task_id}`), style: { cursor: "pointer" } })}
        columns={[
          { title: "标题", dataIndex: "title" },
          { title: "状态", dataIndex: "status", render: (s: string) => <Tag color={statusColor[s] || "default"}>{s}</Tag> },
          { title: "来源", dataIndex: "source_type", render: (s: string) => s === "LIVE" ? "实时录音" : "上传" },
          { title: "创建时间", dataIndex: "created_at", render: (t: string) => t ? new Date(t).toLocaleString() : "-" },
          { title: "时长", dataIndex: "duration_ms", render: (d: number) => d ? `${Math.floor(d/1000)}s` : "-" },
        ]}
      />
    </div>
  );
}
