<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import EnterpriseDataView from './components/EnterpriseDataView.vue'
import DataCatalogView from './components/DataCatalogView.vue'
import BankWorkbenchView from './components/BankWorkbenchView.vue'
import AiAssistantView from './components/AiAssistantView.vue'
import ProjectAnalysisView from './components/ProjectAnalysisView.vue'
import PowerSourceStructure from './components/PowerSourceStructure.vue'
import { fetchHomeSummary, fetchLoadPriceWindow } from './services/enterpriseApi'

function researchSiteUrl(configuredUrl, defaultPort) {
  const configured = configuredUrl?.trim()
  const fallback = `${window.location.protocol}//${window.location.hostname}:${defaultPort}`
  try {
    const url = new URL(configured || fallback)
    if (url.pathname.replace(/\/+$/, '') === '/login') url.pathname = ''
    else url.pathname = url.pathname.replace(/\/+$/, '')
    url.search = ''
    url.hash = ''
    return url.toString().replace(/\/$/, '')
  } catch {
    return fallback
  }
}

const powerSiteUrl = researchSiteUrl(import.meta.env.VITE_POWER_SITE_URL, 5173)
const computeSiteUrl = researchSiteUrl(import.meta.env.VITE_COMPUTE_SITE_URL, 5174)
const bankWorkbenchUrl = `${powerSiteUrl}/bank-workbench`
const activeSignalId = ref('tariff')
const selectedCompanyId = ref('C000020')
const menuOpen = ref(false)
const pendingDataView = ref(null)
const currentPath = ref(window.location.pathname)
const companies = ref([])
const activeRun = ref({})
const analysisCoverage = ref({})
const homeError = ref('')
const loadPriceWindow = ref({ series: [] })
const loadPriceLoading = ref(true)
const loadPriceError = ref('')

const navigation = [
  { label: '能源结构', target: 'energy-mix' },
  { label: '市场信号', target: 'market' },
  { label: '评估方法', target: 'method' },
  { label: '企业画像', target: 'enterprises' },
  { label: '模型溯源', target: 'trace' },
]

const signals = [
  {
    id: 'tariff',
    index: '01',
    title: '峰谷价差',
    shortTitle: '价格信号',
    description: '分时电价将同一度电在不同时段的成本差异转成可度量的移峰空间。',
    question: '企业在何时用电，成本会明显不同？',
    measures: ['峰、平、谷、尖峰电量占比', '平均度电成本', '峰 + 尖峰暴露率'],
    measureDetails: [
      { title: '峰、平、谷、尖峰电量占比', text: '高价时段用电越集中，储能套利和削峰收益空间通常越大，会直接影响项目现金流和可融资规模。' },
      { title: '平均度电成本', text: '反映企业电力成本压力与节能投资承受能力，是判断回收期、现金流改善和还款来源的重要基准。' },
      { title: '峰 + 尖峰暴露率', text: '暴露率越高，企业对电价波动越敏感；银行需关注价差收窄对 NPV、DSCR 和债务比例的压力。' },
    ],
    accent: 'blue',
    note: '用于识别可套利的电价窗口，不等同于企业已签约电价。',
  },
  {
    id: 'demand',
    index: '02',
    title: '月度最大需量',
    shortTitle: '负荷信号',
    description: '月度峰值而非单一全年峰值，决定储能削峰能够带来的实际需量管理价值。',
    question: '储能能否在关键时刻压低企业最大负荷？',
    measures: ['各月原始最大负荷', '储能后最大需量', '需量管理节省额'],
    measureDetails: [
      { title: '各月原始最大负荷', text: '构成需量电费与配电容量压力的测算基线；峰值是否稳定，决定节省收益能否形成可预测的还款现金流。' },
      { title: '储能后最大需量', text: '反映储能真实削峰效果。压降越稳定，项目的工程价值与成本改善越清晰，也越便于银行核验融资用途。' },
      { title: '需量管理节省额', text: '可转化为项目持续经营现金流，并进一步影响 NPV、最低 DSCR、贷款期限与最大可承受债务比例。' },
    ],
    accent: 'teal',
    note: '基于 8760 小时负荷的企业才可进行高置信度的负荷仿真。',
  },
  {
    id: 'policy',
    index: '03',
    title: '政策与需求响应',
    shortTitle: '政策信号',
    description: '储能、需求响应、虚拟电厂和绿色金融政策决定项目可进入的业务与支持路径。',
    question: '项目具备哪些潜在参与资格与合规前提？',
    measures: ['政策适用状态', '尽调事项', '潜在金融产品匹配'],
    measureDetails: [
      { title: '政策适用状态', text: '决定项目能否进入需求响应、虚拟电厂或绿色金融支持路径，并影响可计入测算的收益边界与准入条件。' },
      { title: '尽调事项', text: '接入、场地、审批和主体资格的不确定性会形成合规与落地风险，银行可据此设置提款前提和核验清单。' },
      { title: '潜在金融产品匹配', text: '将项目现金流、期限与政策属性映射到绿色贷款等产品，辅助判断融资期限、增信安排和业务优先级。' },
    ],
    accent: 'amber',
    note: '政策匹配为潜在适用判断，真实资格仍需结合项目和企业材料核验。',
  },
]

const coverageData = ref([
  { value: '24', label: '区域电力统计记录', route: 'regional-power-statistics', page: '区域电力统计' },
  { value: '1,595', label: '电价记录', route: 'electricity-tariff', page: '分时电价数据' },
  { value: '70', label: '市场交易记录', route: 'power-market-trade', page: '电力市场交易数据' },
  { value: '34', label: '政策规则条目', route: 'policy-rules', page: '政策规则库' },
])

const pipeline = [
  { index: '01', title: '能源结构', text: '全国、广东与深圳的装机及发电构成', tag: '宏观方向' },
  { index: '02', title: '市场与政策', text: '价格、交易、区域供需与政策规则', tag: '外部环境' },
  { index: '03', title: '企业负荷', text: '月度账单与 8760 小时用电形态', tag: '用能行为' },
  { index: '04', title: '储能仿真', text: '功率 × 时长 × 接入约束 × 成本曲线', tag: '工程经济' },
  { index: '05', title: '融资测算', text: 'NPV、IRR、DSCR 与债务承受能力', tag: '融资能力' },
  { index: '06', title: '业务建议', text: '机会等级、准入条件与尽调清单', tag: '行动路径' },
]

const activeSignal = computed(() => signals.find((signal) => signal.id === activeSignalId.value))
const selectedCompany = computed(() => companies.value.find((company) => company.id === selectedCompanyId.value) || companies.value[0] || {
  id: '', name: '正在读取数据库', industry: '', opportunity: 'UNKNOWN', profileType: 'POWER_USER', storage: '—', npv: 0,
  dscr: 0, maxDebt: '—', readiness: '—', risk: '—', product: '—', action: '—', note: '—',
})
const detailCompanyId = computed(() => currentPath.value.match(/^\/enterprise\/([^/]+)$/)?.[1] || '')
const dataRoute = computed(() => currentPath.value.match(/^\/data\/([^/]+)$/)?.[1] || '')
const bankWorkbench = computed(() => currentPath.value === '/bank-workbench')
const aiAssistant = computed(() => currentPath.value === '/ai-assistant')
const projectAnalysis = computed(() => currentPath.value === '/project-analysis')
const loadPriceSeries = computed(() => (loadPriceWindow.value.series || []).map((row) => ({
  ...row,
  hour: Number(row.hourOfDay),
  loadMw: Number(row.avgLoadKw || 0) / 1000,
  price: Number(row.avgPriceYuanKwh || 0),
})))
const loadAxisMax = computed(() => {
  const maximum = Math.max(...loadPriceSeries.value.map((row) => row.loadMw), 1)
  return Math.ceil(maximum / 50) * 50
})
const priceAxisMax = computed(() => {
  const maximum = Math.max(...loadPriceSeries.value.map((row) => row.price), 0.1)
  return Math.ceil(maximum * 10) / 10
})
const loadPriceChart = computed(() => loadPriceSeries.value.map((row, index, rows) => ({
  ...row,
  loadPercent: row.loadMw / loadAxisMax.value * 100,
  pricePercent: row.price / priceAxisMax.value * 100,
  nextPricePercent: rows[index + 1]?.price / priceAxisMax.value * 100,
})))
const peakLoadPoint = computed(() => loadPriceSeries.value.reduce((peak, row) => row.loadMw > (peak?.loadMw || 0) ? row : peak, null))
const averageLoadMw = computed(() => loadPriceSeries.value.length
  ? loadPriceSeries.value.reduce((sum, row) => sum + row.loadMw, 0) / loadPriceSeries.value.length : 0)
const priceSpread = computed(() => {
  const prices = loadPriceSeries.value.map((row) => row.price)
  return prices.length ? Math.max(...prices) - Math.min(...prices) : 0
})
const periodBlocks = computed(() => {
  const blocks = []
  loadPriceSeries.value.forEach((row) => {
    const last = blocks[blocks.length - 1]
    if (last?.period === row.timePeriod && last.end === row.hour) last.end = row.hour + 1
    else blocks.push({ period: row.timePeriod, start: row.hour, end: row.hour + 1 })
  })
  return blocks
})
const highPriceWindows = computed(() => formatHourRanges(loadPriceSeries.value
  .filter((row) => ['PEAK', 'CRITICAL', 'CRITICAL_PEAK'].includes(row.timePeriod)).map((row) => row.hour)))

function normalizeLegacyPath() {
  if (window.location.pathname === '/login') {
    window.history.replaceState({}, '', '/')
  }
}

function syncPath() {
  normalizeLegacyPath()
  currentPath.value = window.location.pathname
}

function decimal(value, digits = 2) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed.toFixed(digits) : '—'
}

function mapHomeCompany(row) {
  const generator = row.powerChainRole === 'GENERATOR'
  return {
    id: row.companyId,
    name: row.companyName,
    industry: row.industryName || '行业待补充',
    profileType: generator ? 'GENERATOR' : 'POWER_USER',
    storagePower: Number(row.storagePowerMw || 0),
    storageCapacity: Number(row.storageCapacityMwh || 0),
    storage: `${decimal(row.storagePowerMw)} MW / ${decimal(row.storageCapacityMwh)} MWh`,
    duration: Number(row.storageDurationHour || 0),
    npv: Number(row.npvWanyuan || 0),
    dscr: Number(row.baseMinDscr || 0),
    maxDebt: row.maxDebtRatio == null ? '—' : `${Math.round(Number(row.maxDebtRatio) * 100)}%`,
    opportunity: row.opportunityLevel || 'UNKNOWN',
    readiness: row.readinessLevel || '—',
    risk: row.riskLevel || '—',
    priority: row.businessPriority || '—',
    product: row.recommendedProduct || '待进一步分析',
    action: row.recommendationText || '暂无下一步建议。',
    note: row.riskSummary || `${row.featureAnalysisYear || 2025}年研究口径。`,
    installedCapacity: `${decimal(row.installedCapacity10kKw)} 万千瓦`,
    grossGeneration: `${decimal(row.grossGeneration100mKwh)} 亿千瓦时`,
    onGridElectricity: `${decimal(row.onGridElectricity100mKwh)} 亿千瓦时`,
    marketTradeRatio: `${decimal(row.marketTradeRatioPct)}%`,
    averageOnGridPrice: `${decimal(row.averageOnGridPrice)} 元/kWh`,
    renewableCapacityRatio: `${decimal(row.renewableCapacityRatioPct)}%`,
    debtRatio: row.latestDebtRatio == null ? '—' : `${decimal(Number(row.latestDebtRatio) * 100)}%`,
  }
}

async function loadHomeSummary() {
  try {
    const data = await fetchHomeSummary()
    companies.value = (data.companies || []).map(mapHomeCompany)
    activeRun.value = data.activeRun || {}
    const counts = data.coverage || {}
    analysisCoverage.value = counts
    const values = [counts.regionalPowerStatistics, counts.electricityTariff, counts.powerMarketTrade, counts.policyRule]
    coverageData.value = coverageData.value.map((item, index) => ({ ...item, value: new Intl.NumberFormat('zh-CN').format(values[index] ?? 0) }))
    if (!companies.value.some((company) => company.id === selectedCompanyId.value) && companies.value[0]) selectedCompanyId.value = companies.value[0].id
  } catch (exception) { homeError.value = exception.message }
}

async function loadHeroWindow() {
  loadPriceLoading.value = true
  loadPriceError.value = ''
  try { loadPriceWindow.value = await fetchLoadPriceWindow('C000020', 2025) }
  catch (exception) { loadPriceError.value = exception.message }
  finally { loadPriceLoading.value = false }
}

function formatHourRanges(hours) {
  if (!hours.length) return '—'
  const ranges = []
  let start = hours[0], end = hours[0]
  hours.slice(1).forEach((hour) => {
    if (hour === end + 1) end = hour
    else { ranges.push([start, end + 1]); start = hour; end = hour }
  })
  ranges.push([start, end + 1])
  return ranges.map(([from, to]) => `${String(from).padStart(2, '0')}:00–${String(to).padStart(2, '0')}:00`).join(' / ')
}

onMounted(() => {
  normalizeLegacyPath()
  currentPath.value = window.location.pathname
  window.addEventListener('popstate', syncPath)
  loadHomeSummary()
  loadHeroWindow()
})
onBeforeUnmount(() => window.removeEventListener('popstate', syncPath))

function scrollToSection(target) {
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  menuOpen.value = false
}

function selectCompany(id) {
  selectedCompanyId.value = id
  window.setTimeout(() => {
    document.getElementById('company-detail')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, 0)
}

function formatWanyuan(value) {
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

function openDataView(entry) {
  pendingDataView.value = null
  window.history.pushState({ dataRoute: entry.route }, '', `/data/${entry.route}`)
  currentPath.value = window.location.pathname
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function closeDataViewHint() {
  pendingDataView.value = null
  if (window.location.hash.startsWith('#data/')) {
    window.history.replaceState({}, '', `${window.location.pathname}${window.location.search}`)
  }
}

function navigateToEnterprise(companyId) {
  window.history.pushState({ companyId }, '', `/enterprise/${companyId}`)
  currentPath.value = window.location.pathname
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openBankWorkbench() {
  window.history.pushState({}, '', '/bank-workbench')
  currentPath.value = window.location.pathname
  document.title = '银行客户经理工作台 · 电力能源金融'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openAiAssistant() {
  window.history.pushState({}, '', '/ai-assistant')
  currentPath.value = window.location.pathname
  document.title = 'AI 智能问答 · 电力能源金融'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function openProjectAnalysis() {
  window.history.pushState({}, '', '/project-analysis')
  currentPath.value = window.location.pathname
  document.title = '项目初步尽调 · 电力能源金融'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function returnHome() {
  window.history.pushState({}, '', '/')
  currentPath.value = window.location.pathname
  document.title = '电力能源金融机会分析平台'
  window.scrollTo({ top: 0, behavior: 'smooth' })
}
</script>

<template>
  <div class="app-shell">
    <DataCatalogView v-if="dataRoute" :dataset="dataRoute" @back="returnHome" />

    <BankWorkbenchView
      v-else-if="bankWorkbench"
      :compute-site-url="computeSiteUrl"
      :power-site-url="powerSiteUrl"
      @back="returnHome"
      @open-enterprise="navigateToEnterprise"
    />

    <AiAssistantView
      v-else-if="aiAssistant"
      @back="returnHome"
      @open-project-analysis="openProjectAnalysis"
    />

    <ProjectAnalysisView v-else-if="projectAnalysis" @back="returnHome" />

    <EnterpriseDataView
      v-else-if="detailCompanyId"
      :company-id="detailCompanyId"
      @back="returnHome"
      @select-company="navigateToEnterprise"
    />

    <template v-else>
      <header class="site-header">
      <div class="topbar">
        <button class="brand" type="button" aria-label="返回首页" @click="scrollToSection('home')">
          <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i></span>
          <span>
            <strong>电力能源金融</strong>
            <small>机会分析平台</small>
          </span>
        </button>

        <button class="menu-toggle" type="button" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen">
          <span></span><span></span>
          <em class="sr-only">切换导航</em>
        </button>

        <nav :class="['main-nav', { 'is-open': menuOpen }]" aria-label="主导航">
          <button v-for="item in navigation" :key="item.target" type="button" @click="scrollToSection(item.target)">
            {{ item.label }}
          </button>
        </nav>

        <div class="site-switcher" aria-label="研究站点切换">
          <a :href="bankWorkbenchUrl" title="进入银行客户经理工作台">工作台</a>
          <b>电力研究</b>
          <a :href="computeSiteUrl" title="进入算力能源研究网站">算力研究</a>
        </div>
      </div>
    </header>

    <main>
      <section id="home" class="hero section-shell">
        <div class="hero-copy">
          <p class="eyebrow light"><span></span> 面向银行业务的电力能源研究情景</p>
          <h1><span class="market-highlight">从电力市场变化，</span><br /><em>识别企业能源与融资机会。</em></h1>
          <p class="hero-summary">
            将区域市场、分时电价、企业负荷、储能工程约束、融资偿债与政策适用情况汇入同一条可追溯分析链路。
          </p>
          <div class="hero-actions">
            <button class="button primary" type="button" @click="scrollToSection('energy-mix')">查看能源与市场逻辑 <span>↓</span></button>
            <button class="button ghost" type="button" @click="scrollToSection('enterprises')">浏览企业画像</button>
            <button class="button ghost" type="button" @click="openBankWorkbench">进入银行工作台 →</button>
            <button class="button ghost" type="button" @click="openAiAssistant">AI 智能问答 →</button>
          </div>
          <p class="disclaimer"><span>研究边界</span> 当前展示为公开资料与研究情景下的模型结果，不构成授信承诺。</p>
        </div>

        <div class="hero-dashboard" aria-label="分析快照概览">
          <div class="dashboard-topline">
            <p>当前分析覆盖</p>
            <span>PUBLIC + SIMULATED</span>
          </div>
          <div class="dashboard-grid">
            <article class="hero-stat stat-main">
              <span>重点企业</span>
              <strong>{{ analysisCoverage.focusCompany ?? companies.length }}</strong>
              <p>{{ activeRun.analysisYear || '—' }}年结果快照 · 数据库实时统计</p>
            </article>
            <article class="hero-stat">
              <span>时序样本</span>
              <strong>{{ formatWanyuan(Number(analysisCoverage.loadHour || 0) + Number(analysisCoverage.generationHour || 0)) }}<small>h</small></strong>
              <p>{{ analysisCoverage.completeLoadCompany || 0 }} 家完整负荷 · {{ analysisCoverage.generationHour ? 1 : 0 }} 家发电情景</p>
            </article>
            <article class="hero-stat">
              <span>政策依据</span>
              <strong>{{ analysisCoverage.policyDocument || 0 }}<small>份</small></strong>
              <p>{{ analysisCoverage.policyRule || 0 }} 条规则 · {{ analysisCoverage.publicEnergyMetric || 0 }} 项公开能源指标</p>
            </article>
          </div>
          <div class="load-visual">
            <div class="load-window-heading">
              <div><span>企业负荷 × 分时电价</span><b>{{ loadPriceWindow.companyName || '深圳市地铁集团' }}</b></div>
              <em>2025 年·日内小时均值</em>
            </div>

            <div v-if="loadPriceLoading" class="load-window-state">正在读取 8760 小时数据…</div>
            <div v-else-if="loadPriceError" class="load-window-state error">数据暂时无法读取：{{ loadPriceError }}</div>
            <template v-else>
              <div class="load-window-kpis">
                <div><span>平均负荷</span><strong>{{ averageLoadMw.toFixed(1) }} <small>MW</small></strong></div>
                <div><span>日内峰值</span><strong>{{ peakLoadPoint?.loadMw.toFixed(1) }} <small>MW @ {{ String(peakLoadPoint?.hour).padStart(2, '0') }}:00</small></strong></div>
                <div><span>峰谷价差</span><strong>{{ priceSpread.toFixed(3) }} <small>元/kWh</small></strong></div>
              </div>

              <div class="load-chart-labels"><span>左轴 · 负荷 MW</span><span>右轴 · 电价 元/kWh</span></div>
              <div class="load-chart-shell">
                <div class="load-y-axis left"><span>{{ loadAxisMax }}</span><span>{{ loadAxisMax / 2 }}</span><span>0</span></div>
                <div class="load-chart-plot">
                  <span class="load-gridline top"></span><span class="load-gridline middle"></span><span class="load-gridline bottom"></span>
                  <span v-for="block in periodBlocks" :key="`${block.period}-${block.start}`"
                    :class="['tariff-period', block.period.toLowerCase()]"
                    :style="{ left: `${block.start / 24 * 100}%`, width: `${(block.end - block.start) / 24 * 100}%` }"></span>
                  <div class="load-bars" aria-label="柱状图表示各小时平均负荷">
                    <span v-for="row in loadPriceChart" :key="row.hour"
                      :title="`${String(row.hour).padStart(2, '0')}:00·负荷 ${row.loadMw.toFixed(1)} MW`">
                      <i :style="{ height: `${row.loadPercent}%` }"></i>
                    </span>
                  </div>
                  <div class="price-curve" aria-label="青色阶梯线表示分时电价">
                    <template v-for="(row, index) in loadPriceChart" :key="`price-${row.hour}`">
                      <i class="price-horizontal" :style="{ left: `${index / 24 * 100}%`, width: `${100 / 24}%`, bottom: `${row.pricePercent}%` }"
                        :title="`${String(row.hour).padStart(2, '0')}:00·电价 ${row.price.toFixed(3)} 元/kWh·${row.timePeriod}`"></i>
                      <i v-if="index < loadPriceChart.length - 1" class="price-vertical"
                        :style="{ left: `${(index + 1) / 24 * 100}%`, bottom: `${Math.min(row.pricePercent, row.nextPricePercent)}%`, height: `${Math.abs(row.nextPricePercent - row.pricePercent)}%` }"></i>
                    </template>
                  </div>
                </div>
                <div class="load-y-axis right"><span>{{ priceAxisMax.toFixed(1) }}</span><span>{{ (priceAxisMax / 2).toFixed(1) }}</span><span>0</span></div>
              </div>
              <div class="load-x-axis"><span>00:00</span><span>04:00</span><span>08:00</span><span>12:00</span><span>16:00</span><span>20:00</span><span>24:00</span></div>

              <div class="load-chart-explanation">
                <div class="load-chart-legend"><span><i class="load-legend-bar"></i>负荷</span><span><i class="load-legend-line"></i>电价</span><span><i class="load-legend-valley"></i>谷时段</span><span><i class="load-legend-peak"></i>峰时段</span></div>
                <p><b>核心信号</b> 高价时段 {{ highPriceWindows }}；若负荷同时处于高位，则构成储能削峰和峰谷套利的主要现金流窗口。</p>
              </div>
              <p class="load-chart-boundary"><b>{{ loadPriceChart[0]?.dataType || 'SIMULATED' }}</b> · {{ loadPriceWindow.sampleCount?.toLocaleString('zh-CN') }} 小时聚合。{{ loadPriceWindow.boundary }}</p>
            </template>
          </div>
        </div>
      </section>

      <PowerSourceStructure />

      <section id="market" class="market-section section-shell">
        <div class="section-heading">
          <div>
            <p class="eyebrow"><span></span> 第二层：外部市场环境</p>
            <h2>电力市场的变化，<br />为什么会成为银行业务线索？</h2>
          </div>
          <p class="section-intro">不是“有负荷就做储能”。先识别成本、需量和政策三类外部信号，才能判断企业用能问题是否具有可转化的金融价值。</p>
        </div>

        <div class="signal-layout">
          <div class="signal-list" role="tablist" aria-label="市场信号">
            <button
              v-for="signal in signals"
              :key="signal.id"
              :class="['signal-card', { active: activeSignalId === signal.id }, signal.accent]"
              type="button"
              role="tab"
              :aria-selected="activeSignalId === signal.id"
              @click="activeSignalId = signal.id"
            >
              <span class="signal-index">{{ signal.index }}</span>
              <span class="signal-card-copy"><b>{{ signal.title }}</b><small>{{ signal.description }}</small></span>
              <span class="arrow">↗</span>
            </button>
          </div>

          <article class="signal-detail" :class="activeSignal.accent" role="tabpanel">
            <div class="detail-label">{{ activeSignal.shortTitle }}</div>
            <h3 class="question-nowrap">{{ activeSignal.question }}</h3>
            <div v-if="activeSignal.measureDetails" class="measure-insights">
              <article v-for="measure in activeSignal.measureDetails" :key="measure.title"><strong>{{ measure.title }}</strong><p>{{ measure.text }}</p></article>
            </div>
            <div v-else class="signal-measures">
              <span v-for="measure in activeSignal.measures" :key="measure">{{ measure }}</span>
            </div>
            <div class="signal-mini-chart" aria-hidden="true">
              <div class="chart-ring"><span>市场<br />数据</span></div>
              <div class="chart-path"><i></i><i></i><i></i></div>
              <div class="chart-target"><span>企业<br />评估</span></div>
            </div>
            <p class="detail-note"><b>使用边界：</b>{{ activeSignal.note }}</p>
          </article>
        </div>

        <div class="coverage-strip">
          <button v-for="entry in coverageData" :key="entry.route" class="coverage-data-link" type="button" @click="openDataView(entry)">
            <b>{{ entry.value }}</b><span>{{ entry.label }}</span><em>↗</em>
          </button>
          <p>数据范围为当前课题已整理并入库的研究数据，不代表完整市场数据全集。</p>
        </div>
      </section>

      <section id="method" class="method-section">
        <div class="section-shell">
          <div class="section-heading compact">
            <div>
              <p class="eyebrow light"><span></span> 第三层：统一评估方法</p>
              <h2>把“电力数据”变成<br />可解释的企业评估。</h2>
            </div>
            <p class="section-intro">每一步都保存来源、版本和假设。市场信号只能提供判断的起点，最终建议必须经过项目仿真、偿债能力和政策条件的共同约束。</p>
          </div>

          <div class="pipeline" aria-label="市场到业务建议的评估流程">
            <article v-for="(step, index) in pipeline" :key="step.index" class="pipeline-step">
              <span class="pipeline-number">{{ step.index }}</span>
              <div><small>{{ step.tag }}</small><h3>{{ step.title }}</h3><p>{{ step.text }}</p></div>
              <span v-if="index < pipeline.length - 1" class="pipeline-line" aria-hidden="true"></span>
            </article>
          </div>

          <div class="method-footnotes">
            <p><span>数据</span> 原始数据、公开锚点、模拟数据分层保存，避免把不同可信度的数据混为一谈。</p>
            <p><span>模型</span> 储能 V2.0 采用功率 × 时长搜索、工程约束与非线性成本；融资 V2.0 以 DSCR 约束债务承受能力。</p>
          </div>
        </div>
      </section>

      <section id="enterprises" class="enterprise-section section-shell">
        <div class="section-heading">
          <div>
            <p class="eyebrow"><span></span> 第四层：企业能源画像</p>
            <h2>从统一方法，得到<br />不同的机会与尽调重点。</h2>
          </div>
          <p class="section-intro">以下六家企业及快照结果由 Java API 实时读取数据库。点击企业可查看当前推荐配置、融资边界与下一步尽调动作。</p>
        </div>

        <p v-if="homeError" class="enterprise-api-warning">首页数据库读取失败：{{ homeError }}</p>
        <div class="enterprise-layout">
          <div class="company-grid">
            <button
              v-for="company in companies"
              :key="company.id"
              :class="['company-card', { selected: selectedCompanyId === company.id }]"
              type="button"
              @click="selectCompany(company.id)"
            >
              <div class="company-card-head"><span class="company-id">{{ company.id }}</span><span :class="['opportunity', company.opportunity.toLowerCase()]">{{ company.opportunity }}</span></div>
              <h3>{{ company.name }}</h3>
              <p>{{ company.industry }}</p>
              <div v-if="company.profileType === 'GENERATOR'" class="company-metrics">
                <span><small>控股装机</small><b>{{ company.installedCapacity }}</b></span>
                <span><small>上网电量</small><b>{{ company.onGridElectricity }}</b></span>
                <span><small>市场化占比</small><b>{{ company.marketTradeRatio }}</b></span>
              </div>
              <div v-else class="company-metrics">
                <span><small>推荐储能</small><b>{{ company.storage }}</b></span>
                <span><small>NPV</small><b>{{ formatWanyuan(company.npv) }} 万元</b></span>
                <span><small>最低 DSCR</small><b>{{ company.dscr.toFixed(3) }}</b></span>
              </div>
            </button>
          </div>

          <aside id="company-detail" class="company-detail" aria-live="polite">
            <div class="detail-header">
              <div><p>当前选中企业</p><h3>{{ selectedCompany.name }}</h3></div>
              <span :class="['opportunity', selectedCompany.opportunity.toLowerCase()]">{{ selectedCompany.opportunity }}</span>
            </div>
            <dl v-if="selectedCompany.profileType === 'GENERATOR'">
              <div><dt>2025年发电量</dt><dd>{{ selectedCompany.grossGeneration }}</dd></div>
              <div><dt>2025年上网电量</dt><dd>{{ selectedCompany.onGridElectricity }}</dd></div>
              <div><dt>平均上网电价</dt><dd>{{ selectedCompany.averageOnGridPrice }}</dd></div>
              <div><dt>可再生能源装机占比</dt><dd>{{ selectedCompany.renewableCapacityRatio }}</dd></div>
              <div><dt>资产负债率</dt><dd>{{ selectedCompany.debtRatio }}</dd></div>
            </dl>
            <dl v-else>
              <div><dt>储能研究配置</dt><dd>{{ selectedCompany.storage }} / 4h</dd></div>
              <div><dt>基准 NPV</dt><dd>{{ formatWanyuan(selectedCompany.npv) }} 万元</dd></div>
              <div><dt>最低 DSCR</dt><dd>{{ selectedCompany.dscr.toFixed(3) }}</dd></div>
              <div><dt>最大债务比例</dt><dd>{{ selectedCompany.maxDebt }}</dd></div>
              <div><dt>准备度 / 风险</dt><dd>{{ selectedCompany.readiness }} / {{ selectedCompany.risk }}</dd></div>
            </dl>
            <div class="recommendation"><span>建议产品</span><strong>{{ selectedCompany.product }}</strong><p>{{ selectedCompany.action }}</p></div>
            <p class="company-note"><span>注</span>{{ selectedCompany.note }}</p>
            <button class="enterprise-data-button" type="button" @click="navigateToEnterprise(selectedCompany.id)">
              {{ selectedCompany.profileType === 'GENERATOR' ? '查看企业全部公开数据' : '查看企业所有用电数据' }} <span>→</span>
            </button>
          </aside>
        </div>
      </section>

      <section id="trace" class="trace-section">
        <div class="section-shell trace-content">
          <div>
            <p class="eyebrow light"><span></span> 第五层：结果可溯源</p>
            <h2>每一次分析运行，<br />都留下可比较的结果快照。</h2>
            <p>首页读取的不是过程中的每小时调度数据，而是一次完整模型运行后形成的业务结果汇总。模型或参数升级时，新结果以新快照保存，不覆盖历史判断。</p>
          </div>
          <div class="trace-card">
            <div class="trace-card-top"><span class="status-dot"></span><b>RUN #{{ activeRun.runId || '—' }} · 2025 REBASE</b><small>{{ activeRun.analysisYear || '—' }}</small></div>
            <div class="trace-versions"><span>Energy<br /><b>{{ activeRun.modelVersion || '—' }}</b></span><span>Storage<br /><b>{{ activeRun.storageVersion || '—' }}</b></span><span>Finance<br /><b>{{ activeRun.financeVersion || '—' }}</b></span></div>
            <div class="trace-result"><span>当前重点范围</span><strong>{{ companies.length }} 家企业 · 数据库实时读取</strong><p>PUBLIC年度锚点 / SIMULATED月小时形状</p></div>
          </div>
        </div>
      </section>

      <section class="boundary-section section-shell">
        <div class="boundary-icon">!</div>
        <div><p class="eyebrow"><span></span> 领导展示时的必要说明</p><h2>模型给出的是可验证的研究线索，<br />不是替代尽调的结论。</h2></div>
        <p>真实电价、场地条件、并网与变压器容量、项目主体、授信资质及政策资格，仍需在项目尽调阶段逐项核验。</p>
      </section>
    </main>

    <transition name="toast">
      <aside v-if="pendingDataView" class="data-toast" aria-live="polite">
        <button type="button" aria-label="关闭提示" @click="closeDataViewHint">×</button>
        <p>已预留数据页入口</p>
        <strong>{{ pendingDataView.page }}</strong>
        <span>目标路由：#/data/{{ pendingDataView.route }}</span>
      </aside>
    </transition>

      <footer>
        <span>SPDB POWER FINANCE · RESEARCH DEMO</span>
        <span>Vue 3 · Java API · MySQL</span>
      </footer>
    </template>

    <a
      v-if="!aiAssistant"
      class="ai-analysis-fab"
      href="/ai-assistant"
      aria-label="进入 AI 分析"
    >
      <span class="ai-analysis-fab-mark" aria-hidden="true">✦</span>
      <span class="ai-analysis-fab-tooltip" role="tooltip">进入 AI 分析</span>
    </a>
  </div>
</template>
