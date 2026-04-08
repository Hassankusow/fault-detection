-- mtbf_mttr.sql
-- Computes Mean Time Between Failures (MTBF) and
-- Mean Time To Recover (MTTR) per equipment unit.
--
-- MTBF = total operational hours / number of fault events
-- MTTR = avg hours between a fault and the next OK status

WITH fault_events AS (
    SELECT
        equipment_id,
        equipment_type,
        timestamp                                   AS fault_ts,
        fault_code,
        downstream_system,
        ROW_NUMBER() OVER (
            PARTITION BY equipment_id ORDER BY timestamp
        )                                           AS fault_seq
    FROM parsed_telemetry
    WHERE status = 'FAULT'
),

recoveries AS (
    SELECT
        t.equipment_id,
        t.timestamp                                 AS recovery_ts,
        MIN(f.fault_ts)                             AS prior_fault_ts
    FROM parsed_telemetry t
    JOIN fault_events f
        ON t.equipment_id = f.equipment_id
       AND f.fault_ts < t.timestamp
    WHERE t.status = 'OK'
    GROUP BY t.equipment_id, t.timestamp
),

mttr_calc AS (
    SELECT
        equipment_id,
        AVG(
            (JULIANDAY(recovery_ts) - JULIANDAY(prior_fault_ts)) * 24
        )                                           AS mttr_hours
    FROM recoveries
    GROUP BY equipment_id
),

total_runtime AS (
    SELECT
        equipment_id,
        MAX(runtime_hours) - MIN(runtime_hours)     AS operational_hours
    FROM parsed_telemetry
    GROUP BY equipment_id
),

fault_counts AS (
    SELECT equipment_id, COUNT(*) AS fault_count
    FROM fault_events
    GROUP BY equipment_id
),

downstream_impact AS (
    SELECT
        equipment_id,
        COUNT(DISTINCT downstream_system)           AS impacted_systems,
        COUNT(*)                                    AS total_fault_events
    FROM fault_events
    WHERE downstream_system != 'NONE'
    GROUP BY equipment_id
)

SELECT
    fc.equipment_id,
    fe.equipment_type,
    fc.fault_count,
    ROUND(tr.operational_hours, 1)                  AS operational_hours,
    ROUND(tr.operational_hours / NULLIF(fc.fault_count, 0), 2)
                                                    AS mtbf_hours,
    ROUND(mt.mttr_hours, 2)                         AS mttr_hours,
    COALESCE(di.impacted_systems, 0)                AS downstream_systems_impacted,
    COALESCE(di.total_fault_events, 0)              AS downstream_fault_events
FROM fault_counts fc
JOIN fault_events fe  ON fc.equipment_id = fe.equipment_id AND fe.fault_seq = 1
JOIN total_runtime tr ON fc.equipment_id = tr.equipment_id
LEFT JOIN mttr_calc mt ON fc.equipment_id = mt.equipment_id
LEFT JOIN downstream_impact di ON fc.equipment_id = di.equipment_id
ORDER BY mtbf_hours ASC;
