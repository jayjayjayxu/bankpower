import importlib.util
import unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('model',Path(__file__).parents[1]/'tools/build_synergy_simulation.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class EnergyBalanceTests(unittest.TestCase):
    def test_conservation_and_debt(self):
        anchors=dict(tariff_valley=.29,tariff_flat=.71,tariff_peak=1.05,tariff_critical=1.30)
        for kind in ['CONSERVATIVE','BASE','OPTIMISTIC']:
            p=m.inputs(anchors,kind); rows,annual=m.simulate(p)
            self.assertEqual(len(rows),8760)
            self.assertEqual(len(set(r[0] for r in rows)),8760)
            expected=p['racks']*p['occupancy']*p['it_kw']*8760*p['pue']
            self.assertAlmostEqual(sum(r[3] for r in rows),expected,places=4)
            charge=sum(r[5] for r in rows); discharge=sum(r[6] for r in rows)
            self.assertAlmostEqual(discharge,charge*p['charge_efficiency']*p['discharge_efficiency'],places=5)
            self.assertGreater(sum(r[8] for r in rows),sum(r[3] for r in rows))
            self.assertTrue(all(r[6]<=r[3] and r[8]<=p['grid_limit_kw'] for r in rows))
            self.assertTrue(all(r[1]*r[2] >= 0 for r in rows))
            self.assertLess(annual[-1][15],annual[0][15])
            for r in annual:self.assertAlmostEqual(r[16],r[14]/r[15])
            # End SOC is not a free source of energy.
            self.assertAlmostEqual(rows[-1][7],p['storage_capacity_kwh']*p['soc_min_ratio'])

if __name__=='__main__':unittest.main()
