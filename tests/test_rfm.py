import unittest

import duckdb
import pandas as pd

from ecommerce_analytics.rfm import RFM_SCORE_COLUMNS


class RfmScoringTest(unittest.TestCase):
    def test_equal_metric_values_receive_equal_scores(self):
        metrics = pd.DataFrame(
            [
                (1, 10, 1, 100.0),
                (2, 10, 1, 100.0),
                (3, 20, 2, 200.0),
                (4, 40, 4, 400.0),
                (5, 80, 8, 800.0),
                (6, 160, 16, 1600.0),
            ],
            columns=["customer_id", "recency_days", "frequency", "monetary"],
        )

        with duckdb.connect() as connection:
            connection.register("customer_metrics", metrics)
            scored = connection.execute(
                f"""
                SELECT customer_id, {RFM_SCORE_COLUMNS}
                FROM customer_metrics
                ORDER BY customer_id
                """
            ).df()

        first = scored.loc[scored["customer_id"] == 1].iloc[0]
        second = scored.loc[scored["customer_id"] == 2].iloc[0]
        self.assertEqual(first["r_score"], second["r_score"])
        self.assertEqual(first["f_score"], second["f_score"])
        self.assertEqual(first["m_score"], second["m_score"])

    def test_scores_stay_within_one_to_five_and_recency_is_inverted(self):
        metrics = pd.DataFrame(
            [
                (1, 1, 1, 10.0),
                (2, 10, 2, 20.0),
                (3, 20, 3, 30.0),
                (4, 30, 4, 40.0),
                (5, 40, 5, 50.0),
                (6, 50, 6, 60.0),
            ],
            columns=["customer_id", "recency_days", "frequency", "monetary"],
        )

        with duckdb.connect() as connection:
            connection.register("customer_metrics", metrics)
            scored = connection.execute(
                f"SELECT customer_id, {RFM_SCORE_COLUMNS} FROM customer_metrics"
            ).df()

        for column in ("r_score", "f_score", "m_score"):
            self.assertGreaterEqual(scored[column].min(), 1)
            self.assertLessEqual(scored[column].max(), 5)
        newest = scored.loc[scored["customer_id"] == 1, "r_score"].item()
        oldest = scored.loc[scored["customer_id"] == 6, "r_score"].item()
        self.assertGreater(newest, oldest)


if __name__ == "__main__":
    unittest.main()
