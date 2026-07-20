#!/usr/bin/env python3
"""Generate markdown report from stress_test_report.json."""
import json, os

d = json.load(open("reports/stress_test_report.json", encoding="utf-8"))
lines = []
lines.append("# LakeMind 压力测试报告")
lines.append("")
lines.append(f"> **生成时间**: {d['generated_at']}")
lines.append(f"> **环境**: {d['environment']['server']} / {d['environment']['model_serving']}")
lines.append(f"> **租户**: {d['environment']['tenant']}")
lines.append("")
s = d['summary']
lines.append(f"## 汇总: {s['total']} 项 | PASS {s['passed']} | FAIL {s['failed']} | ERROR {s['errors']}")
lines.append("")
lines.append("| TC | 名称 | 结果 | 关键指标 |")
lines.append("|----|------|------|----------|")
for r in d['results']:
    tc = r['test_case']
    name = r['test_name']
    v = r['verdict']
    icon = 'PASS' if v == 'PASS' else 'FAIL' if v == 'FAIL' else 'ERROR'
    m = r['results']
    parts = []
    if tc == 'TC-1':
        parts.append(f"吞吐 {m.get('throughput_mbs','?')} MB/s")
        parts.append(f"成功率 {m.get('success_rate','?')}%")
    elif tc == 'TC-2':
        parts.append(f"PUT p99 {m.get('put_s',{}).get('p99','?')}s")
        parts.append(f"GET p99 {m.get('get_s',{}).get('p99','?')}s")
    elif tc == 'TC-3':
        b = m.get('batch_100', {})
        parts.append(f"batch_100 {b.get('latency_s','?')}s")
        parts.append(f"吞吐 {b.get('throughput','?')} texts/s")
        parts.append(f"加速比 {m.get('batch_speedup','?')}x")
    elif tc == 'TC-4':
        a1 = m.get('add_1k', {})
        a5 = m.get('add_5k', {})
        parts.append(f"1K: {a1.get('throughput','?')} vec/s")
        parts.append(f"5K: {a5.get('throughput','?')} vec/s")
    elif tc == 'TC-5':
        ss = m.get('single_search_s', {})
        q50 = m.get('qps_50', {})
        parts.append(f"p50 {ss.get('p50','?')}s p99 {ss.get('p99','?')}s")
        parts.append(f"QPS_50 {q50.get('qps','?')}")
    elif tc == 'TC-8':
        a = m.get('add_s', {})
        sr = m.get('search_s', {})
        parts.append(f"add p99 {a.get('p99','?')}s")
        parts.append(f"search p99 {sr.get('p99','?')}s")
        parts.append(f"QPS {m.get('concurrent_qps_50','?')}")
    elif tc == 'TC-10':
        for k, v2 in m.items():
            if k.startswith('conc_') and isinstance(v2, dict):
                parts.append(f"{k}: {v2.get('qps','?')}qps {v2.get('err_rate','?')}%err")
    elif tc == 'TC-11':
        parts.append(f"嵌入冷启动 {m.get('embed_cold_s','?')}s")
        parts.append(f"health {m.get('health_latency_s','?')}s")
    elif tc == 'TC-12':
        parts.append(f"REST {m.get('rest_s',{}).get('mean','?')}s")
        parts.append(f"MCP {m.get('mcp_s',{}).get('mean','?')}s")
        parts.append(f"开销 {m.get('overhead_s','?')}s")
    lines.append(f"| {tc} | {name} | {icon} | {' | '.join(parts)} |")

lines.append("")
lines.append("## 详细结果")
lines.append("")
for r in d['results']:
    lines.append(f"### {r['test_case']}: {r['test_name']} — {r['verdict']}")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(r['results'], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    if r.get('failed_metrics'):
        lines.append(f"**未通过指标**: {r['failed_metrics']}")
        lines.append("")

with open("reports/stress_test_report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"报告已生成: reports/stress_test_report.md ({len(lines)} 行)")
