<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchDueDiligence } from '../services/aiApi'

defineEmits(['back'])

const projectId = ref('SZCF016')
const result = ref(null)
const loading = ref(true)
const error = ref('')

const statusLabel = {
  AVAILABLE: '已具备', MISSING: '缺失', CONFLICTING: '口径冲突', STALE: '已过期', NOT_APPLICABLE: '不适用',
}
const levelLabel = { HIGH: '高优先级', MEDIUM: '中优先级', LOW: '低优先级', UNKNOWN: '待判断' }
const domainLabel = {
  PROJECT_IDENTITY: '项目主体', OPERATION: '经营情况', ENERGY: '能耗与绿电', FINANCIAL: '财务现金流',
  FINANCING: '融资结构', POLICY: '政策材料', DATA_QUALITY: '资料质量', DATA: '数据质量', FINANCE: '融资测算',
}

const completeness = computed(() => result.value?.snapshot?.data_completeness)
const domains = computed(() => Object.entries(result.value?.snapshot?.domains || {}))
const counts = computed(() => completeness.value?.status_counts || {})
const highRisks = computed(() => (result.value?.risks || []).filter((item) => item.level === 'HIGH').length)
const readableProjectName = computed(() => result.value?.snapshot?.project_name || projectId.value)

function score(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? `${parsed.toFixed(1)}%` : '—'
}

function labelStatus(value) { return statusLabel[value] || value || '—' }
function labelLevel(value) { return levelLabel[value] || value || '—' }
function labelDomain(value) { return domainLabel[value] || value || '其他' }

function evidenceText(evidence) {
  const parts = [evidence.value, evidence.unit, evidence.scope, evidence.as_of_date && `截至 ${evidence.as_of_date}`].filter(Boolean)
  return parts.join(' · ') || '未提供数值'
}

async function load() {
  const id = projectId.value.trim().toUpperCase()
  if (!id || loading.value) return
  projectId.value = id
  loading.value = true
  error.value = ''
  try {
    result.value = await fetchDueDiligence(id)
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : '尽调服务暂时不可用。'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="dd-page">
    <header class="dd-topbar">
      <button type="button" class="dd-back" @click="$emit('back')">← 返回电力研究</button>
      <div><strong>项目初步尽调</strong><span>事实、规则与待补材料分层呈现</span></div>
      <em>EnergyComputeAI · V5-D</em>
    </header>

    <main class="dd-shell">
      <section class="dd-hero">
        <div>
          <p>INITIAL DUE DILIGENCE / 可审计项目快照</p>
          <h1>先确认资料，<em>再进入融资判断。</em></h1>
          <span>所有项目事实来自受控只读数据库；政策规则、风险提示与缺口清单均保留其生成依据。</span>
        </div>
        <form class="dd-query" @submit.prevent="load">
          <label for="project-id">项目编号</label>
          <div><input id="project-id" v-model="projectId" maxlength="32" autocomplete="off" /><button type="submit" :disabled="loading">{{ loading ? '正在生成…' : '生成快照 →' }}</button></div>
          <small>当前已接入示例：SZCF016。输入值仅作为项目编号传给受控接口。</small>
        </form>
      </section>

      <div v-if="loading" class="dd-state">正在汇集项目事实、政策规则与资料缺口…</div>
      <div v-else-if="error" class="dd-state error"><p>{{ error }}</p><button type="button" @click="load">重新尝试</button></div>

      <template v-else-if="result">
        <section class="dd-project-bar">
          <div><span>项目</span><h2>{{ readableProjectName }}</h2><small>{{ result.project_id }} · {{ result.snapshot.profile_version }} · 生成于 {{ result.snapshot.generated_at }}</small></div>
          <aside><span>政策规则状态</span><strong>{{ result.eligibility.overall_status }}</strong><small>基于已知事实的初步规则评估</small></aside>
        </section>

        <section class="dd-summary-grid" aria-label="尽调摘要">
          <article class="dd-score"><span>资料完整度</span><strong>{{ score(completeness.score) }}</strong><small>{{ completeness.available_weight }} / {{ completeness.required_weight }} 个加权必需项可用</small></article>
          <article><span>待补资料</span><strong>{{ result.evidence_gaps.length }}</strong><small>按字段、规则与风险生成</small></article>
          <article :class="{ attention: highRisks }"><span>高优先级风险</span><strong>{{ highRisks }}</strong><small>风险不是授信结论</small></article>
          <article><span>压力测试</span><strong>未执行</strong><small>输入资料尚不完整</small></article>
        </section>

        <section class="dd-boundary"><b>结果边界</b><p>{{ result.warning }}</p><p>{{ completeness.definition }}</p></section>

        <section class="dd-section">
          <header class="dd-section-heading"><div><span>01 / PROJECT SNAPSHOT</span><h2>项目资料与事实依据</h2></div><p>字段按资料状态呈现；“口径冲突”不由页面自行消解，须回到原始材料复核。</p></header>
          <div class="dd-counts"><span v-for="status in ['AVAILABLE', 'CONFLICTING', 'MISSING', 'STALE']" :key="status" :class="['dd-status', status.toLowerCase()]">{{ labelStatus(status) }} <b>{{ counts[status] || 0 }}</b></span></div>
          <div class="dd-domain-grid">
            <article v-for="([domain, fields]) in domains" :key="domain" class="dd-domain-card">
              <h3>{{ labelDomain(domain) }}</h3>
              <div v-for="field in fields" :key="field.field" class="dd-field">
                <div><strong>{{ field.label }}</strong><small>{{ field.required ? '必需字段' : '补充字段' }} · {{ field.reason }}</small></div>
                <span :class="['dd-status', field.status.toLowerCase()]">{{ labelStatus(field.status) }}</span>
                <div class="dd-evidence">
                  <template v-if="field.evidence.length"><p v-for="item in field.evidence" :key="`${item.source_id}-${item.value}`">{{ evidenceText(item) }}<small>{{ item.source_id }}<template v-if="item.source_locator"> · {{ item.source_locator }}</template></small></p></template>
                  <p v-else>暂无可追溯原始材料</p>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="dd-two-column">
          <article class="dd-section dd-risk-panel">
            <header class="dd-section-heading"><div><span>02 / RISK FLAGS</span><h2>确定性风险提示</h2></div><p>由字段状态和受控规则触发，不是模型的主观评级。</p></header>
            <div v-if="!result.risks.length" class="dd-empty">当前没有触发风险标记。</div>
            <ol v-else class="dd-list"><li v-for="risk in result.risks" :key="risk.code"><span :class="['dd-level', risk.level.toLowerCase()]">{{ labelLevel(risk.level) }}</span><div><b>{{ risk.trigger }}</b><p>{{ labelDomain(risk.domain) }} · {{ risk.code }}<template v-if="risk.threshold"> · 阈值 {{ risk.threshold }}</template></p><small>依据：{{ risk.source_id }}<template v-if="risk.evidence_ids.length"> · {{ risk.evidence_ids.join('、') }}</template></small></div></li></ol>
          </article>
          <article class="dd-section dd-gap-panel">
            <header class="dd-section-heading"><div><span>03 / EVIDENCE GAPS</span><h2>待补材料清单</h2></div><p>补齐后才能将初步判断推进至可复核的测算。</p></header>
            <ol class="dd-list"><li v-for="gap in result.evidence_gaps" :key="gap.code"><span :class="['dd-level', gap.priority.toLowerCase()]">{{ labelLevel(gap.priority) }}</span><div><b>{{ gap.required_evidence }}</b><p>{{ labelDomain(gap.domain) }} · {{ gap.reason }}</p><small>{{ gap.code }} · {{ gap.source_id }}</small></div></li></ol>
          </article>
        </section>

        <section class="dd-section dd-policy-section">
          <header class="dd-section-heading"><div><span>04 / POLICY & SCENARIO</span><h2>政策与压力测试边界</h2></div><p>政策命中不等同于最终绿色贷款认定；所有资格仍须以项目材料、适用地区和审批规则复核。</p></header>
          <div class="dd-policy-grid"><article><span>规则汇总</span><dl><div v-for="(value, name) in result.eligibility.summary" :key="name"><dt>{{ name }}</dt><dd>{{ value }}</dd></div></dl></article><article><span>压力测试状态</span><p>{{ result.scenario_boundary }}</p><small>当前不使用行业或项目外部假设替代项目单独 CFADS、贷款合同与还款参数。</small></article></div>
        </section>

        <section class="dd-claims"><span>审计声明</span><p v-for="claim in result.claims" :key="claim.claim_type">{{ claim.text }}<small>{{ claim.support_ids.join('、') }}</small></p></section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.dd-page { min-height: 100vh; color: #1c3549; background: #f3f7f8; }.dd-topbar { min-height: 65px; display: flex; align-items: center; gap: 15px; padding: 0 max(28px, calc((100vw - 1180px) / 2)); border-bottom: 1px solid #d8e6e8; background: #fff; }.dd-back { padding: 0; border: 0; color: #376c80; background: transparent; cursor: pointer; font-size: 12px; }.dd-topbar > div { display: grid; gap: 2px; }.dd-topbar strong { color: #1a405a; font-size: 14px; }.dd-topbar span { color: #8397a1; font-size: 10px; }.dd-topbar em { margin-left: auto; color: #5b9d9a; font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .06em; }.dd-shell { width: min(1180px, calc(100% - 56px)); margin: 0 auto; padding: 42px 0 64px; }.dd-hero { display: grid; grid-template-columns: 1.16fr .84fr; gap: 38px; align-items: end; padding: 42px; color: #edf8f8; background: linear-gradient(120deg, #102f4c, #17596a); }.dd-hero p,.dd-section-heading span { color: #70ded1; font: 10px ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: .08em; }.dd-hero h1 { margin: 10px 0 15px; color: #f5fbfb; font-size: clamp(34px, 4.3vw, 51px); line-height: 1.12; letter-spacing: -.045em; }.dd-hero h1 em { color: #77ddd0; font-style: normal; }.dd-hero > div > span { display: block; max-width: 620px; color: #b6d0d6; font-size: 14px; line-height: 1.75; }.dd-query { padding: 18px; border: 1px solid rgba(205, 239, 238, .26); background: rgba(4, 31, 51, .22); }.dd-query label { display: block; margin-bottom: 8px; color: #a9c8ce; font-size: 10px; }.dd-query > div { display: flex; gap: 8px; }.dd-query input { min-width: 0; flex: 1; padding: 10px; border: 1px solid #7fabb4; border-radius: 4px; color: #eaffff; background: #113b58; outline: 0; font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; }.dd-query button { padding: 0 12px; border: 0; border-radius: 4px; color: #10364a; background: #72ddd2; cursor: pointer; font-size: 11px; font-weight: 700; }.dd-query button:disabled { opacity: .6; cursor: wait; }.dd-query small { display: block; margin-top: 9px; color: #9cbac2; font-size: 9px; line-height: 1.5; }.dd-state { display: grid; place-items: center; min-height: 360px; color: #66808d; font-size: 13px; }.dd-state.error { gap: 12px; align-content: center; color: #a3634f; }.dd-state p { margin: 0; }.dd-state button { padding: 8px 10px; border: 1px solid #d8b09d; border-radius: 4px; color: #985e48; background: #fff; cursor: pointer; }.dd-project-bar { display: flex; justify-content: space-between; gap: 20px; align-items: end; padding: 27px 0 22px; border-bottom: 1px solid #dce7e8; }.dd-project-bar span,.dd-project-bar small { color: #77909b; font-size: 10px; }.dd-project-bar h2 { margin: 5px 0; color: #22465c; font-size: 28px; letter-spacing: -.03em; }.dd-project-bar aside { min-width: 260px; padding-left: 22px; border-left: 1px solid #d9e6e8; }.dd-project-bar aside span,.dd-project-bar aside small { display: block; }.dd-project-bar aside strong { display: block; margin: 7px 0 4px; color: #247d77; font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; }.dd-summary-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; margin: 26px 0; border: 1px solid #d8e5e7; background: #d8e5e7; }.dd-summary-grid article { min-height: 124px; padding: 19px; background: #fff; }.dd-summary-grid span { color: #81949e; font-size: 11px; }.dd-summary-grid strong { display: block; margin: 10px 0 7px; color: #26556a; font-size: 28px; letter-spacing: -.04em; }.dd-summary-grid small { color: #8799a1; font-size: 10px; line-height: 1.5; }.dd-summary-grid .dd-score strong { color: #1b857c; font-size: 35px; }.dd-summary-grid .attention strong { color: #b3693b; }.dd-boundary { display: grid; grid-template-columns: 90px 1fr; gap: 15px; padding: 17px 19px; border-left: 3px solid #e2af5e; background: #fffaf0; color: #7c7159; font-size: 11px; line-height: 1.65; }.dd-boundary b { color: #966b2c; }.dd-boundary p { margin: 0; }.dd-section { margin-top: 44px; }.dd-section-heading { display: flex; justify-content: space-between; gap: 30px; align-items: end; margin-bottom: 18px; }.dd-section-heading h2 { margin: 7px 0 0; color: #234960; font-size: 26px; letter-spacing: -.03em; }.dd-section-heading > p { max-width: 410px; margin: 0; color: #748994; font-size: 11px; line-height: 1.7; }.dd-counts { display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 12px; }.dd-status,.dd-level { display: inline-block; padding: 4px 6px; border-radius: 3px; color: #657780; background: #edf1f2; font-size: 9px; white-space: nowrap; }.dd-status b { margin-left: 4px; }.dd-status.available { color: #20766e; background: #e2f3ee; }.dd-status.conflicting { color: #996820; background: #fff1d8; }.dd-status.missing { color: #a15945; background: #fae9e4; }.dd-status.stale { color: #697084; background: #eaecf2; }.dd-domain-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }.dd-domain-card { overflow: hidden; border: 1px solid #d9e6e8; border-radius: 7px; background: #fff; }.dd-domain-card h3 { margin: 0; padding: 14px 17px; border-bottom: 1px solid #e2ebed; color: #2e5267; font-size: 14px; }.dd-field { display: grid; grid-template-columns: minmax(115px, .95fr) auto minmax(150px, 1.05fr); gap: 12px; align-items: start; padding: 13px 17px; border-bottom: 1px solid #edf1f2; }.dd-field:last-child { border-bottom: 0; }.dd-field strong { display: block; color: #405e6e; font-size: 11px; }.dd-field > div:first-child small { display: block; margin-top: 5px; color: #8a9aa1; font-size: 9px; line-height: 1.5; }.dd-evidence p { margin: 0 0 6px; color: #5c7380; font-size: 10px; line-height: 1.45; word-break: break-word; }.dd-evidence p:last-child { margin-bottom: 0; }.dd-evidence small { display: block; margin-top: 3px; color: #91a1a7; font: 8px ui-monospace, SFMono-Regular, Menlo, monospace; }.dd-two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }.dd-two-column .dd-section { min-width: 0; }.dd-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }.dd-list li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: start; padding: 13px; border: 1px solid #dce7e9; border-radius: 6px; background: #fff; }.dd-level.high { color: #a6523e; background: #fae5df; }.dd-level.medium { color: #966a20; background: #fff0d8; }.dd-level.low { color: #28766f; background: #e2f3ee; }.dd-list b { display: block; color: #34576b; font-size: 11px; line-height: 1.5; }.dd-list p { margin: 5px 0; color: #708792; font-size: 10px; line-height: 1.55; }.dd-list small { color: #8c9ca3; font: 8px ui-monospace, SFMono-Regular, Menlo, monospace; line-height: 1.5; word-break: break-word; }.dd-empty { padding: 28px; border: 1px dashed #cedcdf; color: #80939b; background: #fff; font-size: 12px; text-align: center; }.dd-policy-section { padding: 26px; border: 1px solid #d8e5e7; border-radius: 8px; background: #fff; }.dd-policy-grid { display: grid; grid-template-columns: .85fr 1.15fr; gap: 28px; }.dd-policy-grid article { padding: 17px; background: #f5f9f9; }.dd-policy-grid article > span { color: #438c86; font-size: 10px; font-weight: 700; }.dd-policy-grid p { margin: 10px 0; color: #54717f; font-size: 12px; line-height: 1.72; }.dd-policy-grid small { color: #82949e; font-size: 10px; line-height: 1.55; }.dd-policy-grid dl { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px; margin: 13px 0 0; background: #dce9e9; }.dd-policy-grid dl div { padding: 10px; background: #fff; }.dd-policy-grid dt { color: #81959d; font: 8px ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-word; }.dd-policy-grid dd { margin: 5px 0 0; color: #29665f; font-size: 17px; font-weight: 700; }.dd-claims { margin-top: 30px; padding: 18px 0; border-top: 1px solid #dce7e8; color: #718892; font-size: 10px; line-height: 1.65; }.dd-claims > span { color: #3b7674; font: 9px ui-monospace, SFMono-Regular, Menlo, monospace; }.dd-claims p { margin: 7px 0; }.dd-claims small { display: block; color: #95a3a9; font: 8px ui-monospace, SFMono-Regular, Menlo, monospace; word-break: break-word; }
@media (max-width: 850px) { .dd-shell { width: min(100% - 38px, 700px); }.dd-hero,.dd-domain-grid,.dd-two-column,.dd-policy-grid { grid-template-columns: 1fr; }.dd-summary-grid { grid-template-columns: repeat(2, 1fr); }.dd-section-heading { display: grid; gap: 9px; }.dd-project-bar { align-items: start; }.dd-project-bar aside { min-width: 0; }.dd-field { grid-template-columns: 1fr auto; }.dd-evidence { grid-column: 1 / -1; } }
@media (max-width: 540px) { .dd-topbar { padding: 0 16px; }.dd-topbar em { display: none; }.dd-shell { width: min(100% - 28px, 500px); padding-top: 20px; }.dd-hero { padding: 25px 20px; }.dd-query > div { display: grid; }.dd-query button { min-height: 36px; }.dd-project-bar { display: grid; }.dd-project-bar aside { padding: 14px 0 0; border-top: 1px solid #d9e6e8; border-left: 0; }.dd-summary-grid { grid-template-columns: 1fr; }.dd-boundary { grid-template-columns: 1fr; gap: 5px; }.dd-field { grid-template-columns: 1fr; gap: 8px; }.dd-field > .dd-status { justify-self: start; }.dd-policy-section { padding: 20px 15px; } }
</style>
