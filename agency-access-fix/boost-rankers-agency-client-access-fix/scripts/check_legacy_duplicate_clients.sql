-- Run this read-only query BEFORE archiving any legacy duplicate client records.
-- It reports all foreign-key references to the two known duplicate IDs.
-- Do NOT delete anything until every returned dependency is reviewed.

SELECT
    c.id,
    c.business_name,
    c.company_id,
    COUNT(*) FILTER (WHERE a.client_id = c.id) AS audit_refs
FROM clients c
LEFT JOIN audits a ON a.client_id = c.id
WHERE c.id IN (
    '8bc22b35-953c-4f68-9283-8e9ffb8ffafc',
    '2405b793-914d-49a1-9a90-688f4c59d2d0'
)
GROUP BY c.id, c.business_name, c.company_id
ORDER BY c.business_name;
