
import unittest
import pandas as pd
import os
from openpyxl import load_workbook
from src.core.reporting import ExcelReportGenerator

class TestExcelInjection(unittest.TestCase):
    def setUp(self):
        self.filename = "test_injection.xlsx"
        self.malicious_payload = "=HYPERLINK(\"http://malicious.com\", \"Click Me\")"
        self.malicious_payload_2 = "@SUM(1+1)"
        self.malicious_payload_3 = "+1+1"
        self.malicious_payload_4 = "-1-1"

    def tearDown(self):
        if os.path.exists(self.filename):
            os.remove(self.filename)

    def test_formula_injection(self):
        # Create a DataFrame with malicious inputs
        df = pd.DataFrame({
            'title': [self.malicious_payload, 'Normal Title', self.malicious_payload_2, self.malicious_payload_3, self.malicious_payload_4],
            'views': [100, 200, 300, 400, 500],
            'retention_avg_pct': [50.0, 60.0, 70.0, 80.0, 90.0]
        })

        anomalies = {'Viral': df}
        strategy = "Test Strategy"

        generator = ExcelReportGenerator()
        generator.generate_excel(anomalies, strategy, self.filename)

        # Load the workbook and check the values
        wb = load_workbook(self.filename)
        ws = wb['Viral Anomalies']

        # Let's check what's actually in the cell.
        cell_val_1 = ws['A2'].value # =HYPERLINK(...)
        cell_val_3 = ws['A4'].value # @SUM(...)

        print(f"Cell A2 value: {cell_val_1}")

        # We now EXPECT the values to be escaped with a single quote.
        self.assertEqual(cell_val_1, f"'{self.malicious_payload}")
        self.assertEqual(cell_val_3, f"'{self.malicious_payload_2}")

if __name__ == '__main__':
    unittest.main()
