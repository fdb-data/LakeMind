"""零售业务 Agent — 通过 LakeMind AssetMCP 管理认知资产。

演示一个零售 Agent 如何：
1. 摄入商品知识（OKF 格式）
2. 语义检索知识
3. 记录用户偏好到记忆（mem0 风格，LLM 自动抽取事实）
4. 检索历史记忆辅助决策
5. 注册并检索技能
"""
from __future__ import annotations

from lakemind_client import LakeMindClient


def main():
    lake = LakeMindClient()

    # ── 1. 摄入商品知识 ──
    print("=== 1. 摄入商品知识 ===")
    result = lake.ingest_knowledge("retail_products", [
        {
            "frontmatter": {
                "type": "product",
                "title": "智能保温杯",
                "description": "500ml 不锈钢真空保温杯，24h 保温",
                "tags": ["家居", "保温", "不锈钢"],
            },
            "body": "# 智能保温杯\n\n## 规格\n- 容量: 500ml\n- 材质: 316 不锈钢\n- 保温: 24h 热饮 / 12h 冷饮\n\n## 卖点\n温度显示，蓝牙提醒饮水",
        },
        {
            "frontmatter": {
                "type": "product",
                "title": "便携咖啡机",
                "description": "USB 充电便携意式咖啡机，户外露营必备",
                "tags": ["户外", "咖啡", "便携"],
            },
            "body": "# 便携咖啡机\n\n## 规格\n- 压力: 15bar\n- 充电: USB-C\n- 重量: 480g\n\n## 卖点\n一键萃取，支持胶囊和咖啡粉",
        },
    ])
    print(f"摄入结果: {result}")

    # ── 2. 语义检索知识 ──
    print("\n=== 2. 语义检索知识 ===")
    hits = lake.search_knowledge("retail_products", "户外喝热饮需要什么装备", top_k=3)
    for h in hits:
        title = h.get("frontmatter", {}).get("title", h.get("title", "?"))
        score = h.get("_distance", h.get("score", "?"))
        print(f"  - {title} (distance={score})")

    # ── 3. 记录用户偏好到记忆 ──
    print("\n=== 3. 记录用户偏好（mem0 自动抽取事实）===")
    result = lake.add_memory(
        messages=[
            {"role": "user", "content": "我喜欢户外露营，经常需要便携装备"},
            {"role": "assistant", "content": "推荐了便携咖啡机和智能保温杯"},
        ],
        metadata={"source": "chat", "session": "retail-001"},
    )
    print(f"记忆结果: {result}")

    # ── 4. 检索历史记忆辅助决策 ──
    print("\n=== 4. 检索记忆辅助决策 ===")
    memories = lake.search_memory("用户喜欢什么", top_k=5)
    for m in memories:
        content = m.get("memory", m.get("content", str(m)))[:80]
        print(f"  - {content}")

    # ── 5. 注册并检索技能 ──
    print("\n=== 5. 注册技能 ===")
    result = lake.register_skill(
        name="recommend_product",
        description="根据用户偏好和商品知识库推荐商品，输入用户query返回top-k商品列表",
        code=(
            "def recommend(query, kb_name='retail_products', top_k=3):\n"
            "    from lakemind_client import LakeMindClient\n"
            "    lake = LakeMindClient()\n"
            "    return lake.search_knowledge(kb_name, query, top_k)\n"
        ),
    )
    print(f"注册结果: {result}")

    print("\n=== 6. 检索技能 ===")
    skills = lake.search_skill("推荐商品", top_k=3)
    for s in skills:
        name = s.get("name", s.get("title", "?"))
        print(f"  - {name}")

    # ── 资源浏览 ──
    print("\n=== 7. 资源浏览 ===")
    kbs = lake.list_knowledge()
    print(f"知识库列表: {kbs}")
    mem = lake.memory_overview()
    print(f"记忆概况: {mem}")

    lake.close()
    print("\n=== 完成 ===")


if __name__ == "__main__":
    main()
