<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchSimulation } from '../services/computeApi'
import { amount, decimal, scaled } from '../utils/numbers'
const result=ref(null),error=ref(''),loading=ref(true),selected=ref('BWX_SIM_20260908_V2_BASE')
const scenarios=computed(()=>result.value?.scenarios || [])
const scenario=computed(()=>scenarios.value.find(s=>s.scenario_code===selected.value))
const rows=(key)=>computed(()=>(result.value?.[key] || []).filter(r=>r.scenario_code===selected.value))
const annual=rows('annual'),monthly=rows('monthly'),assumptions=rows('assumptions'),daily=rows('daily')
const first=computed(()=>annual.value[0] || {})
const minDscr=computed(()=>annual.value.length ? Math.min(...annual.value.map(r=>Number(r.dscr_proxy))) : null)
const maxLoad=computed(()=>Math.max(1,...daily.value.map(r=>Number(r.grid_import_kw))))
async function load(){ loading.value=true;error.value='';try{result.value=await fetchSimulation();if(!scenario.value) selected.value=scenarios.value[0]?.scenario_code || ''}catch(e){error.value=e.message}finally{loading.value=false} }
onMounted(load)
</script>
<template>
  <section class="simulation-case" aria-label="百旺信三期缺失数据模拟">
    <header><div><p>独立模拟数据集 · SIMULATED</p><h2>深圳易信科技 · 百旺信三期算电协同</h2><span>将缺失参数变为可查看、可复算的研究假设，保留真实资料缺口。</span></div><b>公开锚点 + 模拟参数</b></header>
    <p v-if="loading" role="status">正在读取模拟数据…</p>
    <p v-else-if="error" role="alert">模拟数据暂不可用：{{ error }} <button @click="load">重试</button></p>
    <p v-else-if="!scenarios.length">尚未生成独立模拟情景。</p>
    <template v-else>
      <nav aria-label="模拟情景"><button v-for="s in scenarios" :key="s.scenario_code" :aria-pressed="selected===s.scenario_code" @click="selected=s.scenario_code">{{ s.scenario_name }}</button></nav>
      <p class="boundary">{{ scenario?.boundary }}</p>
      <div class="kpis">
        <article><span>2025全年模拟电量</span><strong>{{ amount(scaled(first.annual_energy_kwh,10000),2) }} 万kWh</strong><small>每情景8760小时；非实测</small></article>
        <article><span>储能电费毛节省</span><strong>{{ amount(scaled(first.storage_saving_yuan,10000),2) }} 万元</strong><small>未扣储能投资、运维及绿电溢价</small></article>
        <article><span>年CFADS代理</span><strong>{{ amount(scaled(first.cfads_proxy_yuan,10000),2) }} 万元</strong><small>含假设回款、税费和维护准备</small></article>
        <article><span>最低情景DSCR</span><strong>{{ decimal(minDscr,3) }}</strong><small>假设债务比例50%；非额度建议</small></article>
      </div>
      <p v-if="minDscr != null && minDscr < 1" class="model-warning">在当前模拟假设下，现金流代理不足以覆盖情景债务本息；补齐模拟字段不代表项目已具备偿债能力。</p>
      <h3>全年平均日内用电 · 储能仅移峰，不削减IT服务负荷</h3>
      <div class="hour-chart"><div v-for="h in daily" :key="h.hour" :title="`${h.hour}时：设施 ${decimal(h.facility_load_kw,1)} kW；电网 ${decimal(h.grid_import_kw,1)} kW`"><i :style="{height:`${Number(h.grid_import_kw)/maxLoad*100}%`}"></i><span>{{ h.hour }}</span></div></div>
      <p>电网购电包含储能损耗。2026年7月公开电价固定应用于2025研究曲线；不是历史账单。逐小时记录已入库。</p>
      <details><summary>查看12个月模拟汇总</summary><div class="table-scroll"><table><thead><tr><th>月份</th><th>小时数</th><th>设施电量 kWh</th><th>电网电量 kWh</th><th>基准电费 元</th><th>移峰后电费 元</th></tr></thead><tbody><tr v-for="m in monthly" :key="m.month"><td>{{ m.month }}</td><td>{{ m.hour_count }}</td><td>{{ amount(m.facility_energy_kwh) }}</td><td>{{ amount(m.grid_energy_kwh) }}</td><td>{{ amount(m.baseline_cost_yuan) }}</td><td>{{ amount(m.optimized_cost_yuan) }}</td></tr></tbody></table></div></details>
      <details><summary>查看全部输入、缺失原因与替代假设（{{ assumptions.length }}项）</summary><div class="table-scroll"><table><thead><tr><th>输入</th><th>三期实际值</th><th>本情景取值</th><th>性质</th><th>依据 / 缺失原因</th></tr></thead><tbody><tr v-for="a in assumptions" :key="a.field_code"><td>{{ a.field_label }}</td><td>{{ a.actual_value == null ? '未取得当前项目实测值' : amount(a.actual_value,4) }}</td><td>{{ amount(a.simulation_value,4) }} {{ a.unit }}</td><td>{{ a.input_type }}</td><td>{{ a.basis }}</td></tr></tbody></table></div></details>
      <details><summary>查看10年偿债压力情景</summary><p>经营规模、成本与税费保持首年不变，仅按等额本金递减利息；未建立增长、通胀、折旧抵税及储能衰减模型。</p><div class="table-scroll"><table><thead><tr><th>年序</th><th>收入 万元</th><th>CFADS代理 万元</th><th>本息 万元</th><th>DSCR代理</th><th>用电边界</th></tr></thead><tbody><tr v-for="a in annual" :key="a.year_index"><td>{{ a.year_index }}</td><td>{{ amount(scaled(a.revenue_yuan,10000),2) }}</td><td>{{ amount(scaled(a.cfads_proxy_yuan,10000),2) }}</td><td>{{ amount(scaled(a.debt_service_yuan,10000),2) }}</td><td>{{ decimal(a.dscr_proxy,3) }}</td><td>{{ a.energy_cap_status==='WITHIN_REFERENCE_CAP'?'未超参考边界':'超过参考边界' }}</td></tr></tbody></table></div></details>
      <small>模型版本 {{ scenario?.model_version }} · 参数校验 {{ scenario?.input_sha256 }}</small>
    </template>
  </section>
</template>
<style scoped>
.simulation-case{max-width:1180px;margin:36px auto;padding:28px;background:#fff;border:1px solid #d3e0e5;border-radius:12px;color:#203e50;font-size:14px;line-height:1.7}.simulation-case header{display:flex;justify-content:space-between;gap:24px}.simulation-case h2{font-size:28px;margin:4px 0}.simulation-case header p{color:#986515;margin:0}.simulation-case header b{align-self:start;background:#fff1d8;padding:6px 12px;white-space:nowrap}.simulation-case nav{display:flex;gap:12px;margin:24px 0}.simulation-case button{padding:9px 16px;border:1px solid #b7ccc9;background:#f3f8f7;border-radius:6px;cursor:pointer;color:#1a5550}.simulation-case button[aria-pressed=true]{background:#195951;color:white}.boundary{background:#f8f4e9;padding:16px}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.kpis article{padding:16px;background:#f2f7f8}.kpis span,.kpis small{display:block}.kpis strong{font-size:23px}.model-warning{color:#8c5420;background:#fff4e2;padding:12px}.hour-chart{height:180px;display:flex;gap:4px;padding:20px 0 30px}.hour-chart>div{position:relative;flex:1;display:flex;align-items:end}.hour-chart i{width:100%;background:#27887b}.hour-chart span{position:absolute;bottom:-25px;font-size:12px}.table-scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid #dce7e8;min-width:90px}details{border-top:1px solid #dce7e8;padding:16px 0}summary{cursor:pointer;font-weight:600}.simulation-case>small{display:block;overflow-wrap:anywhere;color:#526978}@media(max-width:750px){.simulation-case{margin:16px;padding:18px}.simulation-case header{display:block}.kpis{grid-template-columns:1fr 1fr}.simulation-case nav{flex-wrap:wrap}}
</style>
