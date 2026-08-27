<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { fetchPowerSourceOverview } from '../services/enterpriseApi'

const records = ref([])
const modelVersion = ref('V2.0')
const boundary = ref('')
const loading = ref(true)
const error = ref('')
const selectedRegion = ref('CN')
const selectedDatasetKey = ref('')

const regions = [
  { code: 'CN', label: '全国' },
  { code: 'GD', label: '广东省' },
  { code: 'SZ', label: '深圳市' },
]

const energyColors = {
  THERMAL: '#526578', COAL: '#526578', GAS: '#7390a5', NUCLEAR: '#8d7bb0',
  HYDRO: '#50a9c2', WIND: '#4db5a7', SOLAR: '#e4b957', BIOMASS: '#79a978',
  BIOMASS_OTHER: '#87a08a', STORAGE: '#6f91c6', OTHER: '#aeb9bf',
  RENEWABLE_OTHER: '#71a79d', CLEAN_ENERGY_TOTAL: '#55b9ae', UNKNOWN: '#dfe6e8',
}

function datasetKey(row) {
  return `${row.statYear}|${row.metricBasis}|${row.scopeCode}`
}

function basisName(basis) {
  return {
    INSTALLED_CAPACITY: '装机结构',
    GROSS_GENERATION: '发电结构',
    DISCLOSED_SHARE: '公开占比',
  }[basis] || basis
}

const regionRecords = computed(() => records.value.filter((row) => row.regionCode === selectedRegion.value))
const datasetOptions = computed(() => {
  const seen = new Set()
  return regionRecords.value
    .slice()
    .sort((a, b) => Number(b.statYear) - Number(a.statYear)
      || ['DISCLOSED_SHARE', 'INSTALLED_CAPACITY', 'GROSS_GENERATION'].indexOf(a.metricBasis)
      - ['DISCLOSED_SHARE', 'INSTALLED_CAPACITY', 'GROSS_GENERATION'].indexOf(b.metricBasis))
    .filter((row) => {
      const key = datasetKey(row)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .map((row) => ({
      key: datasetKey(row),
      year: row.statYear,
      basis: row.metricBasis,
      label: `${row.statYear} · ${basisName(row.metricBasis)}`,
    }))
})

const activeRows = computed(() => regionRecords.value.filter((row) => datasetKey(row) === selectedDatasetKey.value))
const activeRecord = computed(() => activeRows.value[0] || {})
const totalRow = computed(() => activeRows.value.find((row) => Number(row.isTotal) === 1))
const componentRows = computed(() => activeRows.value
  .filter((row) => Number(row.isTotal) !== 1 && row.shareRatio != null && row.disclosureStatus !== 'NOT_DISCLOSED')
  .sort((a, b) => Number(b.shareRatio) - Number(a.shareRatio)))

const segments = computed(() => {
  const known = componentRows.value.map((row) => ({
    code: row.energyTypeCode,
    label: row.energyTypeName,
    share: Number(row.shareRatio),
    operator: row.valueOperator,
    color: energyColors[row.energyTypeCode] || '#8ca2ad',
  }))
  const used = known.reduce((sum, row) => sum + row.share, 0)
  if (used < 0.999) known.push({ code: 'UNKNOWN', label: '其余／未披露', share: 1 - used, operator: 'LE', color: energyColors.UNKNOWN })
  return known
})

const activeRegion = computed(() => regions.find((region) => region.code === selectedRegion.value) || regions[0])
const sourceRow = computed(() => activeRows.value.find((row) => row.sourceTitle) || {})
const isPartialShare = computed(() => activeRecord.value.metricBasis === 'DISCLOSED_SHARE')

function sumFlag(flag) {
  return componentRows.value.reduce((sum, row) => Number(row[flag]) === 1 ? sum + Number(row.shareRatio || 0) : sum, 0)
}

const fossilShare = computed(() => sumFlag('isFossil'))
const cleanShare = computed(() => isPartialShare.value
  ? Number(componentRows.value.find((row) => row.energyTypeCode === 'CLEAN_ENERGY_TOTAL')?.shareRatio || 0)
  : sumFlag('isCleanEnergy'))
const renewableShare = computed(() => sumFlag('isRenewable'))
const windSolarShare = computed(() => componentRows.value
  .filter((row) => ['WIND', 'SOLAR'].includes(row.energyTypeCode))
  .reduce((sum, row) => sum + Number(row.shareRatio || 0), 0))

const financeObservation = computed(() => {
  if (selectedRegion.value === 'CN' && activeRecord.value.metricBasis === 'INSTALLED_CAPACITY') {
    return `风光装机合计${formatPercent(windSolarShare.value)}，已高于火电装机；但装机不等于实际发电，新能源建设和系统调节能力应分开评估。`
  }
  if (selectedRegion.value === 'CN') return '发电量中火电仍承担主要支撑作用，融资判断应同时关注新能源增量与传统机组灵活性改造。'
  if (selectedRegion.value === 'GD' && activeRecord.value.metricBasis === 'INSTALLED_CAPACITY') {
    return `风光装机合计${formatPercent(windSolarShare.value)}，已接近并略高于煤电；新增资本机会更偏向新能源、储能与调节性电源。`
  }
  if (selectedRegion.value === 'GD') return '广东规上发电仍以火电为主，火电利用、燃料成本和容量补偿会影响电厂现金流稳定性。'
  if (isPartialShare.value) return '当前只能确认本地清洁装机超过80%，不能据此推导深圳全市用电来源；项目融资仍需补充受电结构。'
  return '2023年数据反映深圳本地发电生产结构，不代表深圳企业实际消费电力的来源构成。'
})

const trendYears = computed(() => {
  if (!activeRecord.value.metricBasis || isPartialShare.value) return []
  return [...new Set(regionRecords.value
    .filter((row) => row.metricBasis === activeRecord.value.metricBasis && row.scopeCode === activeRecord.value.scopeCode)
    .map((row) => Number(row.statYear)))]
    .sort((a, b) => a - b)
})

function trendSegments(year) {
  const rows = regionRecords.value
    .filter((row) => Number(row.statYear) === year && row.metricBasis === activeRecord.value.metricBasis
      && row.scopeCode === activeRecord.value.scopeCode && Number(row.isTotal) !== 1
      && row.shareRatio != null && row.disclosureStatus !== 'NOT_DISCLOSED')
    .sort((a, b) => Number(b.shareRatio) - Number(a.shareRatio))
  return rows.map((row) => ({
    code: row.energyTypeCode,
    label: row.energyTypeName,
    share: Number(row.shareRatio),
    color: energyColors[row.energyTypeCode] || '#8ca2ad',
  }))
}

function formatPercent(value, operator = 'EQ') {
  const prefix = operator === 'GT' ? '>' : operator === 'GE' ? '≥' : operator === 'LT' ? '<' : operator === 'LE' ? '≤' : ''
  return `${prefix}${(Number(value || 0) * 100).toFixed(1)}%`
}

function formatMetric(row) {
  if (!row || row.metricValue == null) return row?.disclosureStatus === 'NOT_DISCLOSED' ? '未披露' : '未披露总量'
  const value = Number(row.metricValue)
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value)} ${row.metricUnit || ''}`
}

function selectRegion(code) {
  selectedRegion.value = code
}

watch([selectedRegion, datasetOptions], () => {
  if (!datasetOptions.value.some((option) => option.key === selectedDatasetKey.value)) {
    selectedDatasetKey.value = datasetOptions.value[0]?.key || ''
  }
}, { immediate: true })

onMounted(async () => {
  try {
    const data = await fetchPowerSourceOverview()
    records.value = data.records || []
    modelVersion.value = data.modelVersion || 'V2.0'
    boundary.value = data.boundary || ''
  } catch (exception) {
    error.value = exception.message
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <section id="energy-mix" class="energy-structure-section">
    <div class="section-shell">
      <div class="energy-structure-heading">
        <div>
          <p class="eyebrow"><span></span> 第一层：宏观能源结构</p>
          <h2>先看电从哪里来，<br />再判断资本投向哪里。</h2>
        </div>
        <p>装机结构反映长期建设方向，发电结构反映实际出力。两者结合，才能识别新能源建设、传统电源改造、储能和电网灵活性机会。</p>
      </div>

      <div v-if="loading" class="energy-structure-state">正在读取电源结构 V2…</div>
      <div v-else-if="error" class="energy-structure-state error">电源结构暂时无法读取：{{ error }}</div>

      <div v-else class="energy-structure-board">
        <div class="energy-structure-controls">
          <div class="region-switch" role="tablist" aria-label="选择区域">
            <button v-for="region in regions" :key="region.code" type="button"
              :class="{ active: selectedRegion === region.code }" :aria-selected="selectedRegion === region.code"
              role="tab" @click="selectRegion(region.code)">
              <span>{{ region.code }}</span>{{ region.label }}
            </button>
          </div>
          <div class="basis-switch" aria-label="选择统计口径">
            <button v-for="option in datasetOptions" :key="option.key" type="button"
              :class="{ active: selectedDatasetKey === option.key }" @click="selectedDatasetKey = option.key">
              {{ option.label }}
            </button>
          </div>
          <span class="energy-version">{{ modelVersion }}</span>
        </div>

        <div class="energy-structure-main">
          <article class="energy-chart-card">
            <div class="energy-card-heading">
              <div><small>{{ activeRegion.label }} · {{ basisName(activeRecord.metricBasis) }}</small><h3>{{ activeRecord.statisticalScope }}</h3></div>
              <div class="energy-total"><span>统计总量</span><strong>{{ formatMetric(totalRow) }}</strong></div>
            </div>

            <div class="energy-stack" :aria-label="`${activeRegion.label}${activeRecord.statYear}年${basisName(activeRecord.metricBasis)}`">
              <span v-for="segment in segments" :key="segment.code" :style="{ width: `${segment.share * 100}%`, background: segment.color }"
                :title="`${segment.label} ${formatPercent(segment.share, segment.operator)}`"></span>
            </div>

            <div class="energy-legend">
              <article v-for="row in componentRows" :key="row.energyTypeCode">
                <i :style="{ background: energyColors[row.energyTypeCode] || '#8ca2ad' }"></i>
                <div><span>{{ row.energyTypeName }}</span><small>{{ formatMetric(row) }}</small></div>
                <strong>{{ formatPercent(row.shareRatio, row.valueOperator) }}</strong>
              </article>
              <article v-if="segments.some((segment) => segment.code === 'UNKNOWN')" class="unknown">
                <i :style="{ background: energyColors.UNKNOWN }"></i>
                <div><span>其余／未披露</span><small>不进行无依据拆分</small></div>
                <strong>{{ formatPercent(segments.find((segment) => segment.code === 'UNKNOWN').share, 'LE') }}</strong>
              </article>
            </div>

            <div v-if="trendYears.length > 1" class="energy-trend">
              <div class="energy-trend-title"><span>2020—2025结构变化</span><small>相同统计口径</small></div>
              <div v-for="year in trendYears" :key="year" class="trend-row">
                <b>{{ year }}</b>
                <div><span v-for="segment in trendSegments(year)" :key="segment.code"
                  :style="{ width: `${segment.share * 100}%`, background: segment.color }"
                  :title="`${segment.label} ${formatPercent(segment.share)}`"></span></div>
              </div>
            </div>
          </article>

          <aside class="energy-insight-card">
            <p>结构信号</p>
            <h3>{{ activeRegion.label }}的能源结构意味着什么？</h3>
            <dl>
              <div><dt>传统电源占比</dt><dd>{{ isPartialShare ? '未拆分' : formatPercent(fossilShare) }}</dd></div>
              <div><dt>清洁能源占比</dt><dd>{{ formatPercent(cleanShare, isPartialShare ? 'GT' : 'EQ') }}</dd></div>
              <div><dt>可再生能源占比</dt><dd>{{ isPartialShare ? '未拆分' : formatPercent(renewableShare) }}</dd></div>
            </dl>
            <div class="energy-finance-note"><span>银行观察</span><p>{{ financeObservation }}</p></div>
            <div class="energy-source">
              <span>数据来源 · {{ sourceRow.dataQuality || '—' }}级 · {{ sourceRow.confidenceLevel || '—' }}</span>
              <a v-if="sourceRow.sourceUrl" :href="sourceRow.sourceUrl" target="_blank" rel="noreferrer">{{ sourceRow.sourceTitle }} ↗</a>
              <b v-else>{{ sourceRow.sourceTitle || '来源待补充' }}</b>
            </div>
          </aside>
        </div>

        <div class="energy-boundary"><b>口径边界</b><p>{{ boundary }} 当前图表不会把未披露值自动视为0。</p></div>
      </div>
    </div>
  </section>
</template>
