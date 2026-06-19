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
            workbook.save(workbook_path)
            workbook.close()

            output_path = root / "retail.parquet"
            summary = build_retail_dataset(workbook_path, output_path)
            overview = retail_quality_summary(output_path)

            self.assertEqual(summary["source_rows"], 3)
            self.assertEqual(summary["quarantined_rows"], 0)
            self.assertEqual(overview["raw_rows"], 3)
            self.assertEqual(overview["valid_sale_rows"], 1)
            self.assertEqual(overview["cancelled_rows"], 1)
            self.assertEqual(overview["missing_customer_rows"], 1)
            self.assertEqual(overview["non_positive_price_rows"], 1)
            self.assertAlmostEqual(overview["valid_revenue"], 15.30)


if __name__ == "__main__":
    unittest.main()

