<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  fetchBankRecommendations,
  fetchComputeSensitivity,
  fetchComputeSummary,
  fetchComputePolicyOverview,
  fetchComputeFacilityOperations,
  fetchComputePowerSynergy,
  fetchCreditPolicies,
  fetchCreditPolicyCurve,
  fetchFinanceOpportunities,
  fetchFinanceOpportunity,
} from './services/computeApi'
import './due-diligence.css'
import './power-synergy.css'

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

function normalizeAppBase(value) {
  const normalized = (value || '/').trim().replace(/^\/+|\/+$/g, '')
  return normalized ? `/${normalized}` : ''
}

const appBase = normalizeAppBase(import.meta.env.VITE_APP_BASE)
function currentAppPath() {
  const path = window.location.pathname
  if (appBase && (path === appBase || path.startsWith(`${appBase}/`))) {
    return path.slice(appBase.length) || '/'
  }
  return path || '/'
}
function appUrl(path) {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return `${appBase}${normalized}` || '/'
}

const powerSiteUrl = researchSiteUrl(import.meta.env.VITE_POWER_SITE_URL, 5173)
const bankWorkbenchUrl = `${powerSiteUrl.replace(/\/$/, '')}/bank-workbench`
const menuOpen = ref(false)
const currentPath = ref(currentAppPath())
const selectedFacilityCode = ref('SZCF016')
const selectedProductId = ref('BMGNH100-8XLARGE2048')
const formulaOpen = ref(false)
const computeSummary = ref(null)
const creditPolicies = ref([])
const bankRecommendations = ref([])
const sensitivityRows = ref([])
const financingCurve = ref([])
const selectedScenarioVersion = ref('COMPUTE_BASE_V1')
const selectedPolicyCode = ref('CREDIT_BASE_V1')
const selectedRecommendationId = ref(null)
const financeLoading = ref(true)
const financeError = ref('')
const policyOverview = ref(null)
const policyError = ref('')
const financeOpportunities = ref([])
const opportunityOverview = ref(null)
const selectedOpportunityCode = ref(null)
const selectedOpportunityDetail = ref(null)
const opportunityLoading = ref(true)
const opportunityError = ref('')
const facilityOperations = ref(null)
const facilityOperationsLoading = ref(false)
const facilityOperationsError = ref('')
const selectedPhase3ScenarioCode = ref('BWX_PHASE3_BASE_V1')
const powerSynergy = ref(null)
const powerSynergyLoading = ref(false)
const powerSynergyError = ref('')
const selectedPowerSynergyCode = ref('BWX_PHASE3_TOU_GRID_V1')

const navigation = [
  { label: '算力格局', target: 'landscape' },
  { label: '平台市场', target: 'market' },
  { label: '设施画像', target: 'facilities', page: 'facilities' },
  { label: '算电协同', target: 'collaboration', page: 'synergy' },
  { label: '政策机会', target: 'policy', page: 'policies' },
  { label: '业务清单', target: 'opportunities', page: 'opportunities' },
  { label: '融资路径', target: 'finance', page: 'finance' },
  { label: '模型溯源', target: 'trace' },
]

const coverage = computed(() => {
  const values = computeSummary.value?.coverage || {}
  return [
    { value: values.facilityCount ?? 15, label: '算力设施', note: '物理设施与异地集群分开' },
    { value: values.platformCount ?? 5, label: '服务与调度平台', note: '平台容量不等于自有装机' },
    { value: values.productCount ?? 51, label: '公开算力商品', note: '卡数代表配置而非库存' },
    { value: values.priceCount ?? 189, label: '公开价格记录', note: '参考价、配置价与附加项分行' },
  ]
})

const marketSignals = [
  {
    index: '01', tag: '供给结构', title: '算力从“单体机房”走向“跨域调度”',
    text: '本地设施、深汕节点和异地集群共同形成可调用供给，但物理容量、平台纳管容量和公开商品不能简单相加。',
    impacts: ['建设融资', '设备更新', '跨域调度'], tone: 'blue',
  },
  {
    index: '02', tag: '价格信号', title: '同一卡型在不同配置下价格差异显著',
    text: '公开市场已经能够观察GPU型号、地域和计费周期，但列表价与详情价可能并不一致，授信前仍需合同级核验。',
    impacts: ['收入测算', '租赁定价', '现金流波动'], tone: 'teal',
  },
  {
    index: '03', tag: '能源约束', title: '电力成本决定绿色算力的持续竞争力',
    text: '设备功率、利用率、PUE、电价和绿电比例共同决定每GPU小时成本，也会影响项目利润、碳表现与偿债空间。',
    impacts: ['运营成本', '绿色认定', '偿债能力'], tone: 'amber',
  },
]

const products = [
  {
    id: 'BMGNH100-8XLARGE2048', name: 'H100 80GB SXM（八卡）', model: '8 × H100 80GB',
    region: '深圳二区-I1', listPrice: 77000, detailPrice: 85000, unit: '元/台·月',
    conflict: true, source: '大湾区一体化算力服务平台', type: 'GPU裸金属',
  },
  {
    id: 'GNH800-32XLARGE2048', name: 'H800 80GB SXM（八卡）', model: '8 × H800 80GB',
    region: '深圳一区-S1', listPrice: 85000, detailPrice: 75000, unit: '元/台·月',
    conflict: true, source: '大湾区一体化算力服务平台', type: 'GPU裸金属',
  },
  {
    id: 'rs-cpn-cscvv6pbivm9t74o17kg', name: '鹏城云脑Ⅱ Ascend910-1', model: '1 × Ascend 910',
    region: '鹏城实验室', listPrice: 2016, detailPrice: null, unit: '元/月',
    conflict: false, source: '深圳市智慧城市算力统筹调度平台', type: 'NPU算力',
  },
  {
    id: 'rs-cpn-csd01thbivm9t74o17m0', name: '昇腾910 × 2（小时）', model: '2 × Ascend 910',
    region: '鹏城实验室', listPrice: 5.6, detailPrice: null, unit: '元/小时',
    conflict: false, source: '深圳市智慧城市算力统筹调度平台', type: 'NPU算力',
  },
]

const facilities = [
  {
    code: 'SZCF007', name: '鹏城云脑Ⅱ', type: '国家级AI平台', location: '深圳', status: '运营中', grade: 'A',
    capacity: '1 EOPS', precision: 'FP16', secondaryCapacity: '2 EOPS / INT8',
    energy: '项目级PUE暂无可靠公开值', price: '已有3个公开商品',
    facts: ['4096颗昇腾910处理器', 'FP16与INT8容量分口径保存', '已发现公开月租与小时价'],
    gaps: ['设备实测功率', '年度利用率', '项目级PUE', '绿电比例'],
    fit: '适合作为“算力商品价格—设备利用—电力成本”样板，但能源端仍需情景参数。',
  },
  {
    code: 'SZCF004', name: '前海深港人工智能算力中心', type: '市场化智算中心', location: '前海', status: '运营中', grade: 'A',
    capacity: '500 PFLOPS', precision: 'FP16', secondaryCapacity: '一期口径',
    energy: 'PUE与绿电比例暂缺', price: '一期投资 4.66 亿元',
    facts: ['500P FP16已点亮', '一期投资边界明确', '市场化运营定位'],
    gaps: ['实际算力租赁收入', 'IT负载', 'PUE', '电费合同'],
    fit: '容量与投资额较清楚，可优先建立资本开支、出租率与回收期情景。',
  },
  {
    code: 'SZCF006', name: '龙华新型工业智算中心', type: '工业智算中心', location: '龙华', status: '运营中', grade: 'A',
    capacity: '1,000 PFLOPS', precision: '未披露', secondaryCapacity: '终期规划 10,000P',
    energy: 'GPU全液冷；整体液冷占比 > 50%', price: '投资额暂缺',
    facts: ['一期千P算力已点亮', '规划与当前容量分开', '99.999%持续供电设计'],
    gaps: ['实际PUE', '当前IT负载', '年用电量', '项目投资'],
    fit: '适合研究液冷、供电可靠性与工业客户算力需求之间的融资逻辑。',
  },
  {
    code: 'SZCF009', name: '深圳力合报业大数据中心', type: 'IDC数据中心', location: '龙华', status: '运营中', grade: 'B',
    capacity: '2,301 机柜', precision: '约5kW/柜', secondaryCapacity: 'IDC口径',
    energy: '全年PUE约 1.244', price: '合同额不等于总投资',
    facts: ['机柜与柜功率已披露', 'PUE具备项目级公开口径', '运营状态可确认'],
    gaps: ['实际平均上架率', '年用电量', '绿电比例', '总投资'],
    fit: '现阶段最适合建立“机柜—IT功率—PUE—电费”的能源成本样板。',
  },
  {
    code: 'SZCF013', name: '中国联通深汕云数据中心', type: '云数据中心', location: '深汕', status: '运营中', grade: 'A',
    capacity: '约1,000机柜', precision: '中心整体口径', secondaryCapacity: '约1.2万㎡',
    energy: '2019年中心年均PUE 1.31', price: '融资数据暂缺',
    facts: ['入选国家绿色数据中心', '机柜、面积与PUE可追溯', '深汕与深圳核心城区分区保存'],
    gaps: ['2号楼独立PUE', 'IT负载率', '绿电采购', '收入与投资'],
    fit: '适合构建绿色数据中心对标，但不能把中心汇总PUE解释为单楼数据。',
  },
  {
    code: 'SZCF016', name: '深圳百旺信智算中心', type: '绿色AIDC智算中心', location: '南山', status: '运营中', grade: 'A',
    capacity: '3,780柜（1栋+4栋）', precision: '2025年均上架 2,473柜', secondaryCapacity: '三期：1,760机柜 · 4kW/柜',
    energy: '2025年电量 8,019.62万kWh；三期PUE 1.228', price: '2025均价 5,346元/柜·月',
    facts: ['2025全年上架率65.42%、自建托管收入1.58亿元', '交易所披露三期年电量4,847.33万kWh与历史投资3.2亿元', '有公开固定资产贷款与深圳移动批发合同结构'],
    gaps: ['当前H800 SKU归属', '绿电合同与结算单', '三期单独收入与上架率', '实时客户合同与回款'],
    fit: '目前最完整的真实经营样本：可校准“上架率—分功率价格—电量—电费—毛利”，但全园区经营口径不能代替三期单独现金流；与CNIX H800商品仍仅为中等置信度候选关联。',
  },
]

const pipeline = [
  { index: '01', title: '算力设施', text: '识别物理设施、状态与容量口径', tag: '资产底座' },
  { index: '02', title: '商品市场', text: '采集卡型、地域、配置与公开价格', tag: '收入信号' },
  { index: '03', title: '能源效率', text: '设备功率 × 利用率 × PUE × 电价', tag: '成本核心' },
  { index: '04', title: '绿色能力', text: '绿电比例、碳强度与节能技术', tag: '政策属性' },
  { index: '05', title: '现金流', text: '收入、CAPEX、OPEX与敏感性', tag: '项目经济' },
  { index: '06', title: '银行机会', text: '融资需求、风险与尽调事项', tag: '业务行动' },
]

const scenarioOptions = [
  { version: 'COMPUTE_CONSERVATIVE_V1', label: '保守', note: '利用率35% · PUE 1.50' },
  { version: 'COMPUTE_BASE_V1', label: '基准', note: '利用率65% · PUE 1.35' },
  { version: 'COMPUTE_OPTIMISTIC_V1', label: '乐观', note: '利用率85% · PUE 1.25' },
]

const variableLabels = {
  UTILIZATION: '利用率',
  PUBLIC_PRICE: '公开价格',
  ELECTRICITY_PRICE: '电价',
  PUE: 'PUE',
  CAPEX: 'CAPEX',
}

const selectedFacility = computed(() => facilities.find((item) => item.code === selectedFacilityCode.value) || facilities[0])
const activeDetailPage = computed(() => {
  if (currentPath.value === '/due-diligence/baiwangxin-phase3') return 'due-diligence'
  if (currentPath.value === '/power-synergy/baiwangxin-phase3') return 'synergy'
  const match = currentPath.value.match(/^\/(facilities|policies|opportunities|finance)\/?$/)
  return match?.[1] || ''
})
const isHome = computed(() => !activeDetailPage.value)
const detailPageMeta = computed(() => ({
  facilities: { eyebrow: 'FACILITY DATA ROOM', title: '算力设施画像与经营证据', text: '完整保留设施口径、公开经营事实、价格与三期项目情景。' },
  policies: { eyebrow: 'POLICY DATA ROOM', title: '政策规则与适用性核验', text: '完整展示政策对象、适用条件、证据缺口及模型边界。' },
  opportunities: { eyebrow: 'BANK ACTION ROOM', title: '银行行动与尽调清单', text: '完整展示候选项目、主体线索、公开融资参照与待补材料。' },
  finance: { eyebrow: 'FINANCE MODEL ROOM', title: '融资情景与偿债能力', text: '完整展示经营情景、信贷规则、敏感性与债务容量曲线。' },
  'due-diligence': { eyebrow: 'PROJECT DUE DILIGENCE', title: '百旺信云数据中心三期 · 尽调状态', text: '仅区分已核验公开事实、口径不完整事实与待向项目方补取的材料。' },
  synergy: { eyebrow: 'POWER × COMPUTE', title: '百旺信三期 · 算电协同成本情景', text: '将深圳分时电价、区域电源结构、绿电采购与储能移峰显式映射到项目现金流代理。' },
}[activeDetailPage.value] || {}))
const facilityHighlights = computed(() => ['SZCF016', 'SZCF007', 'SZCF004', 'SZCF009']
  .map((code) => facilities.find((item) => item.code === code)).filter(Boolean))
const selectedProduct = computed(() => products.find((item) => item.id === selectedProductId.value) || products[0])
const priceDifference = computed(() => {
  if (!selectedProduct.value.detailPrice) return null
  return (selectedProduct.value.detailPrice - selectedProduct.value.listPrice) / selectedProduct.value.listPrice
})
const selectedRecommendation = computed(() => bankRecommendations.value.find(
  (item) => item.projectEconomicsResultId === selectedRecommendationId.value,
) || bankRecommendations.value[0] || null)
const selectedPolicy = computed(() => creditPolicies.value.find(
  (item) => item.policyCode === selectedPolicyCode.value,
) || null)
const scenarioComparison = computed(() => computeSummary.value?.scenarioComparison || [])
const policyCoverage = computed(() => policyOverview.value?.coverage || {})
const policyPrograms = computed(() => policyOverview.value?.programs || [])
const policyHighlights = computed(() => policyPrograms.value.slice(0, 4))
const selectedFacilityPolicy = computed(() => (
  policyOverview.value?.facilitySummary || []
).find((item) => item.facilityCode === selectedFacilityCode.value) || null)
const policyPlatformMatches = computed(() => (
  policyOverview.value?.platformProviders || []
).filter((item) => Number(item.matchedProviderCount) > 0))
const opportunityCoverage = computed(() => opportunityOverview.value?.coverage || {})
const opportunityHighlights = computed(() => financeOpportunities.value.slice(0, 4))
const selectedOpportunity = computed(() => selectedOpportunityDetail.value?.opportunity
  || financeOpportunities.value.find((item) => item.opportunityCode === selectedOpportunityCode.value)
  || financeOpportunities.value[0] || null)
const opportunityChecklist = computed(() => selectedOpportunityDetail.value?.checklist || [])
const opportunityCandidateMappings = computed(() => selectedOpportunityDetail.value?.candidateMappings || [])
const opportunityReferenceCases = computed(() => selectedOpportunityDetail.value?.referenceCases || [])
const selectedFacilityOperations = computed(() => (
  selectedFacilityCode.value === 'SZCF016' ? facilityOperations.value : null
))
const baiwangAnnualOperations = computed(() => selectedFacilityOperations.value?.annualOperations || [])
const baiwangLatestOperation = computed(() => baiwangAnnualOperations.value.find(
  (item) => Number(item.factYear) === 2025 && item.factPeriod === 'ANNUAL',
) || baiwangAnnualOperations.value.at(-1) || null)
const baiwangFirstOperation = computed(() => baiwangAnnualOperations.value.find(
  (item) => Number(item.factYear) === 2023 && item.factPeriod === 'ANNUAL',
) || baiwangAnnualOperations.value[0] || null)
const baiwangOperatingInsight = computed(() => {
  const latest = baiwangLatestOperation.value
  const first = baiwangFirstOperation.value
  if (!latest || !first) return null
  return {
    occupancyPoints: (Number(latest.rackUtilizationRatio) - Number(first.rackUtilizationRatio)) * 100,
    revenueGrowth: Number(latest.hostingRevenueWanyuan) / Number(first.hostingRevenueWanyuan) - 1,
    grossMarginPoints: (Number(latest.hostingGrossMargin) - Number(first.hostingGrossMargin)) * 100,
    priceChange: Number(latest.averageRackPriceYuanMonth) / Number(first.averageRackPriceYuanMonth) - 1,
    oneFenElectricitySensitivityYuan: Number(latest.electricityConsumptionKwh) * 0.01,
    oneJiaoElectricitySensitivityYuan: Number(latest.electricityConsumptionKwh) * 0.10,
  }
})
const baiwangBuildingUtilization = computed(() => selectedFacilityOperations.value?.buildingUtilization || [])
const baiwangRackPriceTiers = computed(() => selectedFacilityOperations.value?.rackPriceTiers || [])
const baiwangLatestRackPriceTiers = computed(() => baiwangRackPriceTiers.value.filter(
  (item) => Number(item.factYear) === 2025 && item.factPeriod === 'H1',
))
const baiwangCustomerContracts = computed(() => selectedFacilityOperations.value?.customerContracts || [])
const baiwangPhase3DueDiligence = computed(() => selectedFacilityOperations.value?.phase3DueDiligence || [])
const baiwangDueDiligenceCounts = computed(() => baiwangPhase3DueDiligence.value.reduce((counts, item) => {
  counts[item.evidenceStatus] = (counts[item.evidenceStatus] || 0) + 1
  return counts
}, { VERIFIED: 0, PARTIAL: 0, PENDING: 0 }))
const baiwangPhase3CashflowScenarios = computed(() => selectedFacilityOperations.value?.phase3CashflowScenarios || [])
const selectedBaiwangPhase3Scenario = computed(() => (
  baiwangPhase3CashflowScenarios.value.find((item) => item.scenarioCode === selectedPhase3ScenarioCode.value)
  || baiwangPhase3CashflowScenarios.value.find((item) => item.scenarioCode === 'BWX_PHASE3_BASE_V1')
  || baiwangPhase3CashflowScenarios.value[0]
  || null
))
const selectedBaiwangPhase3Years = computed(() => (
  (selectedFacilityOperations.value?.phase3CashflowYears || []).filter(
    (item) => item.scenarioCode === selectedBaiwangPhase3Scenario.value?.scenarioCode,
  )
))
const powerSynergyScenarios = computed(() => powerSynergy.value?.scenarios || [])
const selectedPowerSynergy = computed(() => (
  powerSynergyScenarios.value.find((item) => item.scenarioCode === selectedPowerSynergyCode.value)
  || powerSynergyScenarios.value.find((item) => item.scenarioCode === 'BWX_PHASE3_TOU_GREEN_STORAGE2_V1')
  || powerSynergyScenarios.value[0]
  || null
))
const selectedPowerSynergyTariffs = computed(() => (
  (powerSynergy.value?.tariffSegments || []).filter(
    (item) => item.scenarioCode === selectedPowerSynergy.value?.scenarioCode,
  )
))
const homePowerSynergy = computed(() => powerSynergyScenarios.value.find(
  (item) => item.scenarioCode === 'BWX_PHASE3_TOU_GREEN_STORAGE2_V1',
) || powerSynergyScenarios.value[0] || null)
const curveChart = computed(() => {
  const rows = financingCurve.value.filter((item) => Number.isFinite(Number(item.minDscr)))
  const threshold = Number(selectedPolicy.value?.minDscr || 1.3)
  // Very low debt ratios can produce three-digit DSCR values. Capping the
  // display scale keeps the policy threshold and feasible boundary readable.
  const observedMax = Math.max(...rows.map((item) => Number(item.minDscr)), 1.5)
  const maxValue = Math.max(threshold * 1.6, Math.min(observedMax, 4))
  const left = 42; const right = 700; const top = 18; const bottom = 180
  const x = (ratio) => left + Number(ratio) * (right - left)
  const y = (value) => bottom - Math.min(Number(value), maxValue) / maxValue * (bottom - top)
  return {
    points: rows.map((item) => `${x(item.debtRatio).toFixed(1)},${y(item.minDscr).toFixed(1)}`).join(' '),
    thresholdY: y(threshold),
    recommendationX: selectedRecommendation.value?.recommendedDebtRatio == null
      ? null : x(selectedRecommendation.value.recommendedDebtRatio),
    maxValue,
  }
})

function scenarioStat(version) {
  return scenarioComparison.value.find((item) => item.scenarioVersion === version) || {}
}

function formatPrice(value) {
  if (value == null) return '—'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
}

function formatWan(value) {
  if (value == null) return '—'
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value) / 10000)} 万元`
}

function formatWanyuan(value) {
  if (value == null) return '—'
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value))} 万元`
}

function formatPercent(value, digits = 0) {
  if (value == null) return '—'
  return `${(Number(value) * 100).toFixed(digits)}%`
}

function formatRatio(value, digits = 2) {
  if (value == null) return '—'
  return Number(value).toFixed(digits)
}

function sensitivityWidth(value) {
  return `${Math.min(100, Math.max(4, Math.abs(Number(value || 0)) * 100))}%`
}

function recommendationStatus(value) {
  if (value === 'PROCEED_DUE_DILIGENCE') return '建议进入尽调'
  if (value === 'NOT_RECOMMENDED_NEGATIVE_NPV') return 'NPV未通过'
  if (value === 'NOT_RECOMMENDED_DSCR') return 'DSCR未通过'
  return value || '待计算'
}

function policyStatus(value) {
  const labels = {
    EFFECTIVE: '现行有效',
    APPLICATION_CLOSED: '本年度窗口已关闭',
    REFERENCE: '政策对照',
    POTENTIALLY_ELIGIBLE: '可进入尽调',
    INSUFFICIENT_EVIDENCE: '待补证据',
    REFERENCE_ONLY: '名单对照',
    MATCHED: '主体精确匹配',
  }
  return labels[value] || value || '待核验'
}

function policyTone(value) {
  if (['EFFECTIVE', 'POTENTIALLY_ELIGIBLE', 'MATCHED'].includes(value)) return 'positive'
  if (['APPLICATION_CLOSED', 'REFERENCE', 'REFERENCE_ONLY'].includes(value)) return 'neutral'
  return 'pending'
}

function opportunityStatus(value) {
  const labels = {
    PRIORITY_DUE_DILIGENCE: '建议进入尽调',
    NOT_RECOMMENDED: '暂不建议推进',
    CLOSED: '已关闭',
  }
  return labels[value] || value || '待核验'
}

function opportunityScope(value) {
  const labels = {
    FACILITY_MAPPED_PRODUCT_UNIT: '已关联设施的商品单元',
    PLATFORM_PRODUCT_UNIT_UNMAPPED_FACILITY: '公开商品单元 · 未映射实体设施',
  }
  return labels[value] || value || '范围待确认'
}

function projectIdentityStatus(value) {
  const labels = {
    CONFIRMED: '主体与资产边界已确认',
    PENDING_PROJECT_OWNER: '待核验融资主体与资产边界',
    PENDING_FACILITY_AND_ASSET_OWNER: '待核验设施、主体与资产权属',
  }
  return labels[value] || value || '待核验'
}

function checklistStatus(value) {
  const labels = {
    PENDING: '待补材料',
    NOT_EVALUABLE: '尚不可评价',
    OUT_OF_CURRENT_WINDOW: '不纳入当前现金流',
    VERIFIED: '已核验',
    NOT_APPLICABLE: '不适用',
  }
  return labels[value] || value || '待核验'
}

function checklistTone(value) {
  if (value === 'VERIFIED') return 'positive'
  if (['OUT_OF_CURRENT_WINDOW', 'NOT_APPLICABLE'].includes(value)) return 'neutral'
  return 'pending'
}

function phase3DueStatus(value) {
  const labels = { VERIFIED: '已核验', PARTIAL: '口径不完整', PENDING: '待补材料' }
  return labels[value] || value || '待核验'
}

function phase3DueTone(value) {
  if (value === 'VERIFIED') return 'verified'
  if (value === 'PARTIAL') return 'partial'
  return 'pending'
}

function phase3DueGroup(value) {
  const labels = {
    PROJECT_IDENTITY: '项目识别', ASSET: '资产与能耗', FINANCING: '融资结构',
    COMMERCIAL: '商业与合同', ENERGY: '电力与容量', GREEN: '绿电与绿色属性',
    CASHFLOW: '现金流', POLICY: '政策适用',
  }
  return labels[value] || value || '尽调事项'
}

function candidateMappingLabel(value) {
  const labels = {
    EXTERNAL_SAME_GPU_REFERENCE: '同型资源参照',
    PROVIDER_CANDIDATE: '服务商候选',
    FACILITY_CANDIDATE: '设施候选',
  }
  return labels[value] || value || '关联线索'
}

function candidateConfidence(value) {
  const labels = { NONE: '不构成映射', LOW: '低置信度', MEDIUM: '中等置信度', HIGH: '高置信度' }
  return labels[value] || value || '待核验'
}

function candidateTone(value) {
  if (value === 'HIGH') return 'positive'
  if (value === 'NONE') return 'neutral'
  return 'pending'
}

function showFacilityCandidate(facilityCode) {
  if (!facilityCode) return
  chooseFacility(facilityCode)
  scrollToSection('facilities')
}

function rackPowerTierLabel(item) {
  if (item.powerTierCode === 'LT_4_4KW') return '< 4.4kW'
  if (item.powerTierCode === 'FROM_4_4_TO_6_6KW') return '4.4–6.6kW'
  if (item.powerTierCode === 'FROM_6_6_TO_10KW') return '6.6–10kW'
  if (item.powerTierCode === 'GT_10KW') return '> 10kW'
  return item.powerTierCode || '功率段待披露'
}

function phase3ScenarioTone(code) {
  if (code === 'BWX_PHASE3_CONSERVATIVE_V1') return 'conservative'
  if (code === 'BWX_PHASE3_OPTIMISTIC_V1') return 'optimistic'
  return 'base'
}

function phase3EnergyStatus(value) {
  if (value === 'WITHIN_REFERENCE_CAP') return '年电量边界内'
  if (value === 'EXCEEDS_REFERENCE_CAP') return '超过年电量边界'
  return value || '待核验'
}

function phase3ResultStatus(value) {
  if (value === 'RESEARCH_SCREENING_ONLY') return '研究筛查结果'
  if (value === 'ENERGY_CAP_EVIDENCE_REQUIRED') return '需补工程证据'
  return value || '待核验'
}

function powerSynergyStatus(value) {
  const labels = {
    REFERENCE_HISTORICAL_BILL: '历史账单参考',
    TARIFF_RISK_SCENARIO: '电价风险情景',
    GREEN_CONTRACT_PENDING: '待核验绿电合同',
    ENGINEERING_PENDING: '待核验工程可行性',
  }
  return labels[value] || value || '待核验'
}

function powerSynergyTone(value) {
  if (value === 'REFERENCE_HISTORICAL_BILL') return 'reference'
  if (value === 'ENGINEERING_PENDING') return 'pending'
  if (value === 'GREEN_CONTRACT_PENDING') return 'green'
  return 'risk'
}

function tariffPeriodLabel(value) {
  const labels = { 尖峰: '尖峰', 高峰: '高峰', 平: '平段', 低谷: '谷段' }
  return labels[value] || value || '时段'
}

function formatKw(value) {
  if (value == null) return '—'
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(Number(value))} kW`
}

function formatMwh(value) {
  if (value == null) return '—'
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value) / 1000)} MWh`
}

function choosePowerSynergyScenario(code) {
  selectedPowerSynergyCode.value = code
}

function choosePhase3Scenario(code) {
  selectedPhase3ScenarioCode.value = code
}

function formatKwhToWan(value) {
  if (value == null) return '—'
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(Number(value) / 10000)} 万kWh`
}

async function loadFacilityOperations(facilityCode = selectedFacilityCode.value) {
  facilityOperationsError.value = ''
  if (facilityCode !== 'SZCF016') {
    facilityOperations.value = null
    facilityOperationsLoading.value = false
    return
  }
  facilityOperationsLoading.value = true
  try {
    facilityOperations.value = await fetchComputeFacilityOperations(facilityCode)
  } catch (error) {
    facilityOperations.value = null
    facilityOperationsError.value = error.message || '真实经营事实加载失败'
  } finally {
    facilityOperationsLoading.value = false
  }
}

async function loadPowerSynergy(facilityCode = 'SZCF016') {
  powerSynergyLoading.value = true
  powerSynergyError.value = ''
  try {
    powerSynergy.value = await fetchComputePowerSynergy(facilityCode)
  } catch (error) {
    powerSynergy.value = null
    powerSynergyError.value = error.message || '算电协同情景加载失败'
  } finally {
    powerSynergyLoading.value = false
  }
}

function chooseFacility(facilityCode) {
  selectedFacilityCode.value = facilityCode
  loadFacilityOperations(facilityCode)
}

async function loadSelectedAnalytics() {
  const item = selectedRecommendation.value
  if (!item) {
    sensitivityRows.value = []
    financingCurve.value = []
    return
  }
  const [sensitivity, curve] = await Promise.all([
    fetchComputeSensitivity({ query: item.externalProductId, size: 100 }),
    fetchCreditPolicyCurve(item.projectEconomicsResultId, selectedPolicyCode.value),
  ])
  sensitivityRows.value = sensitivity.items.filter((row) => row.listingId === item.listingId)
  financingCurve.value = curve.curve
}

async function refreshRecommendations() {
  financeLoading.value = true
  financeError.value = ''
  try {
    const response = await fetchBankRecommendations({
      scenarioVersion: selectedScenarioVersion.value,
      policyCode: selectedPolicyCode.value,
      size: 100,
    })
    bankRecommendations.value = response.items
    const preferred = response.items.find((item) => item.recommendationStatus === 'PROCEED_DUE_DILIGENCE')
      || response.items[0]
    selectedRecommendationId.value = preferred?.projectEconomicsResultId ?? null
    await loadSelectedAnalytics()
  } catch (error) {
    financeError.value = error.message || '融资模型数据加载失败'
  } finally {
    financeLoading.value = false
  }
}

async function loadSelectedOpportunity(code = selectedOpportunityCode.value) {
  if (!code) {
    selectedOpportunityDetail.value = null
    opportunityLoading.value = false
    return
  }
  opportunityLoading.value = true
  opportunityError.value = ''
  selectedOpportunityDetail.value = null
  try {
    selectedOpportunityDetail.value = await fetchFinanceOpportunity(code)
  } catch (error) {
    opportunityError.value = error.message || '业务机会清单加载失败'
  } finally {
    opportunityLoading.value = false
  }
}

async function initializeFinanceDashboard() {
  financeLoading.value = true
  financeError.value = ''
  try {
    const [summary, policies, policy, opportunities] = await Promise.all([
      fetchComputeSummary(), fetchCreditPolicies(), fetchComputePolicyOverview(), fetchFinanceOpportunities(),
    ])
    computeSummary.value = summary
    creditPolicies.value = policies.items
    policyOverview.value = policy
    opportunityOverview.value = opportunities
    financeOpportunities.value = opportunities.items
    selectedOpportunityCode.value = opportunities.items[0]?.opportunityCode ?? null
    await loadSelectedOpportunity()
    await refreshRecommendations()
  } catch (error) {
    financeError.value = error.message || '算力模型数据加载失败'
    policyError.value = error.message || '政策模块数据加载失败'
    opportunityError.value = error.message || '业务机会清单加载失败'
    financeLoading.value = false
  }
}

async function chooseOpportunity(opportunityCode) {
  if (selectedOpportunityCode.value === opportunityCode && selectedOpportunityDetail.value) return
  selectedOpportunityCode.value = opportunityCode
  await loadSelectedOpportunity(opportunityCode)
}

async function chooseScenario(version) {
  if (selectedScenarioVersion.value === version) return
  selectedScenarioVersion.value = version
  await refreshRecommendations()
}

async function choosePolicy(code) {
  if (selectedPolicyCode.value === code) return
  selectedPolicyCode.value = code
  await refreshRecommendations()
}

async function chooseRecommendation(projectId) {
  if (selectedRecommendationId.value === projectId) return
  selectedRecommendationId.value = projectId
  financeLoading.value = true
  financeError.value = ''
  try {
    await loadSelectedAnalytics()
  } catch (error) {
    financeError.value = error.message || '项目分析数据加载失败'
  } finally {
    financeLoading.value = false
  }
}

function setPath(path) {
  window.history.pushState({}, '', appUrl(path))
  currentPath.value = path
}

function openDetailPage(page, facilityCode = null) {
  if (facilityCode || page === 'due-diligence' || page === 'synergy') chooseFacility(facilityCode || 'SZCF016')
  if (page === 'synergy') loadPowerSynergy('SZCF016')
  setPath(page === 'due-diligence' ? '/due-diligence/baiwangxin-phase3'
    : page === 'synergy' ? '/power-synergy/baiwangxin-phase3' : `/${page}`)
  menuOpen.value = false
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

async function returnHome(target = 'top') {
  setPath('/')
  await nextTick()
  if (target === 'top') window.scrollTo({ top: 0, behavior: 'smooth' })
  else document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  menuOpen.value = false
}

function goNavigation(item) {
  if (item.page) {
    openDetailPage(item.page)
    return
  }
  scrollToSection(item.target)
}

async function scrollToSection(target) {
  if (!isHome.value) {
    await returnHome(target)
    return
  }
  document.getElementById(target)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  menuOpen.value = false
}

function syncPath() {
  currentPath.value = currentAppPath()
  if (activeDetailPage.value === 'due-diligence') chooseFacility('SZCF016')
  if (activeDetailPage.value === 'synergy') {
    chooseFacility('SZCF016')
    loadPowerSynergy('SZCF016')
  }
  window.scrollTo({ top: 0 })
}

function closeOnEscape(event) {
  if (event.key === 'Escape') formulaOpen.value = false
}

onMounted(() => {
  window.addEventListener('keydown', closeOnEscape)
  window.addEventListener('popstate', syncPath)
  initializeFinanceDashboard()
  loadFacilityOperations('SZCF016')
  if (activeDetailPage.value === 'due-diligence') chooseFacility('SZCF016')
  if (activeDetailPage.value === 'synergy') {
    chooseFacility('SZCF016')
    loadPowerSynergy('SZCF016')
  }
  if (isHome.value) loadPowerSynergy('SZCF016')
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', closeOnEscape)
  window.removeEventListener('popstate', syncPath)
})
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="topbar">
        <button class="brand" type="button" @click="returnHome()">
          <span class="brand-mark"><i></i><i></i><i></i></span>
          <span><strong>电力能源金融</strong><small>算力研究分站</small></span>
        </button>
        <nav class="main-nav" :class="{ 'is-open': menuOpen }" aria-label="主导航">
          <button v-for="item in navigation" :key="item.target" type="button" @click="goNavigation(item)">{{ item.label }}</button>
        </nav>
        <div class="site-switcher" aria-label="研究站点切换">
          <a :href="bankWorkbenchUrl" title="进入银行客户经理工作台">工作台</a>
          <a :href="powerSiteUrl" title="进入电力能源研究网站">电力研究</a>
          <b>算力研究</b>
        </div>
        <button class="menu-toggle" type="button" aria-label="展开导航" :aria-expanded="menuOpen" @click="menuOpen = !menuOpen"><span></span><span></span></button>
      </div>
    </header>

    <main id="top">
      <section v-if="!isHome" class="detail-page-banner section-shell">
        <button type="button" @click="returnHome()">← 返回研究总览</button>
        <div><span>{{ detailPageMeta.eyebrow }}</span><h1>{{ detailPageMeta.title }}</h1><p>{{ detailPageMeta.text }}</p></div>
      </section>

      <section v-if="isHome" class="hero section-shell">
        <div class="hero-copy">
          <p class="eyebrow light"><span></span>面向银行业务的算力基础设施研究情景</p>
          <h1><span class="market-highlight">从算力供给，</span><em>识别绿色算力与融资机会。</em></h1>
          <p class="hero-summary">把算力设施、公开商品价格、能源效率、电力成本与融资能力放进同一条可追溯分析链路。</p>
          <div class="hero-actions">
            <button class="button primary" type="button" @click="openDetailPage('facilities')">查看设施画像 <span>→</span></button>
            <button class="button ghost" type="button" @click="openDetailPage('synergy')">查看算电协同</button>
          </div>
          <p class="disclaimer"><b>研究边界</b> 当前展示为公开资料与研究框架，不构成算力采购或授信承诺。</p>
        </div>
        <aside class="hero-panel">
          <div class="panel-heading"><span>COMPUTE MARKET / V1.0</span><b>当前公开分析覆盖</b></div>
          <div class="coverage-grid">
            <button v-for="item in coverage" :key="item.label" type="button" @click="scrollToSection(item.label.includes('价格') || item.label.includes('商品') ? 'market' : item.label.includes('平台') ? 'market' : 'facilities')">
              <strong>{{ item.value }}</strong><span>{{ item.label }}</span><small>{{ item.note }} ↗</small>
            </button>
          </div>
          <div class="supply-card">
            <div><span>设施地域分布</span><b>FIELD-VERIFIED</b></div>
            <div class="supply-bar"><i class="local"></i><i class="shenshan"></i><i class="remote"></i></div>
            <dl><div><dt>深圳本地</dt><dd>12</dd></div><div><dt>深汕</dt><dd>2</dd></div><div><dt>异地集群</dt><dd>1</dd></div></dl>
            <p>异地与平台调度容量不计入深圳本地物理容量。</p>
          </div>
        </aside>
      </section>

      <section v-if="isHome" id="landscape" class="landscape-section section-shell">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>外部环境</p><h2>算力市场正在形成新的基础设施金融场景</h2></div>
          <p>银行不只需要判断“有多少P算力”，还要识别容量是否真实投运、商品是否能形成收入，以及能源成本是否可持续。</p>
        </div>
        <div class="signal-grid">
          <article v-for="signal in marketSignals" :key="signal.index" class="signal-card" :class="signal.tone">
            <div class="signal-index">{{ signal.index }}</div><span>{{ signal.tag }}</span><h3>{{ signal.title }}</h3><p>{{ signal.text }}</p>
            <ul><li v-for="impact in signal.impacts" :key="impact">{{ impact }}</li></ul>
          </article>
        </div>
        <div class="boundary-banner"><b>关键口径</b><p>物理装机容量 ≠ 平台纳管容量 ≠ 商品配置卡数。不同精度的 PFLOPS / EOPS 也不能直接相加。</p></div>
      </section>

      <section v-if="isHome" id="market" class="market-section">
        <div class="section-shell">
          <div class="section-heading light-heading">
            <div><p class="eyebrow light"><span></span>公开市场</p><h2>算力商品已经出现价格信号，但仍需解释配置差异</h2></div>
            <p>公开API快照用于观察市场，不代表真实库存、成交合同或未来价格。</p>
          </div>
          <div class="market-layout">
            <div class="product-list">
              <button v-for="product in products" :key="product.id" type="button" :class="{ active: selectedProductId === product.id }" @click="selectedProductId = product.id">
                <span>{{ product.type }}</span><strong>{{ product.name }}</strong><small>{{ product.region }} · {{ product.model }}</small>
              </button>
            </div>
            <article class="price-card">
              <div class="price-heading"><div><span>SELECTED PRODUCT</span><h3>{{ selectedProduct.name }}</h3></div><b :class="{ warning: selectedProduct.conflict }">{{ selectedProduct.conflict ? '价格口径待核验' : '单一公开价' }}</b></div>
              <div class="price-comparison">
                <div><span>列表参考价</span><strong>{{ formatPrice(selectedProduct.listPrice) }}</strong><small>{{ selectedProduct.unit }}</small></div>
                <div><span>详情主实例价</span><strong>{{ formatPrice(selectedProduct.detailPrice) }}</strong><small>{{ selectedProduct.detailPrice ? selectedProduct.unit : '暂未发现独立详情价' }}</small></div>
              </div>
              <div v-if="priceDifference != null" class="price-gap"><span>相对差异</span><b>{{ priceDifference > 0 ? '+' : '' }}{{ (priceDifference * 100).toFixed(1) }}%</b><p>两种价格均保留，不自动判断哪一个正确。可能来自配置、优惠或更新时间差异。</p></div>
              <dl><div><dt>商品配置</dt><dd>{{ selectedProduct.model }}</dd></div><div><dt>地域</dt><dd>{{ selectedProduct.region }}</dd></div><div><dt>来源</dt><dd>{{ selectedProduct.source }}</dd></div><div><dt>成交价格</dt><dd>暂无公开数据</dd></div></dl>
            </article>
          </div>
          <div class="market-stats"><div><strong>51</strong><span>公开商品</span></div><div><strong>14</strong><span>主实例价格冲突</span></div><div><strong>90</strong><span>存储/网络等附加计费项</span></div><p>价格冲突本身也是尽调信号：银行测算收入时，应使用合同价格和最低采购期限，而不是网页起价。</p></div>
        </div>
      </section>

      <section v-if="isHome" id="facilities" class="facility-section section-shell facility-preview-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>设施画像</p><h2>先看四个最具代表性的设施样本</h2></div>
          <p>首页只保留可支持判断的核心口径；完整设施档案、百旺信真实经营事实与三期项目情景进入独立数据页。</p>
        </div>
        <div class="facility-preview-grid">
          <button v-for="facility in facilityHighlights" :key="facility.code" type="button" @click="openDetailPage('facilities', facility.code)">
            <div><span>{{ facility.code }}</span><b>证据 {{ facility.grade }}</b></div>
            <h3>{{ facility.name }}</h3><p>{{ facility.location }} · {{ facility.type }}</p>
            <strong>{{ facility.capacity }}</strong><small>{{ facility.energy }}</small>
          </button>
        </div>
        <div class="preview-action-row"><p><b>当前覆盖 {{ coverage[0].value }} 个设施。</b> 其余设施、字段来源、证据缺口与经营数据不在首页平铺展示。</p><button type="button" @click="openDetailPage('facilities')">查看设施数据页 <span>→</span></button></div>
      </section>

      <section v-else-if="activeDetailPage === 'facilities'" id="facilities" class="facility-section section-shell detail-data-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>设施画像</p><h2>先从公开证据较完整的6个样本开始</h2></div>
          <p>六个样本覆盖智算、IDC、深汕节点和市场化中心。其公开字段各有侧重，现阶段不强行生成统一评分。</p>
        </div>
        <div class="facility-layout">
          <div class="facility-list">
            <button v-for="facility in facilities" :key="facility.code" type="button" :class="{ active: selectedFacilityCode === facility.code }" @click="chooseFacility(facility.code)">
              <span>{{ facility.code }}</span><strong>{{ facility.name }}</strong><small>{{ facility.location }} · {{ facility.type }}</small><i>{{ facility.status }}</i>
            </button>
          </div>
          <article class="facility-detail">
            <div class="facility-title"><div><span>{{ selectedFacility.code }} / {{ selectedFacility.type }}</span><h3>{{ selectedFacility.name }}</h3><p>{{ selectedFacility.location }} · {{ selectedFacility.status }}</p></div><b>证据 {{ selectedFacility.grade }}</b></div>
            <div class="facility-kpis"><div><span>公开规模</span><strong>{{ selectedFacility.capacity }}</strong><small>{{ selectedFacility.precision }}</small></div><div><span>补充口径</span><strong>{{ selectedFacility.secondaryCapacity }}</strong><small>不与主口径直接相加</small></div><div><span>能源信息</span><strong>{{ selectedFacility.energy }}</strong><small>公开披露</small></div><div><span>投资/价格</span><strong>{{ selectedFacility.price }}</strong><small>口径保留</small></div></div>
            <div class="facility-columns"><div><h4>目前可以确认</h4><ul><li v-for="fact in selectedFacility.facts" :key="fact">{{ fact }}</li></ul></div><div><h4>后续仍需补充</h4><ul class="gap-list"><li v-for="gap in selectedFacility.gaps" :key="gap">{{ gap }}<span>暂无</span></li></ul></div></div>
            <div class="facility-use"><span>研究价值</span><p>{{ selectedFacility.fit }}</p></div>
            <button v-if="selectedFacilityCode === 'SZCF016'" class="facility-due-link" type="button" @click="openDetailPage('due-diligence')">查看百旺信三期尽调状态 <span>→</span></button>
            <button v-if="selectedFacilityCode === 'SZCF016'" class="facility-due-link power-link" type="button" @click="openDetailPage('synergy')">查看百旺信三期算电协同情景 <span>→</span></button>

            <div v-if="facilityOperationsError" class="facility-operation-alert">{{ facilityOperationsError }}</div>
            <div v-if="facilityOperationsLoading" class="facility-operation-loading">正在读取百旺信的公开经营事实…</div>
            <section v-if="selectedFacilityOperations" class="facility-operation-panel">
              <header><div><span>PUBLIC OPERATING FACTS / 2023—2025</span><h4>真实经营校准：上架率、收入、电量与单位价格</h4></div><a v-if="baiwangAnnualOperations[0]?.sourceUrl" :href="baiwangAnnualOperations[0].sourceUrl" target="_blank" rel="noreferrer">查看公开披露 ↗</a></header>
              <div class="operation-fact-grid">
                <article v-for="row in baiwangAnnualOperations" :key="`${row.factYear}-${row.factPeriod}`">
                  <span>{{ row.factYear }} 年 · {{ row.factPeriod === 'ANNUAL' ? '全年' : '上半年' }}</span>
                  <strong>{{ formatPercent(row.rackUtilizationRatio, 2) }}</strong><small>上架率 · {{ formatPrice(row.averageOccupiedRackCount) }} / {{ formatPrice(row.rackCapacityCount) }} 柜</small>
                  <dl><div><dt>自建托管收入</dt><dd>{{ formatPrice(row.hostingRevenueWanyuan) }} 万元</dd></div><div><dt>电力用量</dt><dd>{{ formatKwhToWan(row.electricityConsumptionKwh) }}</dd></div><div><dt>平均单价</dt><dd>{{ formatPrice(row.averageRackPriceYuanMonth) }} 元/柜·月</dd></div><div><dt>毛利率</dt><dd>{{ formatPercent(row.hostingGrossMargin, 2) }}</dd></div></dl>
                  <p>不含税电力采购 {{ formatPrice(row.electricityPurchaseWanyuan) }} 万元{{ row.electricityPurchaseTaxIncludedWanyuan == null ? '' : `；含税汇总 ${formatPrice(row.electricityPurchaseTaxIncludedWanyuan)} 万元` }}。{{ row.electricityPurchasePriceYuanKwh == null ? '' : `含税采购单价 ${formatPrice(row.electricityPurchasePriceYuanKwh)} 元/kWh；` }}由公开收入×比例反推的隐含电价 {{ formatPrice(row.derivedImpliedElectricityPriceYuanKwh) }} 元/kWh。</p>
                </article>
              </div>

              <div class="operation-subgrid">
                <article class="building-utilization-card"><div><span>BUILDING RAMP-UP</span><h5>1栋与4栋上架率爬坡</h5></div><dl><div v-for="item in baiwangBuildingUtilization" :key="`${item.operationScopeCode}-${item.factYear}-${item.factPeriod}`"><dt>{{ item.operationScopeName }} · {{ item.factYear }}{{ item.factPeriod === 'H1' ? 'H1' : '' }}</dt><dd>{{ formatPercent(item.rackUtilizationRatio, 2) }}</dd></div></dl><small>这是分栋披露比例；未与全年合并口径混算。</small></article>
                <article class="contract-fact-card" v-for="contract in baiwangCustomerContracts" :key="contract.contractFactCode"><div><span>PUBLIC WHOLESALE CONTRACT</span><h5>{{ contract.customerName }} · 约{{ formatPrice(contract.contractedRackCountApprox) }}柜</h5></div><p>{{ formatPrice(contract.basePriceYuanRackMonth) }} 元/柜·月（含{{ formatPrice(contract.includedCurrentAmp) }}A）；超额 {{ formatPrice(contract.excessPriceYuanAmpRackMonth) }} 元/A·柜·月</p><dl><div><dt>空置保护</dt><dd>{{ contract.vacantProtectionMonths }}个月</dd></div><div><dt>上电门槛</dt><dd>{{ formatPercent(contract.firstOccupancyThresholdRatio) }} / {{ formatPercent(contract.secondOccupancyThresholdRatio) }}</dd></div><div><dt>空置服务费</dt><dd>{{ formatPrice(contract.vacantFeeYuanRackMonth) }} 元/柜·月</dd></div></dl><small>合同有效期披露至 {{ contract.contractEndDate }}；批发合同不能当作零售市场价格。</small></article>
              </div>

              <div class="rack-tier-card"><div class="rack-tier-heading"><div><span>ACTUAL TRANSACTION PRICE · 2025 H1</span><h5>不同功率机柜的实际成交均价</h5></div><small>元/柜·月；按当期托管收入÷托管数量统计</small></div><div class="rack-tier-grid"><article v-for="item in baiwangLatestRackPriceTiers" :key="`${item.buildingScopeCode}-${item.powerTierCode}`"><span>{{ item.buildingScopeCode === 'BUILDING_1' ? '1栋' : '4栋' }} · {{ rackPowerTierLabel(item) }}</span><b>{{ formatPrice(item.actualAveragePriceYuanRackMonth) }}</b></article></div></div>
              <section v-if="baiwangPhase3CashflowScenarios.length" class="phase3-cashflow-panel">
                <header class="phase3-cashflow-heading">
                  <div><span>PHASE III · PUBLIC-ANCHORED CASHFLOW SCENARIOS</span><h5>三期项目：保守、基准与乐观的十年现金流代理</h5></div>
                  <small>公开锚点：3.2亿元历史投资 · 1,760柜 · PUE 1.228 · 年电量边界4,847.33万kWh</small>
                </header>
                <div class="phase3-scenario-grid">
                  <button v-for="scenario in baiwangPhase3CashflowScenarios" :key="scenario.scenarioCode" type="button"
                    :class="[phase3ScenarioTone(scenario.scenarioCode), { active: selectedBaiwangPhase3Scenario?.scenarioCode === scenario.scenarioCode }]"
                    @click="choosePhase3Scenario(scenario.scenarioCode)">
                    <div><span>{{ scenario.scenarioName }}</span><b :class="scenario.energyCapComplianceStatus === 'WITHIN_REFERENCE_CAP' ? 'positive' : 'warning'">{{ phase3ResultStatus(scenario.resultStatus) }}</b></div>
                    <strong>首年 {{ formatWan(scenario.year1PreTaxCashflowProxyYuan) }}</strong><small>税前经营现金流代理</small>
                    <dl><div><dt>上架率</dt><dd>{{ formatPercent(scenario.year1RackOccupancyRatio, 1) }} → {{ formatPercent(scenario.steadyStateRackOccupancyRatio, 1) }}</dd></div><div><dt>首年收入代理</dt><dd>{{ formatWan(scenario.year1RevenueYuan) }}</dd></div><div><dt>年电量边界</dt><dd>{{ phase3EnergyStatus(scenario.energyCapComplianceStatus) }}</dd></div></dl>
                  </button>
                </div>
                <div v-if="selectedBaiwangPhase3Scenario" class="phase3-selected-detail">
                  <div class="phase3-assumption-row">
                    <article><span>机柜价格代理</span><strong>{{ formatPrice(selectedBaiwangPhase3Scenario.rackPriceYuanMonth) }} 元/柜·月</strong><small>{{ selectedBaiwangPhase3Scenario.rackPriceInputType }}</small></article>
                    <article><span>单柜 IT 负载代理</span><strong>{{ formatPrice(selectedBaiwangPhase3Scenario.avgItLoadKwPerOccupiedRack) }} kW</strong><small>{{ selectedBaiwangPhase3Scenario.itLoadInputType }}</small></article>
                    <article><span>电价代理</span><strong>{{ formatPrice(selectedBaiwangPhase3Scenario.electricityPriceYuanKwh) }} 元/kWh</strong><small>{{ selectedBaiwangPhase3Scenario.electricityPriceInputType }}</small></article>
                    <article><span>非电成本代理</span><strong>{{ formatPercent(selectedBaiwangPhase3Scenario.otherOperatingCostProxyRatio, 2) }}</strong><small>{{ selectedBaiwangPhase3Scenario.otherCostInputType }}</small></article>
                  </div>
                  <div class="phase3-year-table-wrap">
                    <table class="phase3-year-table">
                      <thead><tr><th>年份</th><th>上架率</th><th>收入代理</th><th>总电量</th><th>税前现金流代理</th><th>边界校验</th></tr></thead>
                      <tbody><tr v-for="row in selectedBaiwangPhase3Years" :key="row.cashflowYearIndex"><td>{{ row.calendarYear }}</td><td>{{ formatPercent(row.modeledRackOccupancyRatio, 1) }}</td><td>{{ formatWan(row.modeledRevenueYuan) }}</td><td>{{ formatKwhToWan(row.modeledTotalEnergyKwh) }}</td><td>{{ formatWan(row.modeledPreTaxCashflowProxyYuan) }}</td><td><b :class="row.energyCapStatus === 'WITHIN_REFERENCE_CAP' ? 'positive' : 'warning'">{{ phase3EnergyStatus(row.energyCapStatus) }}</b></td></tr></tbody>
                    </table>
                  </div>
                  <div class="phase3-result-strip"><div><span>10年现金流代理现值</span><b>{{ formatWan(selectedBaiwangPhase3Scenario.pvPreTaxCashflowProxyYuan) }}</b></div><div><span>假设绿地重建 NPV 代理</span><b>{{ formatWan(selectedBaiwangPhase3Scenario.hypotheticalGreenfieldNpvProxyYuan) }}</b></div><div><span>结论状态</span><b :class="selectedBaiwangPhase3Scenario.energyCapComplianceStatus === 'WITHIN_REFERENCE_CAP' ? 'positive' : 'warning'">{{ phase3ResultStatus(selectedBaiwangPhase3Scenario.resultStatus) }}</b></div></div>
                  <p class="phase3-disclaimer"><b>模型边界</b>{{ selectedBaiwangPhase3Scenario.assumptionNote }} 公式：收入＝机柜数×上架率×单柜月价×12；总电量＝机柜数×上架率×单柜IT负载×8,760×PUE；现金流代理＝收入－电力成本－非电成本代理。未纳入税费、营运资本、债务本息、维护/更换CAPEX；因此不构成三期真实CFADS、实际NPV、估值或授信建议。</p>
                </div>
              </section>
              <p class="facility-operation-boundary"><b>口径边界</b>{{ selectedFacilityOperations.boundary }}</p>
            </section>
          </article>
        </div>
      </section>

      <section v-else-if="activeDetailPage === 'synergy'" class="power-synergy-section section-shell">
        <div v-if="powerSynergyLoading" class="model-loading">正在读取深圳电价、电源结构与百旺信三期成本情景…</div>
        <div v-else-if="powerSynergyError" class="model-alert">{{ powerSynergyError }}</div>
        <template v-else-if="selectedPowerSynergy">
          <section v-if="baiwangLatestOperation && baiwangOperatingInsight" class="banker-operating-overview">
            <div class="banker-operating-copy">
              <span>FIRST LAYER · PUBLIC OPERATING FACTS</span>
              <h2>重点能源金融客户：经营规模在增长，电力成本已是可量化的核心变量。</h2>
              <p>以下为百旺信1栋+4栋自建托管运营的2023—2025公开经营事实，不与三期项目口径混用。客户经理可以据此判断客户经营质量、电费风险及优先拜访主题。</p>
              <div class="banker-decision"><b>客户经营判断</b><strong>高成长 · 高能耗 · 可开展能源金融营销</strong><small>不等同于三期项目授信结论</small></div>
            </div>
            <div class="banker-kpi-grid">
              <article><span>2025上架率</span><strong>{{ formatPercent(baiwangLatestOperation.rackUtilizationRatio, 2) }}</strong><small>{{ formatPrice(baiwangLatestOperation.averageOccupiedRackCount) }} / {{ formatPrice(baiwangLatestOperation.rackCapacityCount) }} 柜 · 较2023年 +{{ baiwangOperatingInsight.occupancyPoints.toFixed(2) }}个百分点</small></article>
              <article><span>2025托管收入 / 毛利</span><strong>{{ formatWanyuan(baiwangLatestOperation.hostingRevenueWanyuan) }}</strong><small>毛利 {{ formatWanyuan(baiwangLatestOperation.derivedGrossProfitWanyuan) }} · 毛利率 {{ formatPercent(baiwangLatestOperation.hostingGrossMargin, 2) }}</small></article>
              <article><span>2025电力用量 / 电费</span><strong>{{ formatKwhToWan(baiwangLatestOperation.electricityConsumptionKwh) }}</strong><small>电费 {{ formatWanyuan(baiwangLatestOperation.electricityPurchaseWanyuan) }} · 占收入 {{ formatPercent(baiwangLatestOperation.electricityCostRevenueRatio, 2) }}</small></article>
              <article class="sensitivity"><span>电价每变动 0.01 元/kWh</span><strong>{{ formatWan(baiwangOperatingInsight.oneFenElectricitySensitivityYuan) }}</strong><small>按2025实际电量直接计算；0.10元/kWh即约 {{ formatWan(baiwangOperatingInsight.oneJiaoElectricitySensitivityYuan) }}</small></article>
            </div>
          </section>

          <section v-else class="model-loading">正在读取百旺信1栋+4栋的公开经营事实…</section>

          <section v-if="baiwangLatestOperation && baiwangOperatingInsight" class="banker-action-panel">
            <header><div><span>ACCOUNT MANAGER ACTIONS</span><h3>现在可以带着哪些结论去见客户？</h3></div><small>每项均来自公开经营事实或其直接算术推导。</small></header>
            <div>
              <article><b>01</b><div><strong>优先切入电费优化</strong><p>2025电费占托管收入{{ formatPercent(baiwangLatestOperation.electricityCostRevenueRatio, 2) }}；电价每上升0.01元/kWh，成本约增加{{ formatWan(baiwangOperatingInsight.oneFenElectricitySensitivityYuan) }}。可先提供分时账单诊断、购电策略及绿电采购测算。</p></div></article>
              <article><b>02</b><div><strong>关注高功率机柜扩张</strong><p>2025年已有{{ formatPrice(baiwangLatestOperation.highPowerOccupiedRackCount) }}个{{ formatPrice(baiwangLatestOperation.highPowerThresholdKw) }}kW以上机柜。可围绕供配电、液冷、能效改造及设备更新了解资本开支计划。</p></div></article>
              <article><b>03</b><div><strong>经营增长主要来自上架率</strong><p>2023—2025托管收入增长{{ formatPercent(baiwangOperatingInsight.revenueGrowth, 1) }}，而平均单柜月价仅变化{{ formatPercent(baiwangOperatingInsight.priceChange, 1) }}；应重点核验上架率、客户集中度和回款质量，而非只看挂牌价格。</p></div></article>
              <article><b>04</b><div><strong>下一轮拜访索取的材料</strong><p>近12个月分时电费单、最大需量与变压器容量、绿电合同/结算单、高功率机柜扩容与供配电改造计划。拿到后才进入三期的储能、需求响应与融资测算。</p></div></article>
            </div>
          </section>

          <section class="synergy-overview opportunity-layer">
            <div class="synergy-overview-copy">
              <span>SECOND LAYER · PROJECT OPPORTUNITIES</span>
              <h2>绿电、储能和需求响应是可探索的降本路径，不是当前已实现收益。</h2>
              <p>以下以百旺信三期基准情景首年电量 {{ formatKwhToWan(selectedPowerSynergy.referenceEnergyKwh) }} 为统一边界。它用于识别电价风险与工程筛查方向，不覆盖税费、债务本息、实际小时负荷或实际绿电结算。</p>
            </div>
            <div class="synergy-signal-grid">
              <article><span>历史电价代理</span><strong>{{ formatPrice(selectedPowerSynergy.referenceBillPriceYuanKwh) }}</strong><small>元/kWh · 三期既有基准输入</small></article>
              <article><span>深圳分时加权价</span><strong>{{ formatPrice(selectedPowerSynergy.weightedTouPriceYuanKwh) }}</strong><small>元/kWh · 2026年7月研究分配</small></article>
              <article><span>深圳本地清洁电源</span><strong>≥{{ formatPercent(selectedPowerSynergy.regionalCleanReferenceRatio) }}</strong><small>装机信号，不等于设施绿电</small></article>
              <article><span>广东火电发电占比</span><strong>{{ formatPercent(selectedPowerSynergy.regionalFossilGenerationShareRatio, 1) }}</strong><small>2025区域发电结构代理</small></article>
            </div>
          </section>

          <section class="synergy-scenario-panel">
            <header><div><span>SCENARIO COMPARISON</span><h3>电价、绿电与储能对现金流代理的影响</h3></div><small>同一电量边界；储能CAPEX单列，不从年度现金流中扣除。</small></header>
            <div class="synergy-scenario-grid">
              <button v-for="scenario in powerSynergyScenarios" :key="scenario.scenarioCode" type="button"
                :class="[powerSynergyTone(scenario.resultStatus), { active: selectedPowerSynergy?.scenarioCode === scenario.scenarioCode }]"
                @click="choosePowerSynergyScenario(scenario.scenarioCode)">
                <div><span>{{ scenario.scenarioName }}</span><b>{{ powerSynergyStatus(scenario.resultStatus) }}</b></div>
                <strong>{{ formatWan(scenario.modeledPreTaxCashflowProxyYuan) }}</strong><small>税前经营现金流代理</small>
                <p :class="Number(scenario.cashflowChangeFromReferenceYuan) < 0 ? 'negative' : 'positive'">较历史电价参考 {{ Number(scenario.cashflowChangeFromReferenceYuan) > 0 ? '+' : '' }}{{ formatWan(scenario.cashflowChangeFromReferenceYuan) }}</p>
              </button>
            </div>
          </section>

          <section class="synergy-detail-grid">
            <article class="synergy-cost-panel">
              <header><span>COST WATERFALL · {{ selectedPowerSynergy.scenarioName }}</span><h3>现金流变化来自哪里？</h3></header>
              <dl>
                <div><dt>历史账单成本参考</dt><dd>{{ formatWan(selectedPowerSynergy.referenceHistoricalBillCostYuan) }}</dd></div>
                <div><dt>分时电价成本</dt><dd>{{ formatWan(selectedPowerSynergy.modeledTouElectricityCostYuan) }}</dd></div>
                <div><dt>绿电/环境溢价</dt><dd>{{ formatWan(selectedPowerSynergy.greenPowerPremiumCostYuan) }}</dd></div>
                <div><dt>储能套利毛收益</dt><dd class="positive">{{ formatWan(selectedPowerSynergy.storageGrossArbitrageYuan) }}</dd></div>
                <div><dt>储能年运维代理</dt><dd>{{ formatWan(selectedPowerSynergy.storageAnnualOpexYuan) }}</dd></div>
                <div class="emphasis"><dt>现金流代理变化</dt><dd :class="Number(selectedPowerSynergy.cashflowChangeFromReferenceYuan) < 0 ? 'negative' : 'positive'">{{ Number(selectedPowerSynergy.cashflowChangeFromReferenceYuan) > 0 ? '+' : '' }}{{ formatWan(selectedPowerSynergy.cashflowChangeFromReferenceYuan) }}</dd></div>
              </dl>
              <p>分时电价情景的负向变化是“历史账单代理”与“区域分时电价研究分配”之间的风险覆盖，不可解读为已发生损失。</p>
            </article>

            <article class="synergy-action-panel">
              <header><span>GREEN / STORAGE / DEMAND RESPONSE</span><h3>可量化部分与待尽调部分</h3></header>
              <div class="synergy-action-row"><span>绿电采购</span><b>{{ formatPercent(selectedPowerSynergy.greenPowerPurchaseRatio) }}</b><small>{{ selectedPowerSynergy.greenPowerStatus === 'NO_PUBLIC_GREEN_CONTRACT' ? '暂无公开合同' : '研究情景，待合同与结算单' }}</small></div>
              <div class="synergy-action-row"><span>储能移峰</span><b>{{ formatPercent(selectedPowerSynergy.storageShiftRatio) }}</b><small>{{ selectedPowerSynergy.storageStatus === 'NO_STORAGE_ASSET_DISCLOSED' ? '未披露储能资产' : '工程、接入与消防待核验' }}</small></div>
              <div v-if="Number(selectedPowerSynergy.storageShiftRatio) > 0" class="synergy-storage-kpis"><div><span>所需功率代理</span><b>{{ formatKw(selectedPowerSynergy.requiredStoragePowerKw) }}</b></div><div><span>所需容量代理</span><b>{{ formatMwh(selectedPowerSynergy.requiredStorageCapacityKwh) }}</b></div><div><span>储能CAPEX代理</span><b>{{ formatWan(selectedPowerSynergy.storageCapexProxyYuan) }}</b></div></div>
              <div class="synergy-action-row demand"><span>需求响应</span><b>{{ formatKw(selectedPowerSynergy.demandResponseTargetCapacityKwProxy) }}</b><small>按设计最大负荷5%作资格门槛代理；无注册、测试和结算，已计收益为0。</small></div>
            </article>
          </section>

          <section v-if="selectedPowerSynergyTariffs.length" class="synergy-tariff-panel">
            <header><div><span>REGIONAL TOU INPUT</span><h3>采用的深圳分时电价与研究性负荷分配</h3></div><small>最新可匹配：2026年7月 · 10kV · 3001kVA及以上一档。</small></header>
            <div><article v-for="item in selectedPowerSynergyTariffs" :key="item.tariffId"><span>{{ tariffPeriodLabel(item.timePeriod) }}</span><b>{{ formatPrice(item.finalPriceYuanKwh) }}</b><small>元/kWh · 分配 {{ formatPercent(item.loadAllocationRatio, 2) }}</small><em>{{ item.startTimeText }}—{{ item.endTimeText }}</em></article></div>
          </section>

          <p class="synergy-boundary"><b>模型边界</b>{{ powerSynergy.boundary }}</p>
        </template>
      </section>

      <section v-else-if="activeDetailPage === 'due-diligence'" class="due-diligence-section section-shell">
        <div v-if="facilityOperationsLoading" class="model-loading">正在读取百旺信三期的公开尽调状态…</div>
        <div v-else-if="facilityOperationsError" class="model-alert">{{ facilityOperationsError }}</div>
        <template v-else>
          <section class="due-status-overview">
            <div class="due-status-summary">
              <span>当前判断</span><h2>项目边界与工程锚点已披露；尚未具备项目级偿债测算条件。</h2>
              <p>最大阻断项是三期独立收入、成本、回款和债务本息数据缺失。现有现金流仅为公开锚定的研究代理。</p>
            </div>
            <div class="due-status-counts">
              <article class="verified"><strong>{{ baiwangDueDiligenceCounts.VERIFIED }}</strong><span>已核验</span></article>
              <article class="partial"><strong>{{ baiwangDueDiligenceCounts.PARTIAL }}</strong><span>口径不完整</span></article>
              <article class="pending"><strong>{{ baiwangDueDiligenceCounts.PENDING }}</strong><span>待补材料</span></article>
            </div>
          </section>

          <section v-if="baiwangPhase3DueDiligence.length" class="due-checklist-panel">
            <header><div><span>PROJECT DUE DILIGENCE / V1</span><h3>尽调状态清单</h3></div><small>状态基于公开资料，不将缺失信息推定为不符合。</small></header>
            <article v-for="item in baiwangPhase3DueDiligence" :key="item.projectDueDiligenceId" class="due-check-item">
              <div class="due-check-status"><span>{{ phase3DueGroup(item.checkGroup) }}</span><b :class="phase3DueTone(item.evidenceStatus)">{{ phase3DueStatus(item.evidenceStatus) }}</b><em :class="item.riskLevel.toLowerCase()">{{ item.riskLevel }}</em></div>
              <div><h4>{{ item.checkName }}</h4><p>{{ item.evidenceSummary }}</p></div>
              <div><span>需补材料</span><p>{{ item.requiredEvidence }}</p></div>
              <div><span>下一步</span><p>{{ item.dueDiligenceAction }}</p><a v-if="item.sourceUrl" :href="item.sourceUrl" target="_blank" rel="noreferrer">查看公开来源 ↗</a></div>
            </article>
          </section>
          <p class="due-boundary"><b>使用边界</b>本页用于安排尽调与资料收集，不代表授信审批、政策资格确认、项目估值或贷款承诺。</p>
        </template>
      </section>

      <section v-if="isHome" id="collaboration" class="collaboration-section">
        <div class="section-shell">
          <div class="section-heading light-heading">
            <div><p class="eyebrow light"><span></span>算电协同</p><h2>算力模型与电力模型在“能源成本”处自然连接</h2></div>
            <p>算力站负责收入与设施效率，电力站提供电价、绿电和负荷边界，两边共同生成可融资现金流。</p>
          </div>
          <div class="flow-map" aria-label="算力、电力与融资分析流程">
            <article><span>01</span><b>算力设施</b><p>卡型 · 数量 · 状态</p></article><i>→</i>
            <article><span>02</span><b>设备负荷</b><p>功率 · 利用率</p></article><i>→</i>
            <article class="energy-node"><span>03</span><b>电力与PUE</b><p>电价 · 绿电 · 效率</p></article><i>→</i>
            <article><span>04</span><b>单位成本</b><p>元/GPU小时</p></article><i>→</i>
            <article><span>05</span><b>项目现金流</b><p>收入 · OPEX · CAPEX</p></article><i>→</i>
            <article class="bank-node"><span>06</span><b>融资判断</b><p>DSCR · 债务能力</p></article>
          </div>
          <div class="collaboration-notes">
            <article><span>算力站提供</span><p>设备配置、公开租赁价格、商品地域、设施状态、利用率情景。</p></article>
            <article><span>电力站提供</span><p>分时电价、区域能源结构、绿电比例、储能与需求响应机会。</p></article>
            <article><span>共同输出</span><p>单位算力能源成本、绿色算力标签、项目现金流、融资风险提示。</p></article>
            <button type="button" @click="formulaOpen = true">查看核心连接公式 <b>↗</b></button>
          </div>
        </div>
      </section>

      <section v-if="isHome" id="policy" class="compute-policy-section section-shell policy-preview-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>政策机会</p><h2>四类最值得优先核验的政策路径</h2></div>
          <p>首页不罗列全部条款；是否真正改善项目现金流，仍取决于适用对象、申报窗口与项目级证明材料。</p>
        </div>
        <div v-if="policyError" class="model-alert">{{ policyError }}</div>
        <div class="policy-preview-grid">
          <article v-for="program in policyHighlights" :key="program.ruleCode">
            <div><span>{{ program.ruleCategory }}</span><b :class="policyTone(program.ruleStatus)">{{ policyStatus(program.ruleStatus) }}</b></div>
            <h3>{{ program.ruleTitle }}</h3><p>{{ program.applicabilitySummary }}</p>
            <small>{{ program.applicableEntityType }}</small>
          </article>
          <article v-if="!policyHighlights.length" class="preview-empty">正在加载政策规则…</article>
        </div>
        <div class="preview-action-row"><p><b>{{ policyCoverage.ruleCount ?? '—' }} 条可执行规则已入库。</b> 详细政策条款、模型处理方式与设施适用性均保留在政策数据页。</p><button type="button" @click="openDetailPage('policies')">查看政策规则库 <span>→</span></button></div>
      </section>

      <section v-else-if="activeDetailPage === 'policies'" id="policy" class="compute-policy-section section-shell detail-data-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>政策机会 · 公开规则</p><h2>先判断政策对象与证据，再讨论政策能否改善现金流</h2></div>
          <p>算力政策并不都补贴设施运营商：训力券、模型券和龙岗购算力支持主要降低客户成本；绿色数据中心、绿电和虚拟电厂则更接近设施侧的改造与融资机会。</p>
        </div>

        <div v-if="policyError" class="model-alert">{{ policyError }}</div>

        <div class="policy-metric-strip">
          <article><strong>{{ policyCoverage.documentCount ?? '—' }}</strong><span>政策文档</span><small>国家—广东—深圳—龙岗</small></article>
          <article><strong>{{ policyCoverage.ruleCount ?? '—' }}</strong><span>可执行规则</span><small>条件、金额、证据与模型边界</small></article>
          <article><strong>{{ policyCoverage.providerCount ?? '—' }}</strong><span>公开训力券服务机构</span><small>{{ policyCoverage.exactProviderPlatformMatchCount ?? '—' }} 个平台主体精确匹配</small></article>
          <article><strong>{{ policyCoverage.evidenceGapCount ?? '—' }}</strong><span>待补项目级证据</span><small>不以缺失数据替代为“已获支持”</small></article>
        </div>

        <div class="policy-program-grid">
          <article v-for="program in policyPrograms" :key="program.ruleCode" class="policy-program-card">
            <div class="policy-card-top"><span>{{ program.ruleCategory }}</span><b :class="policyTone(program.ruleStatus)">{{ policyStatus(program.ruleStatus) }}</b></div>
            <h3>{{ program.ruleTitle }}</h3>
            <p>{{ program.applicabilitySummary }}</p>
            <dl>
              <div><dt>支持对象</dt><dd>{{ program.applicableEntityType }}</dd></div>
              <div><dt>模型处理</dt><dd>{{ program.modelImpactType === 'NO_AUTOMATIC_EFFECT' ? '不自动影响现金流' : program.modelImpactType === 'SCENARIO' ? '需独立政策情景' : '先补充核验材料' }}</dd></div>
            </dl>
            <div v-if="program.ruleValueText" class="policy-value">{{ program.ruleValueText }}</div>
            <a v-if="program.officialUrl" :href="program.officialUrl" target="_blank" rel="noreferrer">查看政策原文 <span>↗</span></a>
          </article>
        </div>

        <div v-if="selectedFacilityPolicy" class="policy-facility-panel">
          <div class="policy-facility-heading">
            <div><span>FACILITY POLICY READINESS</span><h3>{{ selectedFacility.name }}</h3><p>{{ selectedFacilityPolicy.priorityAction }}</p></div>
            <b :class="policyTone(selectedFacilityPolicy.greenFinanceStatus)">{{ policyStatus(selectedFacilityPolicy.greenFinanceStatus) }}</b>
          </div>
          <div class="policy-readiness-grid">
            <article><span>绿色数据中心</span><strong :class="policyTone(selectedFacilityPolicy.greenDataCenterStatus)">{{ policyStatus(selectedFacilityPolicy.greenDataCenterStatus) }}</strong><small>以16项年度评价为证据框架</small></article>
            <article><span>绿色金融初筛</span><strong :class="policyTone(selectedFacilityPolicy.greenFinanceStatus)">{{ policyStatus(selectedFacilityPolicy.greenFinanceStatus) }}</strong><small>需核验资金用途与能效等级</small></article>
            <article><span>虚拟电厂改造</span><strong :class="policyTone(selectedFacilityPolicy.vppStatus)">{{ policyStatus(selectedFacilityPolicy.vppStatus) }}</strong><small>需证明可调负荷和接入条件</small></article>
            <article><span>国家名单核验</span><strong :class="policyTone(selectedFacilityPolicy.nationalListCheckStatus)">{{ policyStatus(selectedFacilityPolicy.nationalListCheckStatus) }}</strong><small>未匹配不代表不符合绿色条件</small></article>
          </div>
        </div>

        <div class="policy-boundary-grid">
          <article><span>客户侧支持</span><h4>训力券、模型券与购算力支持</h4><p>可降低客户采购成本、增强市场需求；只有在服务机构资格、合同和客户申报均成立后，才可能形成可确认收入。</p></article>
          <article><span>设施侧支持</span><h4>绿色数据中心、绿电与虚拟电厂</h4><p>可形成绿色融资、节能改造或需求响应机会；需要项目级PUE、绿电、负荷和改造投资资料。</p></article>
          <article><span>当前模型原则</span><h4>政策金额不直接进入NPV</h4><p>没有获批文件、可核验工程量和实际结算记录时，政策只改变尽调优先级，不改变当前NPV、IRR、DSCR或贷款建议。</p></article>
        </div>

        <div v-if="policyPlatformMatches.length" class="policy-provider-note">
          <b>已核验的服务机构关联</b><span v-for="item in policyPlatformMatches" :key="item.platformCode">{{ item.platformName }}：{{ item.matchedProviderNames }}</span>
          <small>主体名称精确匹配不等于全部公开商品、价格或客户合同均可使用训力券。</small>
        </div>
      </section>

      <section v-if="isHome" id="opportunities" class="opportunity-section section-shell opportunity-preview-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>银行行动 · 尽调清单</p><h2>优先推进四个可核验的业务线索</h2></div>
          <p>仅展示当前基准经营与信贷情景下的重点候选；首页不展开资产权属、映射证据与每一项尽调材料。</p>
        </div>
        <div v-if="opportunityError" class="model-alert">{{ opportunityError }}</div>
        <div class="opportunity-preview-grid">
          <article v-for="item in opportunityHighlights" :key="item.opportunityCode">
            <div><span>{{ item.businessPriority }}级</span><b>{{ opportunityStatus(item.opportunityStatus) }}</b></div>
            <h3>{{ item.productName }}</h3><p>{{ item.platformName }} · {{ item.acceleratorModel || '配置待核验' }}</p>
            <dl><div><dt>建议贷款额</dt><dd>{{ formatWan(item.recommendedLoanYuan) }}</dd></div><div><dt>待补事项</dt><dd>{{ item.openCheckCount }} 项</dd></div></dl>
          </article>
          <article v-if="!opportunityHighlights.length" class="preview-empty">正在加载业务机会…</article>
        </div>
        <div class="preview-action-row"><p><b>{{ opportunityCoverage.priorityACount ?? '—' }} 个 A 级优先候选。</b> 项目主体、设施映射和合同级现金流仍必须进入尽调后确认。</p><button type="button" @click="openDetailPage('opportunities')">进入银行行动清单 <span>→</span></button></div>
      </section>

      <section v-else-if="activeDetailPage === 'opportunities'" id="opportunities" class="opportunity-section section-shell detail-data-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>银行行动 · 尽调清单</p><h2>把模型结果转化为可核验的算力业务机会</h2></div>
          <p>清单只保留当前基准经营与信贷情景下建议进入尽调的商品单元。当前公开数据尚未把它们对应到物理设施和资产权属，因此先做项目识别与证据补齐，不把它们包装成已落地项目。</p>
        </div>

        <div v-if="opportunityError" class="model-alert">{{ opportunityError }}</div>

        <div class="opportunity-metric-strip">
          <article><strong>{{ opportunityCoverage.opportunityCount ?? '—' }}</strong><span>当前候选</span><small>基准经营 + 基准信贷情景</small></article>
          <article><strong>{{ opportunityCoverage.priorityACount ?? '—' }}</strong><span>A级优先核验</span><small>按建议贷款额和NPV透明排序</small></article>
          <article><strong>{{ opportunityCoverage.identityPendingCount ?? '—' }}</strong><span>主体/设施待确认</span><small>不能直接解释为真实固定资产项目</small></article>
          <article><strong>{{ opportunityCoverage.openCheckCount ?? '—' }}</strong><span>待办尽调事项</span><small>优先关闭阻断性证据缺口</small></article>
        </div>

        <div v-if="selectedOpportunity" class="opportunity-board" :class="{ loading: opportunityLoading }">
          <aside class="opportunity-list">
            <header><span>OPPORTUNITY QUEUE</span><b>{{ financeOpportunities.length }} 个候选</b></header>
            <button v-for="item in financeOpportunities" :key="item.opportunityCode" type="button"
              :class="{ active: selectedOpportunityCode === item.opportunityCode }" @click="chooseOpportunity(item.opportunityCode)">
              <i :class="item.businessPriority === 'A' ? 'priority-a' : 'priority-b'">{{ item.businessPriority }}级</i>
              <strong>{{ item.productName }}</strong><small>{{ item.platformName }} · {{ formatWan(item.recommendedLoanYuan) }}</small>
            </button>
          </aside>

          <div class="opportunity-detail">
            <header class="opportunity-heading">
              <div><span>{{ selectedOpportunity.opportunityCode }} · {{ opportunityScope(selectedOpportunity.opportunityScope) }}</span><h3>{{ selectedOpportunity.opportunityName }}</h3><p>{{ selectedOpportunity.platformName }} · {{ selectedOpportunity.acceleratorModel || '配置待核验' }} · {{ selectedOpportunity.platformRegionLabel || '地域待核验' }}</p></div>
              <b :class="selectedOpportunity.businessPriority === 'A' ? 'positive' : 'pending'">{{ selectedOpportunity.businessPriority }}级 · {{ opportunityStatus(selectedOpportunity.opportunityStatus) }}</b>
            </header>

            <div class="opportunity-kpis">
              <article><span>情景CAPEX</span><strong>{{ formatWan(selectedOpportunity.totalCapexYuan) }}</strong><small>非设备报价</small></article>
              <article><span>NPV / IRR</span><strong>{{ formatWan(selectedOpportunity.npvYuan) }}</strong><small>IRR {{ formatPercent(selectedOpportunity.irr, 1) }}</small></article>
              <article><span>建议贷款额</span><strong>{{ formatWan(selectedOpportunity.recommendedLoanYuan) }}</strong><small>{{ formatPercent(selectedOpportunity.recommendedDebtRatio) }} · DSCR {{ formatRatio(selectedOpportunity.recommendedMinDscr) }}</small></article>
              <article><span>尽调缺口</span><strong>{{ selectedOpportunity.openCheckCount }}</strong><small>{{ selectedOpportunity.blockingCheckCount }} 项阻断性事项</small></article>
            </div>

            <div class="opportunity-context-grid">
              <article><span>项目身份</span><b>{{ projectIdentityStatus(selectedOpportunity.projectIdentityStatus) }}</b><p>{{ selectedOpportunity.policySummary }}</p></article>
              <article><span>首要动作</span><b>先确认资产与主体</b><p>{{ selectedOpportunity.primaryNextAction }}</p></article>
              <article><span>主要风险</span><b>公开数据不能替代合同</b><p>{{ selectedOpportunity.keyRiskSummary }}</p></article>
            </div>

            <div v-if="opportunityCandidateMappings.length" class="candidate-mapping-panel">
              <div class="candidate-mapping-heading"><div><span>PUBLIC INDICATIVE MAPPING</span><h4>商品的服务商与设施候选线索</h4></div><small>候选关联不写入商品的实体设施外键，不能直接用于能耗、抵押或政策测算。</small></div>
              <article v-for="mapping in opportunityCandidateMappings" :key="mapping.candidateMappingId">
                <div><span>{{ candidateMappingLabel(mapping.candidateMappingType) }}</span><b :class="candidateTone(mapping.confidenceLevel)">{{ candidateConfidence(mapping.confidenceLevel) }}</b></div>
                <div><strong>{{ mapping.candidateName }}</strong><p>{{ mapping.evidenceSummary }}</p></div>
                <div><p>{{ mapping.boundaryNote }}</p><a v-if="mapping.sourceUrl" :href="mapping.sourceUrl" target="_blank" rel="noreferrer">查看公开来源 ↗</a></div>
                <button v-if="mapping.candidateFacilityCode" type="button" @click="showFacilityCandidate(mapping.candidateFacilityCode)">查看设施画像 ↗</button>
              </article>
            </div>

            <div v-if="opportunityReferenceCases.length" class="reference-finance-panel">
              <div><span>PUBLIC FINANCING REFERENCE</span><h4>候选设施的已披露融资结构参照</h4></div>
              <article v-for="referenceCase in opportunityReferenceCases" :key="referenceCase.financingReferenceCaseId">
                <p><b>{{ referenceCase.facilityName }}</b> · {{ referenceCase.borrowerName }} · {{ referenceCase.lenderName }}</p>
                <dl><div><dt>原借款</dt><dd>{{ formatPrice(referenceCase.originalPrincipalWanyuan) }} 万元</dd></div><div><dt>期限</dt><dd>{{ referenceCase.termMonths }} 个月</dd></div><div><dt>披露余额</dt><dd>{{ formatPrice(referenceCase.outstandingBalanceWanyuan) }} 万元</dd></div><div><dt>余额时点</dt><dd>{{ referenceCase.balanceAsOfDate || '—' }}</dd></div></dl>
                <small>{{ referenceCase.collateralStructure }}</small><a v-if="referenceCase.sourceUrl" :href="referenceCase.sourceUrl" target="_blank" rel="noreferrer">查看交易所披露 ↗</a>
              </article>
            </div>

            <div class="opportunity-checklist">
              <div class="opportunity-checklist-heading"><div><span>DUE DILIGENCE CHECKLIST</span><h4>需要关闭的证据缺口</h4></div><small>政策支持仅在真实项目与材料可核验后进入独立情景</small></div>
              <article v-for="check in opportunityChecklist" :key="check.checklistId">
                <div><b :class="checklistTone(check.evidenceStatus)">{{ checklistStatus(check.evidenceStatus) }}</b><span :class="{ blocking: check.riskLevel === 'BLOCKING', high: check.riskLevel === 'HIGH' }">{{ check.riskLevel }}</span></div>
                <div><strong>{{ check.checkName }}</strong><p>{{ check.requiredEvidence }}</p></div>
                <div><span>下一步</span><p>{{ check.dueDiligenceAction }}</p></div>
                <div><span>牵头</span><p>{{ check.ownerRole }}</p></div>
              </article>
            </div>
          </div>
        </div>
      </section>

      <section v-if="isHome" id="finance" class="finance-section section-shell finance-preview-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>融资路径</p><h2>经营情景决定可进入尽调的项目范围</h2></div>
          <p>首页保留三档情景与一条当前优先线索；完整的参数、敏感性、DSCR 曲线和授信规则移至模型数据页。</p>
        </div>
        <div v-if="financeError" class="model-alert">{{ financeError }}</div>
        <div class="scenario-comparison compact-scenario-comparison">
          <article v-for="scenario in scenarioOptions" :key="scenario.version" :class="{ active: selectedScenarioVersion === scenario.version }">
            <span>{{ scenario.label }}经营情景</span><strong>{{ scenarioStat(scenario.version).nonnegativeNpvCount ?? '—' }}<small>/ 51</small></strong><p>单位项目 NPV ≥ 0</p><em>{{ scenarioStat(scenario.version).bankableCount ?? '—' }} 个通过经济性与 DSCR 初筛</em>
          </article>
        </div>
        <div v-if="selectedRecommendation" class="finance-preview-card">
          <div><span>当前优先线索</span><h3>{{ selectedRecommendation.productName }}</h3><p>{{ selectedRecommendation.platformName }} · {{ recommendationStatus(selectedRecommendation.recommendationStatus) }}</p></div>
          <dl><div><dt>情景 CAPEX</dt><dd>{{ formatWan(selectedRecommendation.totalCapexYuan) }}</dd></div><div><dt>建议贷款额</dt><dd>{{ formatWan(selectedRecommendation.recommendedLoanYuan) }}</dd></div><div><dt>最低 DSCR</dt><dd>{{ formatRatio(selectedRecommendation.recommendedMinDscr) }}</dd></div></dl>
        </div>
        <div class="preview-action-row"><p><b>结论只用于筛查。</b> 真实融资仍需以项目主体、合同收入、资产权属及银行授信规则为准。</p><button type="button" @click="openDetailPage('finance')">查看融资模型明细 <span>→</span></button></div>
      </section>

      <section v-else-if="activeDetailPage === 'finance'" id="finance" class="finance-section section-shell detail-data-section">
        <div class="section-heading">
          <div><p class="eyebrow"><span></span>银行视角 · 实时模型</p><h2>区分数学偿债能力与银行建议额度</h2></div>
          <p>先通过经营情景得到NPV和DSCR，再叠加收入折扣、资本金、合格CAPEX及贷款比例规则。最终结果只表示是否建议进入尽调。</p>
        </div>

        <div v-if="financeError" class="model-alert">{{ financeError }}</div>

        <div class="model-controls" aria-label="算力融资情景选择">
          <div>
            <span>经营情景</span>
            <button v-for="scenario in scenarioOptions" :key="scenario.version" type="button"
              :class="{ active: selectedScenarioVersion === scenario.version }" @click="chooseScenario(scenario.version)">
              <b>{{ scenario.label }}</b><small>{{ scenario.note }}</small>
            </button>
          </div>
          <div>
            <span>信贷规则</span>
            <button v-for="policy in creditPolicies" :key="policy.policyCode" type="button"
              :class="{ active: selectedPolicyCode === policy.policyCode }" @click="choosePolicy(policy.policyCode)">
              <b>{{ policy.policyName }}</b><small>上限 {{ formatPercent(policy.maxDebtRatio) }} · DSCR {{ formatRatio(policy.minDscr) }}</small>
            </button>
          </div>
        </div>

        <div class="scenario-comparison">
          <article v-for="scenario in scenarioOptions" :key="scenario.version" :class="{ active: selectedScenarioVersion === scenario.version }">
            <span>{{ scenario.label }}经营情景</span>
            <strong>{{ scenarioStat(scenario.version).nonnegativeNpvCount ?? '—' }}<small>/ 51</small></strong>
            <p>单位项目 NPV ≥ 0</p>
            <em>{{ scenarioStat(scenario.version).bankableCount ?? '—' }} 个通过当前信贷规则前的经济性与DSCR检查</em>
          </article>
        </div>

        <div v-if="selectedRecommendation" class="finance-dashboard" :class="{ loading: financeLoading }">
          <aside class="finance-project-list">
            <div><span>PRODUCT UNIT RESULTS</span><b>{{ bankRecommendations.length }} 个商品单位</b></div>
            <button v-for="item in bankRecommendations" :key="item.projectEconomicsResultId" type="button"
              :class="{ active: selectedRecommendationId === item.projectEconomicsResultId }"
              @click="chooseRecommendation(item.projectEconomicsResultId)">
              <span>{{ item.externalProductId }}</span><strong>{{ item.productName }}</strong>
              <small>{{ recommendationStatus(item.recommendationStatus) }}</small>
            </button>
          </aside>

          <div class="finance-model-detail">
            <header>
              <div><span>{{ selectedRecommendation.platformName }} · {{ selectedRecommendation.scenarioName }}</span><h3>{{ selectedRecommendation.productName }}</h3><p>{{ selectedRecommendation.acceleratorModel || '公开配置未完整披露' }}</p></div>
              <b :class="{ pass: selectedRecommendation.recommendationStatus === 'PROCEED_DUE_DILIGENCE' }">{{ recommendationStatus(selectedRecommendation.recommendationStatus) }}</b>
            </header>

            <div class="finance-kpis">
              <article><span>单位CAPEX</span><strong>{{ formatWan(selectedRecommendation.totalCapexYuan) }}</strong><small>SCENARIO</small></article>
              <article><span>NPV / IRR</span><strong>{{ formatWan(selectedRecommendation.npvYuan) }}</strong><small>IRR {{ formatPercent(selectedRecommendation.irr, 1) }}</small></article>
              <article><span>数学DSCR容量</span><strong>{{ formatPercent(selectedRecommendation.mathematicalDscrCapacityRatio) }}</strong><small>未叠加银行政策上限</small></article>
              <article class="recommended"><span>银行建议额度</span><strong>{{ formatWan(selectedRecommendation.recommendedLoanYuan) }}</strong><small>{{ formatPercent(selectedRecommendation.recommendedDebtRatio) }} · DSCR {{ formatRatio(selectedRecommendation.recommendedMinDscr) }}</small></article>
            </div>

            <div class="credit-rule-strip">
              <div><span>最高债务比例</span><b>{{ formatPercent(selectedPolicy?.maxDebtRatio) }}</b></div>
              <div><span>最低资本金</span><b>{{ formatPercent(selectedPolicy?.minEquityRatio) }}</b></div>
              <div><span>收入折扣</span><b>{{ formatPercent(selectedPolicy?.revenueHaircutRatio) }}</b></div>
              <div><span>最低DSCR</span><b>{{ formatRatio(selectedPolicy?.minDscr) }}</b></div>
              <p>最终约束：<strong>{{ selectedRecommendation.bindingRule }}</strong></p>
            </div>

            <div class="model-visual-grid">
              <article class="sensitivity-panel">
                <div class="visual-heading"><div><span>ROBUSTNESS</span><h4>NPV单变量敏感性</h4></div><small>基准参数逐项变化</small></div>
                <div v-if="sensitivityRows.length" class="sensitivity-bars">
                  <div v-for="row in sensitivityRows" :key="row.variableCode">
                    <span>{{ variableLabels[row.variableCode] || row.variableCode }}</span>
                    <i><b :class="row.sensitivityLevel.toLowerCase()" :style="{ width: sensitivityWidth(row.maxAbsNpvChangeRatio) }"></b></i>
                    <strong>{{ formatPercent(row.maxAbsNpvChangeRatio, 1) }}</strong><em :class="row.sensitivityLevel.toLowerCase()">{{ row.sensitivityLevel }}</em>
                  </div>
                </div>
                <p v-else>暂无该商品的敏感性结果。</p>
              </article>

              <article class="dscr-panel">
                <div class="visual-heading"><div><span>DEBT CAPACITY</span><h4>债务比例—最低DSCR</h4></div><small>1%—100%遍历</small></div>
                <svg viewBox="0 0 720 220" role="img" aria-label="债务比例与最低DSCR曲线">
                  <line x1="42" y1="180" x2="700" y2="180" class="axis" />
                  <line x1="42" y1="18" x2="42" y2="180" class="axis" />
                  <line x1="42" :y1="curveChart.thresholdY" x2="700" :y2="curveChart.thresholdY" class="threshold" />
                  <polyline v-if="curveChart.points" :points="curveChart.points" class="dscr-line" />
                  <line v-if="curveChart.recommendationX != null" :x1="curveChart.recommendationX" y1="18" :x2="curveChart.recommendationX" y2="180" class="recommend-line" />
                  <text x="42" y="204">0%</text><text x="356" y="204">50%</text><text x="680" y="204">100%</text>
                  <text x="50" :y="curveChart.thresholdY - 6">DSCR {{ formatRatio(selectedPolicy?.minDscr) }}</text>
                </svg>
                <div class="curve-legend"><span><i class="curve"></i>最低DSCR</span><span><i class="limit"></i>建议债务比例</span><span><i class="floor"></i>政策门槛</span></div>
              </article>
            </div>

            <div class="model-boundary"><b>模型边界</b><p>{{ selectedRecommendation.recommendationText }} 当前结果是单个商品配置的研究情景，不是整座算力中心的授信额度。</p></div>
          </div>
        </div>

        <div v-else-if="financeLoading" class="model-loading">正在读取算力经营、敏感性与融资结果…</div>

        <div class="pipeline">
          <article v-for="step in pipeline" :key="step.index"><span>{{ step.index }}</span><small>{{ step.tag }}</small><h3>{{ step.title }}</h3><p>{{ step.text }}</p></article>
        </div>
      </section>

      <section v-if="isHome" id="collaboration" class="integration-section">
        <div class="section-shell integration-layout">
          <div><p class="eyebrow"><span></span>算电协同 · 已接入</p><h2>不再只引用电力概念，而是把区域电力信号写入算力成本情景</h2><p>首个样本为百旺信三期：深圳分时电价直接形成现金流压力测试；绿电、储能和需求响应均保留合同或工程证据边界。</p><button class="button dark-button" type="button" @click="openDetailPage('synergy')">查看算电协同结果 <span>→</span></button></div>
          <div class="integration-stack">
            <article><b>01</b><div><strong>分时电价压力</strong><p v-if="homePowerSynergy">加权价 {{ formatPrice(homePowerSynergy.weightedTouPriceYuanKwh) }} 元/kWh；相对历史账单代理的现金流变化 {{ formatWan(homePowerSynergy.cashflowChangeFromReferenceYuan) }}。</p><p v-else>正在读取区域分时电价情景。</p></div></article>
            <article><b>02</b><div><strong>电源结构不等于绿电消费</strong><p>深圳本地清洁电源装机≥80%，广东2025年规上发电火电占比71.1%；两项均不替代设施绿电合同。</p></div></article>
            <article><b>03</b><div><strong>储能只作为工程情景</strong><p v-if="homePowerSynergy">2%移峰需要约 {{ formatKw(homePowerSynergy.requiredStoragePowerKw) }} / {{ formatMwh(homePowerSynergy.requiredStorageCapacityKwh) }}，CAPEX代理 {{ formatWan(homePowerSynergy.storageCapexProxyYuan) }}。</p><p v-else>需先读取储能工程情景。</p></div></article>
            <article><b>04</b><div><strong>需求响应不预填收益</strong><p>仅显示最大负荷5%资格门槛代理；未取得注册、能力测试和结算材料前，模型收益固定为0。</p></div></article>
          </div>
        </div>
      </section>

      <section v-if="isHome" id="trace" class="trace-section section-shell">
        <div><p class="eyebrow"><span></span>模型溯源</p><h2>每个结论都要知道来自事实、公开报价还是研究情景</h2></div>
        <div class="trace-grid"><article><span>PUBLIC FACT</span><strong>政府、运营主体及法定披露</strong><p>设施名称、状态、容量、PUE、投资等字段逐项保存来源。</p></article><article><span>PUBLIC SNAPSHOT</span><strong>公开平台API快照</strong><p>保留抓取时间、原始JSON、SHA-256和价格口径冲突。</p></article><article><span>SCENARIO</span><strong>后续研究情景</strong><p>设备功率、利用率与融资参数必须显式标注，不冒充企业实测。</p></article></div>
      </section>
    </main>

    <footer><span>算力能源金融机会分析平台 · V1 雏形</span><span>PUBLIC DATA + RESEARCH SCENARIO</span><a :href="powerSiteUrl">返回电力研究站 ↗</a></footer>

    <div v-if="formulaOpen" class="modal-backdrop" role="presentation" @click.self="formulaOpen = false">
      <section class="formula-modal" role="dialog" aria-modal="true" aria-labelledby="formula-title">
        <button type="button" aria-label="关闭" @click="formulaOpen = false">×</button><p>COMPUTE × ENERGY</p><h2 id="formula-title">算力与电力的核心连接公式</h2>
        <article><span>设施总功率</span><code>TotalPower = ITPower × PUE</code><p>IT设备功率乘以PUE，得到含制冷、供配电等辅助系统的设施总功率。</p></article>
        <article><span>单位算力电力成本</span><code>ElectricityCost / GPU-hour = EquipmentPower × PUE × Tariff</code><p>必须使用同一设备配置、负载水平和电价边界。</p></article>
        <article><span>年度算力收入</span><code>Revenue = SellableGPU × UtilizedHours × ContractPrice</code><p>网页商品卡数不能代替可售库存，参考价不能代替合同成交价。</p></article>
        <article><span>融资现金流</span><code>CFADS = Revenue − ElectricityCost − OtherOPEX − Tax</code><p>再进入电力网站现有的DSCR、债务比例和敏感性分析框架。</p></article>
        <div><b>研究边界</b><span>缺少项目实际数据时，只能形成情景结果，并明确标注 `SIMULATED/SCENARIO`。</span></div>
      </section>
    </div>

    <a
      class="ai-analysis-fab"
      :href="`${powerSiteUrl}/ai-assistant`"
      aria-label="进入 AI 分析"
    >
      <span class="ai-analysis-fab-mark" aria-hidden="true">✦</span>
      <span class="ai-analysis-fab-tooltip" role="tooltip">进入 AI 分析</span>
    </a>
  </div>
</template>
