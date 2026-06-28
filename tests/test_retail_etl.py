import csv
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook

from ecommerce_analytics.retail_etl import (
    build_retail_dataset,
    retail_quality_summary,
)


class RetailEtlTest(unittest.TestCase):
    def test_build_retail_dataset_preserves_quality_signals(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            workbook_path = root / "retail.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Year 2010-2011"
            sheet.append(
                [
                    "Invoice",
                    "StockCode",
                    "Description",
                    "Quantity",
                    "InvoiceDate",
                    "Price",
                    "Customer ID",
                    "Country",
                ]
            )
            sheet.append(
                [
                    536365,
                    "85123A",
                    "WHITE HANGING HEART",
                    6,
                    datetime(2010, 12, 1, 8, 26),
                    2.55,
                    17850,
                    "United Kingdom",
                ]
            )
            sheet.append(
                [
                    "C536379",
                    "D",
                    "Discount",
                    -1,
                    datetime(2010, 12, 1, 9, 41),
                    27.5,
                    14527,
                    "United Kingdom",
                ]
            )
            sheet.append(
                [
                    536380,
                    "POST",
                    "Postage",
                    1,
                    datetime(2010, 12, 1, 9, 41),
                    0,
                    None,
                    "France",
                ]
            )
            sheet.append(
                [
                    536381,
                    "TEST",
                    "Malformed quantity",
                    "bad quantity",
                    datetime(2010, 12, 1, 10, 0),
                    4.5,
                    12345,
                    "United Kingdom",
                ]
            )
            sheet.append(
                [
                    536382,
                    "TEST",
                    "Fractional quantity",
                    1.5,
                    datetime(2010, 12, 1, 10, 1),
                    4.5,
                    12345,
                    "United Kingdom",
                ]
            )
            sheet.append(
                [
                    536383,
                    "TEST",
                    "Malformed customer ID",
                    1,
                    datetime(2010, 12, 1, 10, 2),
                    4.5,
                    "not-a-customer",
                    "United Kingdom",
                ]
            )
            sheet.append(
                [
                    536384,
                    "TEST",
                    "Non-finite price",
                    1,
                    datetime(2010, 12, 1, 10, 3),
                    "NaN",
                    12345,
                    "United Kingdom",
                ]
            )
            workbook.save(workbook_path)
            workbook.close()

            output_path = root / "retail.parquet"
            summary = build_retail_dataset(workbook_path, output_path)
            overview = retail_quality_summary(output_path)
            quarantine_path = output_path.with_suffix(".quarantine.csv")
            with quarantine_path.open(newline="", encoding="utf-8") as file:
                quarantined_rows = list(csv.DictReader(file))

            self.assertEqual(summary["source_rows"], 7)
            self.assertEqual(summary["staged_rows"], 3)
            self.assertEqual(summary["quarantined_rows"], 4)
            self.assertEqual(overview["raw_rows"], 3)
            self.assertEqual(overview["valid_sale_rows"], 1)
            self.assertEqual(overview["cancelled_rows"], 1)
            self.assertEqual(overview["missing_customer_rows"], 1)
            self.assertEqual(overview["non_positive_price_rows"], 1)
            self.assertAlmostEqual(overview["valid_revenue"], 15.30)
            self.assertEqual(len(quarantined_rows), 4)
            self.assertEqual(
                quarantined_rows[0]["source_period"],
                "Year 2010-2011",
            )
            self.assertEqual(quarantined_rows[0]["source_row"], "5")
            self.assertIn("bad quantity", quarantined_rows[0]["raw_values"])
            quarantine_errors = {
                row["source_row"]: row["error"] for row in quarantined_rows
            }
            self.assertIn("must be an integer", quarantine_errors["6"])
            self.assertIn("must be numeric", quarantine_errors["7"])
            self.assertIn("must be finite", quarantine_errors["8"])


if __name__ == "__main__":
    unittest.main()
