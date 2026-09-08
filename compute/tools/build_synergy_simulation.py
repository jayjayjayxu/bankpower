#!/usr/bin/env python3
"""Deterministic, additive Phase III scenario generator; stdlib only.
Reads existing public/model anchors with mysql; emits SQL for review/import.
Never fills NULL public facts or marks due-diligence items verified.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import subprocess
from pathlib import Path

VERSION = 'BWX_SIM_20260908_V2'
BOUNDARY = ('深圳易信科技股份有限公司·百旺信三期：全部小时值、项目经营与偿债结果为SIMULATED。'
            '公开工程锚点不代表实际利用率、账单、合同或CFADS。模拟假设不改变真实资料缺失和尽调状态。'
            '采用数据库2026年7月分时价格作为2025全年恒定价格压力情景，不是历史结算复原。'
            '保持IT服务负荷不变，仅储能移峰；需求响应收益为0；不计需量节省、碳收益、补贴。')

# value, unit, label, type, reason. A public reference is not a verified current actual.
DEFAULTS = {
 'racks': (1760,'柜','三期机柜容量','PUBLIC_REFERENCE','三期工程披露，source_id=3038；非实际上架柜数'),
 'rack_kw': (4,'kW/柜','额定单柜功率','PUBLIC_REFERENCE','三期工程披露，source_id=3038'),
 'energy_cap': (48473300,'kWh/年','公开年电量边界','PUBLIC_REFERENCE','三期工程披露，source_id=3038；作为边界校验'),
 'capex': (320000000,'元','历史投资参考','PUBLIC_REFERENCE','三期CAPEX 32000万元换算；source_id=3038；不代表当前融资需求'),
 'occupancy': (.6542,'比例','上架率','SIMULATED_PROXY','基准参考1+4栋2025年65.42%；仅代理三期，非三期实际'),
 'it_kw': (3.0146,'kW/已上架柜','单柜平均IT负载','SIMULATED_PROXY','既有BWX_PHASE3_BASE_V1参数；缺少三期实测'),
 'pue': (1.228,'比例','全年平均PUE','SIMULATED_PROXY','以三期披露PUE为基准，实际逐小时PUE未取得'),
 'rack_price': (4170.22,'元/柜·月','机柜服务价格','SIMULATED_PROXY','既有三期基准采用1栋低功率机柜价代理；不代表三期合同'),
 'other_cost_ratio': (.3266,'比例','非电经营成本率','SIMULATED_PROXY','既有三期模型由全园区经营成本推导；不代表三期账簿'),
 'collection_ratio': (.98,'比例','当年回款率','SIMULATED_ASSUMPTION','无三期回款明细，假设98%；未回款部分不计当年可用现金'),
 'reserve_ratio': (.02,'比例','维护资本开支准备率','SIMULATED_ASSUMPTION','缺少项目维保资本开支计划，按收入2%准备'),
 'tax_ratio': (.25,'比例','现金税费代理率','SIMULATED_ASSUMPTION','统一25%模型扣减，非企业实际税率/税务测算；不建折旧抵税'),
 'grid_limit_kw': (10000,'kW','接入功率约束','SIMULATED_ASSUMPTION','暂设10MW技术情景，待接入协议与变压器容量核验'),
 'storage_power_kw': (1000,'kW','储能额定功率','SIMULATED_ASSUMPTION','独立1MW/2MWh移峰方案；非已建设资产'),
 'storage_capacity_kwh': (2000,'kWh','储能额定容量','SIMULATED_ASSUMPTION','独立1MW/2MWh移峰方案；待场地消防工程核验'),
 'soc_min_ratio': (.1,'比例','最低SOC','SIMULATED_ASSUMPTION','保留10%下限，不调用UPS备用容量'),
 'soc_max_ratio': (.9,'比例','最高SOC','SIMULATED_ASSUMPTION','90%上限，80%可用窗口'),
 'charge_efficiency': (.95,'比例','充电效率','SIMULATED_ASSUMPTION','研究参数，待设备规格确认'),
 'discharge_efficiency': (.95,'比例','放电效率','SIMULATED_ASSUMPTION','研究参数，往返效率为两者乘积'),
 'storage_capex': (2400000,'元','储能新增投资','SIMULATED_ASSUMPTION','研究报价假设1200元/kWh，不是供应商报价'),
 'storage_opex_ratio': (.02,'比例','储能年运维率','SIMULATED_ASSUMPTION','新增储能投资的2%，不计残值，未建衰减模型'),
 'green_ratio': (.2,'比例','绿电采购比例','SIMULATED_ASSUMPTION','假设20%电网购电；未取得绿电合同，不认定真实绿色资格'),
 'green_premium': (.01,'元/kWh','绿电溢价','SIMULATED_ASSUMPTION','研究性增量溢价，非合同报价'),
 'loan_ratio': (.5,'比例','情景债务比例','SIMULATED_ASSUMPTION','历史投资+新增储能投资的50%假设融资，非建议额度'),
 'loan_rate': (.04,'比例','情景年利率','SIMULATED_ASSUMPTION','假设4%，非银行报价'),
 'loan_years': (10,'年','情景还款期限','SIMULATED_ASSUMPTION','10年等额本金，无宽限期'),
 'dr_revenue': (0,'元/年','需求响应收入','EXCLUDED_PENDING_EVIDENCE','缺少注册、测试、结算证据，收入不纳入模型'),
}

def inputs(anchors, kind):
    values = {k: v[0] for k,v in DEFAULTS.items()}
    values.update(anchors)
    changes = {
      'CONSERVATIVE': dict(occupancy=.55, pue=1.35, rack_price=3900, other_cost_ratio=.40, collection_ratio=.95),
      'BASE': {},
      'OPTIMISTIC': dict(occupancy=.80, pue=1.20, rack_price=4400, other_cost_ratio=.31, collection_ratio=.99),
    }
    values.update(changes[kind])
    return values

def simulate(p, year=2025):
    assert 0 <= p['occupancy'] <= 1 and p['pue'] >= 1
    assert 0 < p['charge_efficiency'] <= 1 and 0 < p['discharge_efficiency'] <= 1
    hours = (dt.datetime(year+1,1,1)-dt.datetime(year,1,1)).days*24
    # Shapes are normalized to preserve annual IT energy and energy-weighted PUE.
    shapes = [1 + .04*math.sin(2*math.pi*(h%24-8)/24) + .06*math.sin(2*math.pi*h/hours) for h in range(hours)]
    mean = sum(shapes)/hours
    it = [p['racks']*p['occupancy']*p['it_kw']*v/mean for v in shapes]
    pue_shapes = [1+.03*math.sin(2*math.pi*(h/hours-.25)) for h in range(hours)]
    pue_norm = sum(a*b for a,b in zip(it,pue_shapes))/sum(it)
    floor=p['storage_capacity_kwh']*p['soc_min_ratio']; ceiling=p['storage_capacity_kwh']*p['soc_max_ratio']; soc=floor
    hourly=[]
    for h in range(hours):
        ts=dt.datetime(year,1,1)+dt.timedelta(hours=h); hour=ts.hour
        pue=p['pue']*pue_shapes[h]/pue_norm; load=it[h]*pue
        if hour<8: tariff=p['tariff_valley']
        elif hour in [10,11,14,15,16,17,18]: tariff=p['tariff_critical'] if ts.month in [7,8,9] and hour in [14,15,16] else p['tariff_peak']
        else: tariff=p['tariff_flat']
        charge=min(p['storage_power_kw'],(ceiling-soc)/p['charge_efficiency'],max(0,p['grid_limit_kw']-load)) if hour<8 else 0
        # Discharge exactly across 17–19; no curtailment of computing load.
        discharge=min(p['storage_power_kw'],load,(soc-floor)*p['discharge_efficiency']) if hour in [17,18] else 0
        soc+=charge*p['charge_efficiency']-discharge/p['discharge_efficiency']
        grid=load+charge-discharge
        assert floor-1e-6<=soc<=ceiling+1e-6 and grid>=0
        hourly.append((ts.isoformat(sep=' '),it[h],pue,load,tariff,charge,discharge,soc,grid,load*tariff,grid*tariff))
    assert abs(soc-floor)<1e-6, 'Terminal SOC must equal initial SOC; no free stored energy'
    annual_energy=sum(r[3] for r in hourly); grid_energy=sum(r[8] for r in hourly)
    baseline=sum(r[9] for r in hourly); optimized=sum(r[10] for r in hourly)
    revenue=p['racks']*p['occupancy']*p['rack_price']*12
    green=grid_energy*p['green_ratio']*p['green_premium']; other=revenue*p['other_cost_ratio']
    opex=p['storage_capex']*p['storage_opex_ratio']; reserve=revenue*p['reserve_ratio']
    cash_before_tax=revenue*p['collection_ratio']-optimized-green-other-opex
    tax=max(0,cash_before_tax)*p['tax_ratio']; cfads=cash_before_tax-tax-reserve
    loan=(p['capex']+p['storage_capex'])*p['loan_ratio']; principal=loan/p['loan_years']
    annual=[]
    for y in range(1,int(p['loan_years'])+1):
        service=principal+(loan-principal*(y-1))*p['loan_rate']
        annual.append((y,annual_energy,grid_energy,max(r[8] for r in hourly),
          'WITHIN_REFERENCE_CAP' if grid_energy<=p['energy_cap'] else 'EXCEEDS_REFERENCE_CAP',
          revenue,baseline,optimized,baseline-optimized,green,other,opex,reserve,tax,cfads,service,cfads/service if service else None))
    return hourly,annual

def sql_value(value):
    if value is None: return 'NULL'
    if isinstance(value,(float,int)): return format(value,'.10f')
    # Hex strings avoid SQL-mode-dependent quote/backslash behavior.
    return "CONVERT(X'"+str(value).encode().hex()+"' USING utf8mb4)"

def insert(table, rows):
    return 'INSERT INTO '+table+' VALUES\n'+',\n'.join('('+','.join(map(sql_value,r))+')' for r in rows)+';\n'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--mysql',default='/usr/local/mysql/bin/mysql');ap.add_argument('--login-path',default='bank_ai_local');ap.add_argument('--output',required=True);args=ap.parse_args()
    query="""SELECT JSON_OBJECT('racks',reference_rack_capacity_count,'pue',reference_pue,'energy_cap',reference_annual_energy_cap_kwh,'capex',reference_historical_capex_yuan) FROM compute_facility_project_scenario_v1 WHERE scenario_code='BWX_PHASE3_BASE_V1';
    SELECT time_period,final_price_yuan_kwh FROM electricity_tariff WHERE tariff_id BETWEEN 19109 AND 19112;"""
    raw=subprocess.check_output([args.mysql,'--login-path='+args.login_path,'--batch','--skip-column-names','spdb_power_finance','-e',query],text=True).splitlines()
    anchors=json.loads(raw[0]);keys={'尖峰':'tariff_critical','高峰':'tariff_peak','平':'tariff_flat','低谷':'tariff_valley'}
    for row in raw[1:]:
        period,price=row.split('\t');anchors[keys[period]]=float(price)
    assert all(k in anchors for k in keys.values()), 'All four tariff periods required'
    output=[Path(__file__).parents[1].joinpath('backend/sql/compute_synergy_simulation_v2.sql').read_text(),'START TRANSACTION;\n']
    for kind,label in [('CONSERVATIVE','保守'),('BASE','基准'),('OPTIMISTIC','乐观')]:
        p=inputs(anchors,kind);code=VERSION+'_'+kind; encoded=json.dumps(p,sort_keys=True,ensure_ascii=False)
        hourly,annual=simulate(p)
        # No overwrite on re-run: duplicate version causes rollback in batch mysql.
        output.append(insert('compute_synergy_simulation_v2 (scenario_code,facility_code,scenario_name,project_scope,model_version,simulation_year,data_type,input_sha256,parameters,boundary)',[(code,'SZCF016',label+' · 缺失数据模拟','PHASE_III_EXCHANGE_DISCLOSURE',VERSION,2025,'SIMULATED',hashlib.sha256(encoded.encode()).hexdigest(),encoded,BOUNDARY)]))
        assumptions=[]
        for key,value in p.items():
            if key.startswith('tariff_'): unit='元/kWh';name=key;typ='PUBLIC_PRICE_SCENARIO';basis='electricity_tariff:19109–19112，2026-07公开价固定映射2025全年；时段分配为研究假设'
            else: _,unit,name,typ,basis=DEFAULTS[key]
            if kind!='BASE' and key in ['occupancy','pue','rack_price','other_cost_ratio','collection_ratio']:typ='SIMULATED_ASSUMPTION';basis=label+'敏感性假设；非企业实际值'
            assumptions.append((code,key,name,None,value,unit,typ,basis))
        output.append(insert('compute_synergy_assumption_v2',assumptions))
        for start in range(0,len(hourly),500):output.append(insert('compute_synergy_hourly_v2',[(code,*r,'SIMULATED') for r in hourly[start:start+500]]))
        output.append(insert('compute_synergy_annual_v2',[(code,*r) for r in annual]))
        print(json.dumps(dict(scenario=code,hours=len(hourly),energy_kwh=annual[0][1],grid_energy_kwh=annual[0][2],cfads_proxy=annual[0][14],min_dscr=min(r[16] for r in annual)),ensure_ascii=False))
    output.append('COMMIT;\n');Path(args.output).write_text(''.join(output))

if __name__=='__main__':main()
