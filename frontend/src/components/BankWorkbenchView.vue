<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchBankWorkbench } from '../services/enterpriseApi'

const props = defineProps({
  computeSiteUrl: { type: String, required: true },
  powerSiteUrl: { type: String, required: true },
})
const emit = defineEmits(['back', 'open-enterprise'])

const loading = ref(true)
const error = ref('')
const data = ref(null)
const selectedTrack = ref('ALL')
const query = ref('')

const allItems = computed(() => {
  const power = (data.value?.powerItems || []).map((item) => ({ ...item, key: `POWER-${item.companyId}` }))
  const compute = [
    ...(data.value?.computeProject ? [{ ...data.value.computeProject, key: 'COMPUTE-BWX-PHASE3', title: '百旺信云数据中心三期' }] : []),
    ...(data.value?.computeCandidates || []).map((item) => ({ ...item, key: `COMPUTE-${item.opportunityCode}` })),
  ]
  return [...power, ...compute]
})

const filteredItems = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return allItems.value.filter((item) => {
    if (selectedTrack.value !== 'ALL' && item.track !== selectedTrack.value) return false
    if (!keyword) return true
    return [item.companyName, item.title, item.officialName, item.industryName, item.recommendedProduct]
      .filter(Boolean).join(' ').toLowerCase().includes(keyword)
  })
})

const powerItems = computed(() => allItems.value.filter((item) => item.track === 'POWER'))
const computeItem = computed(() => allItems.value.find((item) => item.track === 'COMPUTE'))

function amount(value, digits = 0) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '—'
  return new Intl.NumberFormat('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(number)
}

function percent(value, digits = 1) {
  const number = Number(value)
  return Number.isFinite(number) ? `${(number * 100).toFixed(digits)}%` : '—'
}

function decimal(value, digits = 2) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '—'
}

function labelForSource(value) {
  return {
    PUBLIC: '公开事实',
    'PUBLIC + SCENARIO': '公开 + 情景',
    SCENARIO: '研究情景',
    'TO BE VERIFIED': '待核验',
  }[value] || value || '待核验'
}

function sourceTone(value) {
  return {
    PUBLIC: 'public',
    'PUBLIC + SCENARIO': 'mixed',
    SCENARIO: 'scenario',
  }[value] || 'unknown'
}

function labelForPriority(value) {
  return value ? `${value}级优先` : '待排序'
}

function labelForOpportunity(value) {
  return {
    HIGH: '高机会',
    MEDIUM: '中机会',
    LOW: '低机会',
    DUE_DILIGENCE: '尽调优先',
  }[value] || '待评估'
}

function openItem(item) {
  if (item.track === 'COMPUTE') return
  emit('open-enterprise', item.companyId)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchBankWorkbench()
  } catch (exception) {
    error.value = exception.message || '工作台数据暂时无法读取。'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <main class="workbench-shell">
    <header class="workbench-header">
      <div class="workbench-topbar">
        <button class="workbench-brand" type="button" @click="emit('back')">
          <span class="workbench-mark" aria-hidden="true"><i></i><i></i><i></i></span>
          <span><strong>电力能源金融</strong><small>银行客户经理工作台</small></span>
        </button>
        <div class="workbench-sites" aria-label="研究站点切换">
          <b>银行工作台</b>
          <a :href="powerSiteUrl" title="进入电力研究">电力研究</a>
          <a :href="computeSiteUrl" title="进入算力研究">算力研究</a>
        </div>
      </div>
    </header>

    <section class="workbench-hero">
      <div>
        <p>RELATIONSHIP MANAGER DESK · READ ONLY</p>
        <h1>把研究结果变成<br /><em>可执行的客户行动。</em></h1>
        <span>统一呈现电力侧重点企业与算力侧真实项目样本；先看可谈方向，再看数据依据和需补材料。</span>
      </div>
      <aside>
        <span>当前结果版本</span>
        <strong>{{ data?.activeRun?.runName || '正在读取' }}</strong>
        <small>{{ data?.activeRun?.analysisYear || '—' }} 年电力快照 · 算力项目按最新公开证据</small>
      </aside>
    </section>

    <section v-if="loading" class="workbench-state">正在汇总研究结果与尽调状态…</section>
    <section v-else-if="error" class="workbench-state error"><p>{{ error }}</p><button type="button" @click="load">重新读取</button></section>

    <template v-else>
      <section class="summary-strip" aria-label="工作台概览">
        <article><span>电力重点客户</span><strong>{{ data.summary.powerCandidateCount }}</strong><small>{{ data.summary.powerModelledCount }} 家已具备模型快照</small></article>
        <article><span>电力A级线索</span><strong>{{ data.summary.powerPriorityACount }}</strong><small>按当前快照的业务优先级</small></article>
        <article><span>算力重点客户</span><strong>{{ data.summary.computeFocusCustomerCount }}</strong><small>百旺信三期 · 公开项目样本</small></article>
        <article class="warning"><span>算力A级线索</span><strong>{{ data.summary.computePriorityACount }}</strong><small>公开商品候选 · 需先完成尽调</small></article>
      </section>

      <section class="action-grid">
        <article>
          <span>01 · 先约谈什么</span>
          <h2>已有模型快照的电力客户</h2>
          <p>优先围绕电费结构、储能工程条件和项目主体开展首次拜访。数值仅是模型筛选结果，不能直接作为报价或授信结论。</p>
          <button type="button" @click="selectedTrack = 'POWER'">查看电力客户 {{ powerItems.length }} 家 →</button>
        </article>
        <article class="compute-action">
          <span>02 · 先尽调什么</span>
          <h2>百旺信云数据中心三期</h2>
          <p>物理边界、投资、PUE与能耗锚点已披露；项目级收入、成本、回款和债务本息仍是获得授信测算的关键缺口。</p>
          <a :href="`${computeSiteUrl}/due-diligence/baiwangxin-phase3`">进入三期尽调状态 →</a>
        </article>
        <article class="discipline-action">
          <span>03 · 使用纪律</span>
          <h2>先区分事实，再使用模型</h2>
          <p><b>公开事实</b>可用于初筛；<b>公开+情景</b>用于测算讨论；<b>研究情景</b>只用于排优先级，必须由客户资料校准。</p>
        </article>
      </section>

      <section class="queue-section">
        <header class="queue-heading">
          <div><span>UNIFIED ACTION QUEUE</span><h2>客户与项目机会队列</h2><p>每个赛道优先展示 3 条线索；点击进入详情，不在本页重复展开全部底层数据。</p></div>
          <div class="queue-tools">
            <div class="track-filter" aria-label="赛道筛选">
              <button :class="{ active: selectedTrack === 'ALL' }" type="button" @click="selectedTrack = 'ALL'">全部</button>
              <button :class="{ active: selectedTrack === 'POWER' }" type="button" @click="selectedTrack = 'POWER'">电力</button>
              <button :class="{ active: selectedTrack === 'COMPUTE' }" type="button" @click="selectedTrack = 'COMPUTE'">算力</button>
            </div>
            <label><span class="sr-only">搜索客户或项目</span><input v-model="query" type="search" placeholder="搜索客户或项目" /></label>
          </div>
        </header>

        <div class="queue-table" role="table" aria-label="客户与项目机会队列">
          <div class="queue-row queue-labels" role="row"><span>对象</span><span>当前业务方向</span><span>核心指标</span><span>数据与阻断项</span><span>行动</span></div>

          <article v-for="item in filteredItems" :key="item.key" class="queue-row" :class="item.track.toLowerCase()" role="row">
            <div class="subject-cell" role="cell">
              <span class="track-tag">{{ item.track === 'POWER' ? '电力' : '算力' }}</span>
              <strong>{{ item.companyName || item.title }}</strong>
              <small>{{ item.industryName || '数据中心基础设施 · 三期项目' }} · {{ item.companyId || item.facilityCode }}</small>
              <div><em :class="item.businessPriority === 'A' ? 'priority-a' : ''">{{ labelForPriority(item.businessPriority) }}</em><em :class="item.opportunityLevel === 'DUE_DILIGENCE' ? 'due' : ''">{{ labelForOpportunity(item.opportunityLevel) }}</em></div>
            </div>

            <div class="direction-cell" role="cell"><b>{{ item.recommendedProduct }}</b><p>{{ item.recommendationText || '公共事实与三期项目尽调样本；需要用项目级材料更新测算。' }}</p></div>

            <div class="metric-cell" role="cell">
              <template v-if="item.track === 'POWER' && item.modelAvailable">
                <span>模型NPV</span><strong>{{ amount(item.npvWanyuan) }} 万元</strong>
                <small>最低 DSCR {{ decimal(item.baseMinDscr) }} · 模型最大贷款 {{ amount(item.maxLoanAmountWanyuan) }} 万元</small>
              </template>
              <template v-else-if="item.computeKind === 'PROJECT'">
                <span>公开经营锚点</span><strong>上架率 {{ percent(item.wholeFacility2025RackUtilizationRatio, 2) }}</strong>
                <small>2025年1+4栋自建托管收入 {{ amount(item.wholeFacility2025HostingRevenueWanyuan) }} 万元</small>
              </template>
              <template v-else-if="item.track === 'COMPUTE'">
                <span>研究模型</span><strong>NPV {{ amount(item.npvYuan / 10000) }} 万元</strong>
                <small>最低 DSCR {{ decimal(item.recommendedMinDscr) }} · 建议贷款 {{ amount(item.recommendedLoanYuan / 10000) }} 万元</small>
              </template>
              <template v-else>
                <span>当前状态</span><strong>待建模</strong><small>尚未形成项目级储能与融资测算</small>
              </template>
            </div>

            <div class="evidence-cell" role="cell"><b :class="['source-badge', sourceTone(item.dataBasis)]">{{ labelForSource(item.dataBasis) }}</b><p>{{ item.blockingSummary }}</p><small>{{ item.dataExplanation }}</small></div>

            <div class="open-cell" role="cell">
              <button v-if="item.track === 'POWER'" type="button" @click="openItem(item)">查看企业 →</button>
              <a v-else-if="item.computeKind === 'PROJECT'" :href="`${computeSiteUrl}/due-diligence/baiwangxin-phase3`">查看尽调 →</a>
              <a v-else :href="`${computeSiteUrl}/opportunities`">查看线索 →</a>
              <p>{{ item.nextAction }}</p>
            </div>
          </article>

          <p v-if="!filteredItems.length" class="empty-state">未找到匹配的客户或项目。</p>
        </div>
      </section>

      <section v-if="computeItem" class="compute-detail-strip">
        <div><span>COMPUTE CASE · PUBLIC FACTS + SCENARIO BOUNDARY</span><h2>百旺信三期：已可做什么，尚不能做什么？</h2></div>
        <dl>
          <div><dt>公开历史投资</dt><dd>{{ amount(computeItem.referenceHistoricalCapexYuan / 10000) }} 万元</dd></div>
          <div><dt>公开PUE锚点</dt><dd>{{ decimal(computeItem.referencePue, 3) }}</dd></div>
          <div><dt>公开年电量边界</dt><dd>{{ amount(computeItem.referenceAnnualEnergyCapKwh / 10000) }} 万kWh</dd></div>
          <div><dt>三期实际CFADS</dt><dd class="pending">待补</dd></div>
        </dl>
        <p>可用于安排项目尽调、核验资金用途和梳理潜在绿色金融方向；不可据此形成项目级DSCR、最终贷款额度或授信结论。</p>
      </section>

      <p class="workbench-boundary"><b>使用边界</b>{{ data.boundary }}</p>
    </template>
  </main>
</template>

<style scoped>
.workbench-shell { min-height: 100vh; color: #1d344b; background: #f4f7f8; }
.workbench-header { position: sticky; top: 0; z-index: 100; border-bottom: 1px solid rgba(209, 222, 229, .72); background: rgba(245, 247, 250, .94); box-shadow: 0 7px 21px rgba(16, 42, 69, .06); backdrop-filter: blur(14px); }
.workbench-topbar { display: flex; align-items: center; gap: 17px; min-height: 68px; width: min(1220px, calc(100% - 56px)); margin: 0 auto; }
.workbench-brand { display: flex; gap: 11px; align-items: center; padding: 0; border: 0; color: #10233c; background: transparent; cursor: pointer; text-align: left; }.workbench-brand strong { display: block; font-size: 15px; }.workbench-brand small { display: block; margin-top: 3px; color: #6d7f8b; font-size: 10px; letter-spacing: .14em; }.workbench-mark { display: flex; align-items: flex-end; gap: 3px; width: 29px; height: 29px; padding: 4px; border-radius: 7px; background: #143a58; }.workbench-mark i { flex: 1; height: 42%; background: #6ee0d7; border-radius: 1px; }.workbench-mark i:nth-child(2) { height: 72%; }.workbench-mark i:nth-child(3) { height: 100%; background: #e8f6f5; }
.workbench-sites { display: flex; margin-left: auto; padding: 3px; border: 1px solid #d7e4e7; border-radius: 999px; background: #fff; font-size: 11px; white-space: nowrap; }.workbench-sites b,.workbench-sites a { padding: 7px 10px; border-radius: 999px; }.workbench-sites b { color: #fff; background: #143a58; }.workbench-sites a { color: #466175; text-decoration: none; }.workbench-sites a:hover { color: #143a58; background: #edf4f5; }
.workbench-hero { display: grid; grid-template-columns: 1.2fr .8fr; gap: 46px; align-items: end; padding: 58px max(28px, calc((100vw - 1180px) / 2)) 52px; color: #ecf7f7; background: linear-gradient(115deg, #0e2947, #163f58); }.workbench-hero p { margin: 0 0 14px; color: #73d7cf; font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .08em; }.workbench-hero h1 { margin: 0; max-width: 760px; color: #f6fafb; font-size: clamp(35px, 4vw, 55px); line-height: 1.12; letter-spacing: -.045em; }.workbench-hero h1 em { color: #77ded4; font-style: normal; }.workbench-hero > div > span { display: block; max-width: 680px; margin-top: 19px; color: #b2cad3; font-size: 15px; line-height: 1.8; }.workbench-hero aside { padding: 21px; border: 1px solid rgba(197,230,232,.2); background: rgba(3,24,42,.28); }.workbench-hero aside > span { color: #8ab4c4; font-size: 11px; }.workbench-hero aside strong { display: block; margin: 10px 0 7px; color: #76ded4; font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; }.workbench-hero aside small { color: #b5cbd3; font-size: 11px; line-height: 1.6; }
.summary-strip,.action-grid,.queue-section,.compute-detail-strip,.workbench-boundary { width: min(1180px, calc(100% - 64px)); margin-right: auto; margin-left: auto; }.summary-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; margin-top: -1px; border: 1px solid #d9e5e8; background: #d9e5e8; }.summary-strip article { min-height: 132px; padding: 20px; background: #fff; }.summary-strip span { color: #75909d; font-size: 11px; }.summary-strip strong { display: block; margin: 11px 0 7px; color: #244b62; font-size: 34px; letter-spacing: -.04em; }.summary-strip small { color: #83949d; font-size: 11px; }.summary-strip .warning strong { color: #ad7624; }
.action-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; padding: 48px 0; }.action-grid article { min-height: 232px; padding: 24px; border: 1px solid #dbe6e9; border-radius: 8px; background: #fff; }.action-grid span { color: #468f8a; font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; }.action-grid h2 { margin: 17px 0 11px; color: #23445d; font-size: 21px; line-height: 1.35; }.action-grid p { margin: 0; color: #708692; font-size: 12px; line-height: 1.75; }.action-grid button,.action-grid a { display: inline-block; margin-top: 16px; padding: 0; border: 0; color: #337c77; background: transparent; cursor: pointer; font-size: 12px; font-weight: 700; text-decoration: none; }.compute-action { border-color: #b7dcd8 !important; background: #f5fbfa !important; }.discipline-action { background: #fafbfc !important; }.discipline-action b { color: #416477; }
.queue-section { padding: 31px; border: 1px solid #d7e3e6; border-radius: 10px; background: #fff; }.queue-heading { display: flex; justify-content: space-between; gap: 30px; align-items: end; margin-bottom: 24px; }.queue-heading > div > span,.compute-detail-strip > div > span { color: #41918a; font: 11px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .06em; }.queue-heading h2,.compute-detail-strip h2 { margin: 8px 0 6px; color: #213f56; font-size: 28px; letter-spacing: -.025em; }.queue-heading p { margin: 0; color: #718692; font-size: 12px; }.queue-tools { display: flex; gap: 10px; align-items: center; }.track-filter { display: flex; padding: 3px; border: 1px solid #d8e4e7; border-radius: 999px; background: #f8fafb; }.track-filter button { padding: 6px 9px; border: 0; border-radius: 999px; color: #617985; background: transparent; cursor: pointer; font-size: 11px; }.track-filter button.active { color: #fff; background: #1b5268; }.queue-tools input { width: 168px; padding: 8px 10px; border: 1px solid #d4e0e4; border-radius: 6px; color: #2c4e61; outline: none; font-size: 11px; }.queue-tools input:focus { border-color: #5ab9b1; }
.queue-table { border-top: 1px solid #dae5e8; }.queue-row { display: grid; grid-template-columns: 1.15fr 1.15fr 1fr 1.15fr .92fr; gap: 18px; align-items: start; padding: 19px 8px; border-bottom: 1px solid #e6edef; }.queue-labels { padding-top: 11px; padding-bottom: 9px; color: #8296a0; font-size: 10px; }.queue-row:last-child { border-bottom: 0; }.subject-cell strong { display: block; margin-top: 7px; color: #234860; font-size: 14px; }.subject-cell small { display: block; margin-top: 4px; color: #84949c; font-size: 10px; line-height: 1.5; }.track-tag { display: inline-block; padding: 3px 5px; border-radius: 3px; color: #376d86; background: #edf4f7; font-size: 9px; }.compute .track-tag { color: #2e8278; background: #e7f5f2; }.subject-cell em { display: inline-block; margin: 9px 4px 0 0; padding: 3px 5px; border-radius: 3px; color: #767f86; background: #f0f3f4; font-size: 9px; font-style: normal; }.subject-cell em.priority-a { color: #1f766f; background: #e4f5f1; }.subject-cell em.due { color: #956a1d; background: #fff1d7; }.direction-cell b { color: #31556a; font-size: 12px; }.direction-cell p,.evidence-cell p,.open-cell p { margin: 7px 0 0; color: #718590; font-size: 10px; line-height: 1.65; }.metric-cell span { color: #76919c; font-size: 10px; }.metric-cell strong { display: block; margin: 5px 0; color: #26576a; font-size: 16px; letter-spacing: -.02em; }.metric-cell small { color: #84949c; font-size: 10px; line-height: 1.5; }.source-badge { display: inline-block; padding: 3px 5px; border-radius: 3px; color: #2d7772; background: #e4f5f0; font-size: 9px; }.source-badge.scenario { color: #976a1b; background: #fff1d9; }.source-badge.public { color: #3e7187; background: #eaf2f6; }.source-badge.unknown { color: #6d777d; background: #f0f2f3; }.evidence-cell small { display: block; margin-top: 6px; color: #90a0a7; font-size: 9px; line-height: 1.55; }.open-cell button,.open-cell a { padding: 7px 9px; border: 1px solid #b9d9d6; border-radius: 5px; color: #277a73; background: #f4fbf9; cursor: pointer; font-size: 10px; font-weight: 700; text-decoration: none; }.open-cell button:hover,.open-cell a:hover { background: #e6f5f1; }.empty-state { padding: 28px; color: #83949d; font-size: 12px; text-align: center; }
.compute-detail-strip { display: grid; grid-template-columns: 1fr 1.24fr; gap: 27px; align-items: center; margin-top: 46px; padding: 26px; border: 1px solid #cde1df; border-radius: 9px; background: #edf8f6; }.compute-detail-strip h2 { font-size: 22px; }.compute-detail-strip dl { display: grid; grid-template-columns: repeat(2, 1fr); margin: 0; border: 1px solid #d6e6e4; background: #d6e6e4; }.compute-detail-strip dl div { padding: 12px; background: rgba(255,255,255,.8); }.compute-detail-strip dt { color: #76909a; font-size: 10px; }.compute-detail-strip dd { margin: 6px 0 0; color: #31596a; font-size: 13px; font-weight: 700; }.compute-detail-strip dd.pending { color: #9b7023; }.compute-detail-strip > p { grid-column: 1 / -1; margin: -8px 0 0; color: #6d818b; font-size: 11px; line-height: 1.65; }.workbench-boundary { display: grid; grid-template-columns: 90px 1fr; gap: 16px; padding: 32px 0 50px; color: #728792; font-size: 11px; line-height: 1.7; }.workbench-boundary b { color: #31566b; }
.workbench-state { display: grid; place-items: center; min-height: 350px; color: #78909c; font-size: 13px; }.workbench-state.error { gap: 13px; align-content: center; color: #a5684c; }.workbench-state.error p { margin: 0; }.workbench-state.error button { padding: 8px 11px; border: 1px solid #d6b299; border-radius: 5px; color: #95654c; background: #fff; cursor: pointer; }
@media (max-width: 900px) { .workbench-topbar,.summary-strip,.action-grid,.queue-section,.compute-detail-strip,.workbench-boundary { width: min(100% - 40px, 760px); }.workbench-hero { grid-template-columns: 1fr; padding: 46px 20px; }.summary-strip,.action-grid { grid-template-columns: repeat(2, 1fr); }.queue-heading { display: grid; align-items: start; }.queue-row { grid-template-columns: 1fr 1fr; }.queue-labels { display: none; }.queue-row > div { padding-bottom: 12px; }.queue-row > div:nth-child(3),.queue-row > div:nth-child(4) { border-top: 1px solid #edf2f3; padding-top: 12px; }.compute-detail-strip { grid-template-columns: 1fr; }.compute-detail-strip > p { grid-column: auto; } }
@media (max-width: 560px) { .workbench-topbar,.summary-strip,.action-grid,.queue-section,.compute-detail-strip,.workbench-boundary { width: min(100% - 28px, 500px); }.workbench-topbar { gap: 9px; }.workbench-brand small { display: none; }.workbench-sites { font-size: 9px; }.workbench-sites b,.workbench-sites a { padding: 6px 7px; }.workbench-hero h1 { font-size: 35px; }.summary-strip,.action-grid { grid-template-columns: 1fr; }.summary-strip article { min-height: 102px; }.queue-section { padding: 20px 15px; }.queue-tools { display: grid; width: 100%; }.queue-tools input { width: 100%; }.queue-row { grid-template-columns: 1fr; gap: 8px; }.queue-row > div:nth-child(n+2) { border-top: 1px solid #edf2f3; padding-top: 12px; }.compute-detail-strip { padding: 20px; }.compute-detail-strip dl { grid-template-columns: 1fr; }.workbench-boundary { grid-template-columns: 1fr; gap: 5px; } }
</style>
