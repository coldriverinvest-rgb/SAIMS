import unittest
from backend.services.komis_service import parse_chart

class KomisParserTest(unittest.TestCase):
    def fixture(self):
        return {'data': {'mnrlInfo': {'prcUnitCdNm':'USD','weigUnitCd':'kg'}, 'prcCrtr':'test grade', 'xaxis':['2026.09.01','2026.09.02'], 'series':[{'spid':'MNRL0001','data':['20.5','21']} ]}}

    def test_price_and_units(self):
        grade, unit, rows = parse_chart(self.fixture(), 'MNRL0001')
        self.assertEqual(unit, 'USD/kg')
        self.assertEqual(rows, [('2026-09-01',20.5),('2026-09-02',21)])

    def test_missing_not_zero(self):
        data = self.fixture()
        data['data']['series'][0]['data'][0] = None
        self.assertEqual(len(parse_chart(data,'MNRL0001')[2]),1)

    def test_reject_changed_structure(self):
        data = self.fixture()
        data['data']['xaxis'] = []
        with self.assertRaises(ValueError): parse_chart(data,'MNRL0001')

    def test_reject_missing_unit(self):
        data = self.fixture()
        del data['data']['mnrlInfo']['weigUnitCd']
        with self.assertRaises(ValueError): parse_chart(data,'MNRL0001')

    def test_reject_nonfinite(self):
        data = self.fixture()
        data['data']['series'][0]['data'][0] = 'NaN'
        with self.assertRaises(ValueError): parse_chart(data,'MNRL0001')

if __name__ == '__main__': unittest.main()
