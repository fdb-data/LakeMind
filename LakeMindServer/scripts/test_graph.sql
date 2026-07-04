-- 插入节点
INSERT INTO graph_nodes (graph_name, node_id, label, properties, tenant_id) VALUES
  ('ontology_1', 'concept_risk', 'Concept', '{"name":"risk","desc":"risk control"}', 'platform'),
  ('ontology_1', 'concept_rule', 'Concept', '{"name":"rule","desc":"risk rule"}', 'platform'),
  ('ontology_1', 'concept_system', 'Concept', '{"name":"system","desc":"risk system"}', 'platform');

-- 插入边
INSERT INTO graph_edges (graph_name, edge_id, src_id, dst_id, rel_type, properties, tenant_id) VALUES
  ('ontology_1', 'e1', 'concept_rule', 'concept_risk', 'belongs_to', '{}', 'platform'),
  ('ontology_1', 'e2', 'concept_risk', 'concept_system', 'part_of', '{}', 'platform');

-- 查询节点
SELECT n.node_id, n.label, n.properties->>'name' as name
FROM graph_nodes n
WHERE n.graph_name = 'ontology_1' AND n.tenant_id = 'platform';

-- 查询关系
SELECT e.rel_type, e.dst_id, n.properties->>'name' as dst_name
FROM graph_edges e
JOIN graph_nodes n ON e.graph_name = n.graph_name AND e.dst_id = n.node_id
WHERE e.graph_name = 'ontology_1' AND e.src_id = 'concept_risk';
