<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { fetchReferenceData } from '../services/enterpriseApi'

const props = defineProps({ dataset: { type: String, required: true } })
const emit = defineEmits(['back'])
const originalTitle = document.title
const result = ref({ items: [], page: 0, size: 20, total: 0, totalPages: 0 })
const query = ref('')
const loading = ref(true)
const error = ref('')
const selected = ref(null)

const configurations = {
  'regional-power-statistics': {
    kicker: '表1 · 区域供需', accent: 'REGIONAL',
    columns: [
      ['statId', 'ID'], ['regionName', '地区'], ['year', '年度'], ['totalGenerationGwh', '发电量(GWh)', 'number'],
      ['totalConsumptionGwh', '用电量(GWh)', 'number'], ['secondaryIndustryGwh', '第二产业(GWh)', 'number'],
      ['tertiaryIndustryGwh', '第三产业(GWh)', 'number'], ['maxLoadMw', '最大负荷(MW)', 'number'],
      ['powerGrowthRate', '用电增速', 'percent'], ['dataQuality', '质量'], ['sourceTitle', '来源', 'link', 'sourceUrl'],
    ],
  },
  'electricity-tariff': {
    kicker: '表3 · 价格信号', accent: 'TARIFF',
    columns: [
      ['tariffId', 'ID'], ['regionName', '地区'], ['priceZone', '价区'], ['year', '年度'], ['month', '月份'],
      ['customerType', '用户类型'], ['voltageLevel', '电压等级'], ['marketType', '市场类型'], ['timePeriod', '时段'],
      ['startTimeText', '开始时间'], ['endTimeText', '结束时间'], ['finalPriceYuanKwh', '最终电价(元/kWh)', 'decimal4'],
      ['demandPrice', '需量单价', 'decimal4'], ['sourceTitle', '来源', 'link', 'sourceUrl'],
    ],
  },
  'power-market-trade': {
    kicker: '表4 · 市场交易', accent: 'TRADE',
    columns: [
      ['tradeId', 'ID'], ['regionName', '地区'], ['year', '年度'], ['month', '月份'], ['marketCategory', '市场类别'],
      ['tradeCycle', '周期'], ['tradeType', '交易类型'], ['energyType', '能源类型'],
      ['transactionVolumeGwh', '成交量(GWh)', 'number'], ['averagePriceYuanMwh', '均价(元/MWh)', 'decimal2'],
      ['weightedAvgPriceYuanMwh', '加权均价', 'decimal2'], ['dataQuality', '质量'], ['sourceTitle', '来源', 'link', 'sourceUrl'],
    ],
  },
  'policy-rules': {
    kicker: '表11 · 业务规则层', accent: 'POLICY',
    columns: [
      ['policyRuleId', 'ID'], ['ruleTitle', '规则名称'], ['applicableRegion', '适用地区'],
      ['applicableEntityType', '适用主体'], ['applicableAssetType', '适用资产'],
      ['ruleStatus', '状态'], ['interpretationConfidence', '解释置信度'], ['documentTitle', '政策文件', 'link', 'officialUrl'],
    ],
  },
}

const config = computed(() => configurations[props.dataset] || { kicker: '数据目录', accent: 'DATA', columns: [] })
const detailEntries = computed(() => selected.value ? Object.entries(selected.value).filter(([, value]) => value !== null && value !== '') : [])

function number(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '—'
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return String(value)
  return new Intl.NumberFormat('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(parsed)
}
function display(value, type) {
  if (value === null || value === undefined || value === '') return '—'
  if (type === 'number') return number(value, 2)
  if (type === 'decimal2') return number(value, 2)
  if (type === 'decimal4') return number(value, 4)
  if (type === 'percent') return `${number(Number(value) * 100, 2)}%`
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}
function fieldLabel(key) { return config.value.columns.find((column) => column[0] === key)?.[1] || key }

async function load(page = 0) {
  loading.value = true; error.value = ''; selected.value = null
  try {
    result.value = await fetchReferenceData(props.dataset, { query: query.value.trim(), page, size: 20 })
    document.title = `${result.value.title}｜电力能源金融机会分析平台`
  } catch (exception) { error.value = exception.message }
  finally { loading.value = false }
}
function search() { load(0) }
function reset() { query.value = ''; load(0) }

onMounted(() => load(0))
watch(() => props.dataset, () => { query.value = ''; load(0) })
onBeforeUnmount(() => { document.title = originalTitle })
</script>

<template>
  <div class="catalog-page">
    <header class="detail-site-header"><div class="detail-topbar">
      <button class="brand" type="button" aria-label="返回平台首页" @click="emit('back')"><span class="brand-mark"><i></i><i></i><i></i></span><span><strong>电力能源金融</strong><small>基础数据目录</small></span></button>
      <div class="detail-breadcrumb"><span>市场与政策数据</span><b>/</b><strong>{{ result.title || dataset }}</strong></div>
      <button class="detail-back-button" type="button" @click="emit('back')">← 返回首页</button>
    </div></header>

    <main class="catalog-shell">
      <section class="catalog-hero">
        <div><p>{{ config.kicker }}</p><h1>{{ result.title || '正在读取数据' }}</h1><span>{{ result.subtitle }}</span></div>
        <aside><small>数据库记录</small><strong>{{ number(result.total, 0) }}</strong><em>{{ config.accent }}</em></aside>
      </section>

      <section class="catalog-toolbar">
        <form @submit.prevent="search"><label><span>⌕</span><input v-model="query" type="search" placeholder="搜索地区、年度、类型、来源或规则关键词" /></label><button type="submit">搜索</button><button v-if="query" class="secondary" type="button" @click="reset">清除</button></form>
        <p>第 {{ result.totalPages ? result.page + 1 : 0 }} / {{ result.totalPages }} 页 · 每页 {{ result.size }} 条</p>
      </section>

      <div v-if="error" class="enterprise-api-warning">{{ error }}</div>
      <div v-if="loading" class="catalog-loading"><span></span><p>正在通过 Java API 查询 MySQL</p></div>
      <section v-else class="catalog-table-card">
        <div class="catalog-table-scroll"><table><thead><tr><th v-for="column in config.columns" :key="column[0]">{{ column[1] }}</th></tr></thead>
          <tbody><tr v-for="row in result.items" :key="`${dataset}-${row[config.columns[0]?.[0]]}`" :class="{ selected: selected === row }" @click="selected = row">
            <td v-for="column in config.columns" :key="column[0]">
              <a v-if="column[2] === 'link' && row[column[3]]" :href="row[column[3]]" target="_blank" rel="noreferrer" @click.stop>{{ display(row[column[0]]) }} ↗</a>
              <span v-else>{{ display(row[column[0]], column[2]) }}</span>
            </td>
          </tr><tr v-if="result.items.length === 0"><td :colspan="config.columns.length">没有找到匹配记录</td></tr></tbody>
        </table></div>
        <footer class="catalog-pagination"><button :disabled="result.page === 0 || loading" @click="load(result.page - 1)">← 上一页</button><span>共 {{ number(result.total, 0) }} 条</span><button :disabled="result.page + 1 >= result.totalPages || loading" @click="load(result.page + 1)">下一页 →</button></footer>
      </section>

      <section v-if="selected" class="catalog-record-detail">
        <div class="catalog-detail-heading"><div><p>完整数据库记录</p><h2>{{ display(selected[config.columns[0]?.[0]]) }} · {{ display(selected[config.columns[2]?.[0]]) }}</h2></div><button type="button" @click="selected = null">关闭</button></div>
        <dl><div v-for="entry in detailEntries" :key="entry[0]"><dt>{{ fieldLabel(entry[0]) }}</dt><dd><a v-if="String(entry[0]).toLowerCase().includes('url')" :href="entry[1]" target="_blank" rel="noreferrer">{{ entry[1] }}</a><span v-else>{{ display(entry[1]) }}</span></dd></div></dl>
      </section>

      <section class="catalog-boundary"><b>数据说明</b><p>页面直接读取数据库活动记录。来源链接指向已保存的公开出处；派生字段、单位换算、质量等级与备注按数据库原值展示。政策规则是研究提取结果，不能替代正式政策原文或项目资格审核。</p></section>
    </main>
    <footer class="enterprise-detail-footer"><span>SPDB POWER FINANCE · REFERENCE DATA</span><span>JAVA API · MYSQL READ ONLY</span></footer>
  </div>
</template>
