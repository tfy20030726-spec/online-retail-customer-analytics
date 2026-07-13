"""Tie-aware RFM score expressions shared by the dashboard and tests."""

RFM_SCORE_COLUMNS = """
    6 - CAST(
        LEAST(
            5,
            FLOOR(percent_rank() OVER (ORDER BY recency_days) * 5) + 1
        ) AS INTEGER
    ) AS r_score,
    CAST(
        LEAST(
            5,
            FLOOR(percent_rank() OVER (ORDER BY frequency) * 5) + 1
        ) AS INTEGER
    ) AS f_score,
    CAST(
        LEAST(
            5,
            FLOOR(percent_rank() OVER (ORDER BY monetary) * 5) + 1
        ) AS INTEGER
    ) AS m_score
""".strip()
