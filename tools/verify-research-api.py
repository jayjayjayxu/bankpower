#!/usr/bin/env python3
"""Read-only release smoke checks; accepts local or deployed API bases."""
import argparse,json,urllib.request
p=argparse.ArgumentParser();p.add_argument('--power',default='http://127.0.0.1:8081/api');p.add_argument('--compute',default='http://127.0.0.1:8082/api');a=p.parse_args()
def get(base,path):
    with urllib.request.urlopen(base.rstrip('/')+'/'+path,timeout=30) as f:return json.load(f)
home=get(a.power,'enterprises/home-summary');work=get(a.power,'bank-workbench')
assert len(work['powerItems'])==work['summary']['powerCandidateCount']
assert len({r['companyId'] for r in work['powerItems']})==len(work['powerItems'])
assert home['activeRun']['runId']==work['activeRun']['runId']
for company in home['companies']:
    detail=get(a.power,'enterprises/'+company['companyId'])
    assert detail['snapshot']['runId']==home['activeRun']['runId']
products=get(a.compute,'compute/products?size=100')
assert products['items']
get(a.compute,'compute/products/'+str(products['items'][0]['listingId']))
for path in ['compute/summary','compute/facilities?size=100','compute/facilities/SZCF016','compute/policy/overview','compute/opportunities','compute/power-synergy/SZCF016']:
    get(a.compute,path)
sim=get(a.compute,'compute/simulation/SZCF016')
assert len(sim['scenarios'])==3 and len(sim['annual'])==30 and len(sim['monthly'])==36
assert len(sim['assumptions'])==93 and all(r['actual_value'] is None for r in sim['assumptions'])
for s in sim['scenarios']:
    assert s['data_type']=='SIMULATED'
    months=[r for r in sim['monthly'] if r['scenario_code']==s['scenario_code']]
    assert sum(r['hour_count'] for r in months)==8760
    first=next(r for r in sim['annual'] if r['scenario_code']==s['scenario_code'] and r['year_index']==1)
    assert abs(sum(float(r['facility_energy_kwh']) for r in months)-float(first['annual_energy_kwh']))<.1
    print(s['scenario_name'], 'hours=8760', 'CFADS_proxy='+str(first['cfads_proxy_yuan']), 'DSCR_proxy='+str(first['dscr_proxy']))
print('PASS: full customer queue, consistent snapshots, directories, policies, existing synergy, new simulations')
