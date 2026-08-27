<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { fetchEnterprise, fetchEnterprises, fetchHourlyGeneration, fetchHourlyLoad } from '../services/enterpriseApi'

const props = defineProps({ companyId: { type: String, required: true } })
const emit = defineEmits(['back', 'select-company'])
const originalTitle = document.title
const query = ref('')
const companies = ref([])
const detail = ref(null)
const hourly = ref({ items: [], page: 0, size: 24, total: 0, totalPages: 0 })
const loading = ref(true)
const hourlyLoading = ref(false)
const error = ref('')
const activeFormula = ref([])

const profile = computed(() => detail.value?.profile || {})
const feature = computed(() => detail.value?.energyFeature || {})
const snapshot = computed(() => detail.value?.snapshot || {})
const coverage = computed(() => detail.value?.hourlyCoverage?.[0] || {})
const monthly = computed(() => detail.value?.monthlyPower || [])
const generationCoverage = computed(() => detail.value?.generationCoverage?.[0] || {})
const monthlyGeneration = computed(() => detail.value?.monthlyGeneration || [])
const publicMetrics = computed(() => detail.value?.publicEnergyMetrics || [])
const financials = computed(() => detail.value?.financials || [])
const provenance = computed(() => Object.fromEntries((detail.value?.energyFeatureProvenance || []).map((item) => [item.fieldName, item])))
const resultProvenance = computed(() => Object.fromEntries((detail.value?.snapshotFieldProvenance || []).map((item) => [item.fieldName, item])))
const isGenerator = computed(() => profile.value?.powerChainRole === 'GENERATOR')
const latestFinancial = computed(() => financials.value[0] || {})
const filteredCompanies = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  if (!keyword) return companies.value
  return companies.value.filter((item) =>
    [item.companyId, item.companyName, item.industryName].some((value) => String(value || '').toLowerCase().includes(keyword)),
  )
})

function present(value) { return value !== null && value !== undefined && value !== '' }
function text(value, fallback = '暂无数据') { return present(value) ? value : fallback }
function number(value, digits = 0) {
  if (!present(value) || Number.isNaN(Number(value))) return '暂无数据'
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(Number(value))
}
function percent(value, digits = 1) { return present(value) ? `${number(Number(value) * 100, digits)}%` : '暂无数据' }
function dateTime(value) { return present(value) ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '暂无数据' }
function levelClass(value) { return String(value || 'unknown').toLowerCase() }
function publicMetric(code) { return publicMetrics.value.find((item) => item.metricCode === code) || {} }
function origin(field) {
  const labels = { PUBLIC: '公开披露', MODEL_ESTIMATE: '模型估算', TARIFF_SCENARIO: '情景电价', SIMULATED_SHAPE: '模拟负荷形状' }
  return labels[provenance.value[field]?.provenanceType] || ''
}
function resultOriginLabel(field) {
  const labels = { SIMULATED_MODEL: '模型模拟', FORMULA_DERIVED: '公式推算', SCENARIO_PARAMETER: '情景参数', MIXED_DERIVED: '混合推算', PUBLIC: '公开披露' }
  return labels[resultProvenance.value[field]?.provenanceType] || '来源待补充'
}
function openFormula(...fields) { activeFormula.value = fields.map((field) => resultProvenance.value[field]).filter(Boolean) }
function closeFormula() { activeFormula.value = [] }
function handleKeydown(event) { if (event.key === 'Escape') closeFormula() }

async function loadCompanies() { companies.value = await fetchEnterprises('', 200) }
async function loadDetail() {
  loading.value = true
  error.value = ''
  hourly.value = { items: [], page: 0, size: 24, total: 0, totalPages: 0 }
  try {
    detail.value = await fetchEnterprise(props.companyId)
    document.title = `${profile.value.companyName}｜企业全部数据`
    const analysisYear = isGenerator.value ? generationCoverage.value.analysisYear : coverage.value.analysisYear
    if (analysisYear) await loadHourly(0)
  } catch (exception) {
    detail.value = null
    error.value = exception.message
  } finally { loading.value = false }
}
async function loadHourly(page) {
  hourlyLoading.value = true
  try {
    const year = isGenerator.value ? generationCoverage.value.analysisYear : coverage.value.analysisYear
    hourly.value = isGenerator.value
      ? await fetchHourlyGeneration(props.companyId, { year, page, size: 24 })
      : await fetchHourlyLoad(props.companyId, { year, page, size: 24 })
  }
  catch (exception) { error.value = exception.message }
  finally { hourlyLoading.value = false }
}

onMounted(async () => {
  window.addEventListener('keydown', handleKeydown)
  try { await loadCompanies() } catch (exception) { error.value = exception.message }
  await loadDetail()
})
watch(() => props.companyId, loadDetail)
onBeforeUnmount(() => { document.title = originalTitle; window.removeEventListener('keydown', handleKeydown) })
</script>

<template>
  <div class="enterprise-data-page">
    <header class="detail-site-header"><div class="detail-topbar">
      <button class="brand" type="button" aria-label="返回平台首页" @click="emit('back')"><span class="brand-mark"><i></i><i></i><i></i></span><span><strong>电力能源金融</strong><small>企业数据中心</small></span></button>
      <div class="detail-breadcrumb"><span>企业画像</span><b>/</b><strong>{{ profile.companyName || companyId }}</strong></div>
      <button class="detail-back-button" type="button" @click="emit('back')">← 返回首页</button>
    </div></header>

    <div v-if="loading" class="enterprise-loading"><span></span><h1>正在读取企业数据</h1><p>Java 接口正在查询 MySQL，请稍候。</p></div>

    <div v-else-if="detail" class="enterprise-data-shell">
      <aside class="enterprise-browser">
        <div class="browser-heading"><p>企业数据目录</p><span>{{ companies.length }} 家企业</span></div>
        <label class="enterprise-search"><span>⌕</span><input v-model="query" type="search" placeholder="搜索企业名称、ID 或行业" /></label>
        <div class="enterprise-search-results" aria-live="polite">
          <button v-for="item in filteredCompanies" :key="item.companyId" :class="['enterprise-result', { active: item.companyId === companyId }]" type="button" @click="emit('select-company', item.companyId)">
            <span><b>{{ item.companyName }}</b><small>{{ item.companyId }} · {{ text(item.industryName, '行业待补充') }}</small></span>
            <em :class="levelClass(item.opportunityLevel)">{{ text(item.opportunityLevel, '—') }}</em>
          </button>
          <p v-if="filteredCompanies.length === 0" class="no-company-result">未找到匹配企业。</p>
        </div>
        <div class="browser-note"><span>数据来源</span><p>本页由 Java 只读接口实时查询 MySQL。空值明确显示“暂无数据”，不进行推测填充。</p></div>
      </aside>

      <main class="enterprise-data-main">
        <div v-if="error" class="enterprise-api-warning">{{ error }}</div>
        <section class="enterprise-profile-hero">
          <div><p class="profile-kicker">{{ profile.companyId }} · {{ text(snapshot.snapshotVersion, '主数据') }}</p><h1>{{ profile.companyName }}</h1>
            <div class="profile-tags"><span>{{ text(profile.industryName, '行业待补充') }}</span><span>{{ text(profile.cityName, '地区待补充') }}</span><span>{{ text(feature.dataType || snapshot.dataType, '数据类型待确认') }}</span></div>
          </div>
          <div class="profile-rating"><small>业务机会</small><strong :class="levelClass(snapshot.opportunityLevel)">{{ text(snapshot.opportunityLevel, '未评级') }}</strong><p>优先级 {{ text(snapshot.businessPriority, '—') }} · 风险 {{ text(snapshot.riskLevel, '—') }}</p></div>
        </section>

        <section v-if="snapshot.runStatus === 'ARCHIVED'" class="enterprise-api-warning">
          当前储能与融资快照为模拟结果：不代表公开事实层的当前结论。
        </section>

        <section v-if="isGenerator" class="enterprise-key-metrics">
          <article><span>控股装机容量</span><strong>{{ number(publicMetric('INSTALLED_CAPACITY').metricValue, 2) }} 万kW</strong><p>2025年集团公开口径</p></article>
          <article><span>全年上网电量</span><strong>{{ number(publicMetric('ON_GRID_ELECTRICITY').metricValue, 2) }} 亿kWh</strong><p>同比增长 12.70%</p></article>
          <article><span>市场化交易占比</span><strong>{{ number(publicMetric('MARKET_TRADED_RATIO').metricValue, 2) }}%</strong><p>{{ number(publicMetric('MARKET_TRADED_ELECTRICITY').metricValue, 2) }} 亿kWh</p></article>
          <article><span>新增储能项目储备</span><strong>{{ number(publicMetric('NEW_STORAGE_POWER').metricValue, 0) }} 万kW</strong><p>{{ number(publicMetric('NEW_STORAGE_CAPACITY').metricValue, 0) }} 万kWh · 非已投运口径</p></article>
        </section>
        <section v-else class="enterprise-key-metrics">
          <article><span>负荷数据覆盖</span><strong>{{ number(coverage.rowCount) }} h</strong><p>{{ dateTime(coverage.startTime) }} — {{ dateTime(coverage.endTime) }}</p></article>
          <article><span>推荐储能配置</span><strong>{{ number(snapshot.storagePowerMw, 2) }} MW</strong><p>{{ number(snapshot.storageCapacityMwh, 2) }} MWh · {{ number(snapshot.storageDurationHour, 1) }}h</p></article>
          <article><span>项目 NPV</span><strong>{{ number(snapshot.npvWanyuan, 2) }} 万元</strong><p>{{ text(snapshot.storageVersion, '无储能快照') }}</p></article>
          <article><span>最低 DSCR</span><strong>{{ number(snapshot.baseMinDscr, 3) }}</strong><p>最大债务比例 {{ percent(snapshot.maxDebtRatio, 0) }}</p></article>
        </section>

        <div class="enterprise-data-grid">
          <section v-if="isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>01</span><h2>发电与市场运营</h2></div><em>PUBLIC 2025</em></div>
            <dl class="enterprise-data-list"><div><dt>发电量</dt><dd>{{ number(publicMetric('GROSS_GENERATION').metricValue, 2) }} 亿kWh</dd></div><div><dt>上网电量</dt><dd>{{ number(publicMetric('ON_GRID_ELECTRICITY').metricValue, 2) }} 亿kWh</dd></div><div><dt>外购电量</dt><dd>{{ number(publicMetric('PURCHASED_ELECTRICITY').metricValue, 4) }} 亿kWh</dd></div><div><dt>市场化交易电量</dt><dd>{{ number(publicMetric('MARKET_TRADED_ELECTRICITY').metricValue, 2) }} 亿kWh</dd></div><div><dt>平均上网电价</dt><dd>{{ number(publicMetric('AVERAGE_ON_GRID_PRICE').metricValue, 2) }} 元/kWh</dd></div><div><dt>厂用电率 / 利用小时</dt><dd>{{ number(publicMetric('PLANT_AUXILIARY_RATE').metricValue, 2) }}% / {{ number(publicMetric('UTILIZATION_HOURS').metricValue) }}h</dd></div></dl>
          </section>
          <section v-if="isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>02</span><h2>装机与能源结构</h2></div><em>PUBLIC 2025</em></div>
            <dl class="enterprise-data-list"><div><dt>煤电 / 气电</dt><dd>{{ number(publicMetric('COAL_CAPACITY').metricValue, 2) }} / {{ number(publicMetric('GAS_CAPACITY').metricValue, 2) }} 万kW</dd></div><div><dt>风电 / 光伏</dt><dd>{{ number(publicMetric('WIND_CAPACITY').metricValue, 2) }} / {{ number(publicMetric('SOLAR_CAPACITY').metricValue, 2) }} 万kW</dd></div><div><dt>水电 / 垃圾发电</dt><dd>{{ number(publicMetric('HYDRO_CAPACITY').metricValue, 2) }} / {{ number(publicMetric('WASTE_CAPACITY').metricValue, 2) }} 万kW</dd></div><div><dt>清洁能源装机占比</dt><dd>{{ number(publicMetric('CLEAN_CAPACITY_RATIO').metricValue, 2) }}%</dd></div><div><dt>可再生能源装机占比</dt><dd>{{ number(publicMetric('RENEWABLE_CAPACITY_RATIO').metricValue, 2) }}%</dd></div><div><dt>售电代理用户购电量</dt><dd>{{ number(publicMetric('RETAIL_AGENT_PURCHASE').metricValue, 2) }} 亿kWh</dd></div></dl>
          </section>
          <section v-if="isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>03</span><h2>公开财务画像</h2></div><em>2025</em></div>
            <dl class="enterprise-data-list"><div><dt>营业收入</dt><dd>{{ number(latestFinancial.revenueWanyuan, 2) }} 万元</dd></div><div><dt>归母净利润</dt><dd>{{ number(latestFinancial.netProfitWanyuan, 2) }} 万元</dd></div><div><dt>总资产</dt><dd>{{ number(latestFinancial.totalAssetsWanyuan, 2) }} 万元</dd></div><div><dt>总负债</dt><dd>{{ number(latestFinancial.totalLiabilitiesWanyuan, 2) }} 万元</dd></div><div><dt>资产负债率</dt><dd>{{ percent(latestFinancial.debtRatio, 2) }}</dd></div><div><dt>经营现金流</dt><dd>{{ number(latestFinancial.operatingCashflowWanyuan, 2) }} 万元</dd></div></dl>
          </section>
          <section v-if="isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>04</span><h2>银行业务线索</h2></div><em>{{ text(snapshot.snapshotVersion) }}</em></div>
            <dl class="enterprise-data-list"><div><dt>机会等级</dt><dd>{{ text(snapshot.opportunityLevel) }}</dd></div><div><dt>资料准备度</dt><dd>{{ text(snapshot.readinessLevel) }}</dd></div><div><dt>风险等级</dt><dd>{{ text(snapshot.riskLevel) }}</dd></div><div><dt>推荐产品</dt><dd>{{ text(snapshot.recommendedProduct) }}</dd></div><div><dt>融资测算状态</dt><dd>{{ text(snapshot.financingStatus) }}</dd></div></dl><div v-if="snapshot.recommendationText" class="enterprise-action-note"><span>下一步动作</span><p>{{ snapshot.recommendationText }}</p></div>
          </section>

          <section v-if="!isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>01</span><h2>企业与用电画像</h2></div><em>{{ text(feature.featureVersion, 'NO FEATURE') }}</em></div>
            <dl class="enterprise-data-list">
              <div><dt>统一社会信用代码</dt><dd>{{ text(profile.creditCode) }}</dd></div><div><dt>分析年度</dt><dd>{{ text(feature.analysisYear) }}</dd></div>
              <div><dt>年用电量</dt><dd>{{ number(feature.annualPowerKwh) }} kWh<small class="field-origin">{{ origin('annual_power_kwh') }}</small></dd></div><div><dt>年电费</dt><dd>{{ number(feature.annualElectricityCostYuan, 2) }} 元<small class="field-origin">{{ origin('annual_electricity_cost_yuan') }}</small></dd></div>
              <div><dt>平均度电成本</dt><dd>{{ number(feature.avgPriceYuanKwh, 4) }} 元/kWh<small class="field-origin">{{ origin('avg_price_yuan_kwh') }}</small></dd></div><div><dt>峰+尖峰暴露率</dt><dd>{{ percent(feature.peakPlusCriticalRatio) }}<small class="field-origin">{{ origin('peak_plus_critical_ratio') }}</small></dd></div>
              <div><dt>最大负荷 / P95</dt><dd>{{ number(feature.maxLoadKw, 2) }} / {{ number(feature.p95LoadKw, 2) }} kW<small class="field-origin">{{ origin('max_load_kw') }}</small></dd></div><div><dt>负荷率 / 负荷CV</dt><dd>{{ number(feature.loadFactor, 4) }} / {{ number(feature.loadCv, 4) }}<small class="field-origin">{{ origin('load_factor') }}</small></dd></div>
            </dl>
            <p v-if="feature.dataType === 'MIXED'" class="enterprise-model-note">{{ feature.featureVersion }}：年度规模来自公开披露；2025月度、小时、电费、最大负荷和 P95 均为研究模拟或模型估算，不是企业实测账单。</p>
          </section>
          <section v-if="!isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>02</span><h2>储能经济性</h2></div><em>{{ text(snapshot.storageVersion) }}</em></div>
            <dl class="enterprise-data-list result-lineage-list">
              <div><dt>储能功率</dt><dd>{{ number(snapshot.storagePowerMw, 2) }} MW<button class="result-origin-button" type="button" :title="resultProvenance.storage_power_mw?.notes" @click="openFormula('storage_power_mw')">{{ resultOriginLabel('storage_power_mw') }} · 查看选择规则</button></dd></div>
              <div><dt>储能容量</dt><dd>{{ number(snapshot.storageCapacityMwh, 2) }} MWh<button class="result-origin-button" type="button" :title="resultProvenance.storage_capacity_mwh?.notes" @click="openFormula('storage_capacity_mwh')">{{ resultOriginLabel('storage_capacity_mwh') }} · 查看公式</button></dd></div>
              <div><dt>储能时长</dt><dd>{{ number(snapshot.storageDurationHour, 2) }} 小时<button class="result-origin-button" type="button" :title="resultProvenance.storage_duration_hour?.notes" @click="openFormula('storage_duration_hour')">{{ resultOriginLabel('storage_duration_hour') }} · 查看公式</button></dd></div>
              <div><dt>总投资</dt><dd>{{ number(snapshot.capexWanyuan, 2) }} 万元<button class="result-origin-button" type="button" :title="resultProvenance.capex_wanyuan?.notes" @click="openFormula('capex_wanyuan')">{{ resultOriginLabel('capex_wanyuan') }} · 查看CAPEX公式</button></dd></div>
              <div><dt>年收益</dt><dd>{{ number(snapshot.annualBenefitWanyuan, 2) }} 万元<button class="result-origin-button" type="button" :title="resultProvenance.annual_benefit_wanyuan?.notes" @click="openFormula('annual_benefit_wanyuan')">{{ resultOriginLabel('annual_benefit_wanyuan') }} · 查看公式</button></dd></div>
              <div><dt>NPV / IRR</dt><dd>{{ number(snapshot.npvWanyuan, 2) }} 万元 / {{ percent(snapshot.irr, 2) }}<button class="result-origin-button" type="button" @click="openFormula('npv_wanyuan', 'irr')">公式推算 · 查看NPV/IRR</button></dd></div>
              <div><dt>静态回收期</dt><dd>{{ number(snapshot.paybackYear, 2) }} 年<button class="result-origin-button" type="button" :title="resultProvenance.payback_year?.notes" @click="openFormula('payback_year')">{{ resultOriginLabel('payback_year') }} · 查看公式</button></dd></div>
            </dl>
          </section>
          <section v-if="!isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>03</span><h2>融资能力</h2></div><em>{{ text(snapshot.financeVersion) }}</em></div>
            <dl class="enterprise-data-list result-lineage-list">
              <div><dt>基准债务比例</dt><dd>{{ percent(snapshot.baseDebtRatio, 0) }}<button class="result-origin-button" type="button" :title="resultProvenance.base_debt_ratio?.notes" @click="openFormula('base_debt_ratio')">{{ resultOriginLabel('base_debt_ratio') }} · 查看参数</button></dd></div>
              <div><dt>基准贷款额</dt><dd>{{ number(snapshot.baseLoanAmountWanyuan, 2) }} 万元<button class="result-origin-button" type="button" :title="resultProvenance.base_loan_amount_wanyuan?.notes" @click="openFormula('base_loan_amount_wanyuan')">{{ resultOriginLabel('base_loan_amount_wanyuan') }} · 查看公式</button></dd></div>
              <div><dt>最低 DSCR</dt><dd>{{ number(snapshot.baseMinDscr, 3) }}<button class="result-origin-button" type="button" :title="resultProvenance.base_min_dscr?.notes" @click="openFormula('base_min_dscr')">{{ resultOriginLabel('base_min_dscr') }} · 查看DSCR公式</button></dd></div>
              <div><dt>最大债务比例</dt><dd>{{ percent(snapshot.maxDebtRatio, 0) }}<button class="result-origin-button" type="button" :title="resultProvenance.max_debt_ratio?.notes" @click="openFormula('max_debt_ratio')">{{ resultOriginLabel('max_debt_ratio') }} · 查看搜索约束</button></dd></div>
              <div><dt>最大贷款额</dt><dd>{{ number(snapshot.maxLoanAmountWanyuan, 2) }} 万元<button class="result-origin-button" type="button" :title="resultProvenance.max_loan_amount_wanyuan?.notes" @click="openFormula('max_loan_amount_wanyuan')">{{ resultOriginLabel('max_loan_amount_wanyuan') }} · 查看公式</button></dd></div>
              <div><dt>融资状态</dt><dd>{{ text(snapshot.financingStatus) }}<button class="result-origin-button" type="button" :title="resultProvenance.financing_status?.notes" @click="openFormula('financing_status')">{{ resultOriginLabel('financing_status') }} · 查看判定规则</button></dd></div>
            </dl>
          </section>
          <section v-if="!isGenerator" class="enterprise-data-card"><div class="data-card-heading"><div><span>04</span><h2>政策、风险与建议</h2></div><em>{{ text(snapshot.policyVersion) }}</em></div>
            <dl class="enterprise-data-list"><div><dt>综合风险</dt><dd>{{ text(snapshot.overallRisk) }}</dd></div><div><dt>价差 / CAPEX 风险</dt><dd>{{ text(snapshot.tariffSpreadRisk) }} / {{ text(snapshot.capexRisk) }}</dd></div><div><dt>接入 / 衰减风险</dt><dd>{{ text(snapshot.gridCapacityRisk) }} / {{ text(snapshot.degradationRisk) }}</dd></div><div><dt>绿色金融状态</dt><dd>{{ text(snapshot.greenFinanceStatus) }}</dd></div><div><dt>推荐产品</dt><dd>{{ text(snapshot.recommendedProduct) }}</dd></div></dl>
            <div v-if="snapshot.recommendationText" class="enterprise-action-note"><span>下一步动作</span><p>{{ snapshot.recommendationText }}</p></div>
          </section>
        </div>

        <section v-if="publicMetrics.length" class="enterprise-record-section"><div class="catalog-heading"><div><p>V3 公开年度事实</p><h2>经来源与统计边界核验的能源披露</h2></div><span>{{ publicMetrics.length }} 项 · PUBLIC</span></div>
          <div class="enterprise-table-wrap"><table><thead><tr><th>年度</th><th>指标</th><th>披露值</th><th>归一值(kWh)</th><th>统计边界</th><th>替代级别</th><th>来源</th></tr></thead><tbody><tr v-for="row in publicMetrics" :key="row.metricId"><td>{{ row.reportYear }}</td><td>{{ row.metricName }}</td><td>{{ number(row.metricValue, 2) }} {{ row.metricUnit }}</td><td>{{ present(row.normalizedValueKwh) ? number(row.normalizedValueKwh, 2) : '—' }}</td><td>{{ row.reportingScope }}</td><td>{{ row.replacementEligibility }}</td><td><a :href="row.sourceUrl" target="_blank" rel="noreferrer">{{ row.sourceTitle }}</a><small v-if="row.sourcePage">{{ row.sourcePage }}</small></td></tr></tbody></table></div>
        </section>

        <section v-if="!isGenerator" class="enterprise-record-section"><div class="catalog-heading"><div><p>月度用电记录</p><h2>月度电量、成本与最大需量</h2></div><span>{{ monthly.length }} 条数据库记录 · 以类型列为准</span></div>
          <div class="enterprise-table-wrap"><table><thead><tr><th>年月</th><th>用电量(kWh)</th><th>电费(元)</th><th>均价</th><th>峰/平/谷/尖峰(kWh)</th><th>最大需量(kW)</th><th>类型</th></tr></thead><tbody><tr v-for="row in monthly" :key="row.recordId"><td>{{ row.year }}-{{ String(row.month).padStart(2, '0') }}</td><td>{{ number(row.powerConsumptionKwh, 2) }}</td><td>{{ number(row.electricityCostYuan, 2) }}</td><td>{{ number(row.averagePriceYuanKwh, 4) }}</td><td>{{ number(row.peakPowerKwh) }} / {{ number(row.flatPowerKwh) }} / {{ number(row.valleyPowerKwh) }} / {{ number(row.criticalPeakKwh) }}</td><td>{{ number(row.maxDemandKw, 2) }}</td><td>{{ row.dataType }}</td></tr><tr v-if="monthly.length === 0"><td colspan="7">暂无月度用电记录</td></tr></tbody></table></div>
        </section>

        <section v-if="!isGenerator" class="enterprise-record-section"><div class="catalog-heading"><div><p>小时负荷明细</p><h2>活动负荷记录分页查阅</h2></div><span>共 {{ number(hourly.total) }} 条 · 每页 24 条</span></div>
          <div class="enterprise-table-wrap" :class="{ 'is-loading': hourlyLoading }"><table><thead><tr><th>时间</th><th>电量(kWh)</th><th>负荷(kW)</th><th>时段</th><th>电价</th><th>电费(元)</th><th>类型</th></tr></thead><tbody><tr v-for="row in hourly.items" :key="row.loadId"><td>{{ dateTime(row.ts) }}</td><td>{{ number(row.powerConsumptionKwh, 3) }}</td><td>{{ number(row.loadKw, 3) }}</td><td>{{ text(row.timePeriod) }}</td><td>{{ number(row.electricityPriceYuanKwh, 4) }}</td><td>{{ number(row.electricityCostYuan, 2) }}</td><td>{{ row.dataType }}</td></tr><tr v-if="hourly.items.length === 0"><td colspan="7">该企业暂无小时负荷记录</td></tr></tbody></table></div>
          <div v-if="hourly.totalPages > 1" class="enterprise-pagination"><button :disabled="hourly.page === 0 || hourlyLoading" @click="loadHourly(hourly.page - 1)">上一页</button><span>第 {{ hourly.page + 1 }} / {{ hourly.totalPages }} 页</span><button :disabled="hourly.page + 1 >= hourly.totalPages || hourlyLoading" @click="loadHourly(hourly.page + 1)">下一页</button></div>
        </section>

        <section v-if="isGenerator" class="enterprise-record-section"><div class="catalog-heading"><div><p>月度发电情景</p><h2>2025月度发电量与上网电量</h2></div><span>{{ monthlyGeneration.length }} 条 · 年度公开总量锚定</span></div>
          <div class="enterprise-table-wrap"><table><thead><tr><th>年月</th><th>发电量(kWh)</th><th>上网电量(kWh)</th><th>平均容量因子</th><th>类型</th><th>质量</th></tr></thead><tbody><tr v-for="row in monthlyGeneration" :key="row.generationMonthId"><td>{{ row.year }}-{{ String(row.month).padStart(2, '0') }}</td><td>{{ number(row.grossGenerationKwh, 2) }}</td><td>{{ number(row.onGridGenerationKwh, 2) }}</td><td>{{ percent(row.averageCapacityFactor, 2) }}</td><td>{{ row.dataType }}</td><td>{{ row.dataQuality }}</td></tr></tbody></table></div>
        </section>

        <section v-if="isGenerator" class="enterprise-record-section"><div class="catalog-heading"><div><p>小时发电明细</p><h2>2025年8760小时发电情景</h2></div><span>共 {{ number(hourly.total) }} 条 · 年度总量公开、小时形状模拟</span></div>
          <div class="enterprise-table-wrap" :class="{ 'is-loading': hourlyLoading }"><table><thead><tr><th>时间</th><th>发电量(kWh)</th><th>上网电量(kWh)</th><th>发电功率(kW)</th><th>容量因子</th><th>类型</th></tr></thead><tbody><tr v-for="row in hourly.items" :key="row.generationId"><td>{{ dateTime(row.ts) }}</td><td>{{ number(row.grossGenerationKwh, 3) }}</td><td>{{ number(row.onGridGenerationKwh, 3) }}</td><td>{{ number(row.grossGenerationKw, 3) }}</td><td>{{ percent(row.capacityFactor, 2) }}</td><td>{{ row.dataType }}</td></tr></tbody></table></div>
          <div v-if="hourly.totalPages > 1" class="enterprise-pagination"><button :disabled="hourly.page === 0 || hourlyLoading" @click="loadHourly(hourly.page - 1)">上一页</button><span>第 {{ hourly.page + 1 }} / {{ hourly.totalPages }} 页</span><button :disabled="hourly.page + 1 >= hourly.totalPages || hourlyLoading" @click="loadHourly(hourly.page + 1)">下一页</button></div>
        </section>

        <section v-if="financials.length" class="enterprise-record-section"><div class="catalog-heading"><div><p>企业财务记录</p><h2>已落库年度财务信息</h2></div><span>{{ financials.length }} 条</span></div><div class="enterprise-table-wrap"><table><thead><tr><th>年度</th><th>营收(万元)</th><th>净利润(万元)</th><th>总资产(万元)</th><th>负债率</th><th>数据质量</th></tr></thead><tbody><tr v-for="row in financials" :key="row.financialYear"><td>{{ row.financialYear }}</td><td>{{ number(row.revenueWanyuan, 2) }}</td><td>{{ number(row.netProfitWanyuan, 2) }}</td><td>{{ number(row.totalAssetsWanyuan, 2) }}</td><td>{{ percent(row.debtRatio) }}</td><td>{{ text(row.dataQuality) }}</td></tr></tbody></table></div></section>
        <section class="enterprise-page-boundary"><b>研究边界</b><p>PUBLIC 仅代表公开披露年度及其明确统计边界；2025月度及8760小时序列均标记为 SIMULATED，不是企业实测。公开年度总量仅作为模拟曲线的年度锚点，不会把月度或小时记录标成 ACTUAL。</p></section>
      </main>
    </div>

    <main v-else class="enterprise-not-found"><span>连接失败</span><h1>无法读取该企业</h1><p>{{ error || `企业编号“${companyId}”不存在。` }}</p><button type="button" @click="emit('back')">返回企业画像</button></main>
    <footer class="enterprise-detail-footer"><span>SPDB POWER FINANCE · ENTERPRISE DATA</span><span>JAVA API · MYSQL READ ONLY</span></footer>

    <div v-if="activeFormula.length" class="formula-modal-backdrop" role="presentation" @click.self="closeFormula">
      <section class="formula-modal" role="dialog" aria-modal="true" aria-labelledby="formula-modal-title">
        <button class="formula-modal-close" type="button" aria-label="关闭公式说明" @click="closeFormula">×</button>
        <p>字段级结果溯源</p><h2 id="formula-modal-title">计算依据与公式</h2>
        <article v-for="item in activeFormula" :key="item.fieldName">
          <div><strong>{{ item.fieldLabel }}</strong><span>{{ resultOriginLabel(item.fieldName) }}</span></div>
          <code>{{ item.formulaText }}</code>
          <dl><div><dt>来源表</dt><dd>{{ item.sourceTable }}</dd></div><div><dt>来源字段</dt><dd>{{ item.sourceField }}</dd></div></dl>
          <small>{{ item.notes }}</small>
        </article>
        <div class="formula-modal-boundary"><b>研究边界</b><span>公式和参数用于课题情景测算；除明确标记 PUBLIC 的字段外，不代表企业真实项目数据或银行授信条件。</span></div>
      </section>
    </div>
  </div>
</template>
