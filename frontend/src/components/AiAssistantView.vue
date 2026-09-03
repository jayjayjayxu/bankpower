<script setup>
import { computed, nextTick, ref } from 'vue'
import { AiApiError, askAi, clearFinanceAssumptions, resetConversationContext } from '../services/aiApi'

defineEmits(['back', 'open-project-analysis'])

const question = ref('')
const messages = ref([])
const loading = ref(false)
const requestError = ref('')
const sessionId = ref(null)
const conversation = ref(null)
const conversationViewport = ref(null)
const examples = [
  '深圳百旺信智算中心2025年的上架率和平均机柜价格是多少？',
  '哪些算力中心PUE低于1.3？',
  'B200-C4-1对应哪个数据中心？',
]

const canSubmit = computed(() => Boolean(question.value.trim()) && !loading.value)
const contextItems = computed(() => {
  const state = conversation.value
  if (!state) return []
  const entities = (state.active_entities || []).map((item) => ({ key: `entity-${item.id}`, label: `项目：${item.name}` }))
  const year = state.active_time_range?.year ? [{ key: 'year', label: `年份：${state.active_time_range.year}` }] : []
  const metrics = (state.active_metrics || []).map((item) => ({ key: `metric-${item}`, label: `指标：${metricLabel(item)}` }))
  const assumptions = (state.assumptions || []).map((item) => ({ key: `assumption-${item.field}`, label: `假设：${assumptionLabel(item)}` }))
  return [...entities, ...year, ...metrics, ...assumptions]
})

function metricLabel(metric) {
  return { rack_occupancy_rate: '上架率', rack_price: '平均机柜价格', pue: 'PUE' }[metric] || metric
}

function assumptionLabel(item) {
  const value = item.field === 'annual_cfads' ? '逐年 CFADS' : item.value
  const label = { debt_ratio: '债务比例', interest_rate: '年利率', loan_term_years: '期限', required_min_dscr: '最低 DSCR' }[item.field] || item.field
  if (item.field === 'debt_ratio' || item.field === 'interest_rate') return `${label} ${Number(item.value) * 100}%`
  return `${label} ${value}${item.unit === 'YEAR' ? '年' : ''}`
}

async function clearAssumptions() {
  if (!sessionId.value || loading.value) return
  requestError.value = ''
  try {
    const result = await clearFinanceAssumptions(sessionId.value)
    conversation.value = result.conversation
  } catch (error) {
    requestError.value = publicRequestError(error, '无法清除融资假设。')
  }
}

async function resetContext() {
  if (!sessionId.value || loading.value) return
  requestError.value = ''
  try {
    const result = await resetConversationContext(sessionId.value)
    conversation.value = result.conversation
  } catch (error) {
    requestError.value = publicRequestError(error, '无法重置当前上下文。')
  }
}

function sourcePages(source) {
  if (source.locator) return source.locator
  if (source.page_start == null) return '页码待补充'
  return source.page_start === source.page_end ? `第 ${source.page_start} 页` : `第 ${source.page_start}–${source.page_end} 页`
}

function sourceDetails(source) {
  const parts = [source.issuing_authority, source.policy_status, source.policy_level, source.region, source.effective_date && `生效 ${source.effective_date}`].filter(Boolean)
  return parts.length ? parts.join(' · ') : (source.authority || '文件来源')
}

function routeLabel(route) {
  return {
    SQL: '电力 / 算力结构化查询',
    RAG: '现行公开政策检索',
    BOTH: '数据库 + 政策证据比对',
    DUE_DILIGENCE: '项目初步尽调',
    DUE_DILIGENCE_FOLLOW_UP: '尽调结果复用',
    FINANCE_FOLLOW_UP: '融资假设重算',
    PROVENANCE: '上一轮证据追溯',
    SQL_CALC: '公开统计程序计算',
    CALC_PROVENANCE: '计算过程追溯',
    CLARIFICATION: '需澄清指标',
    IN_SCOPE_DATA_MISSING: '领域内数据暂缺',
    OUT_OF_SCOPE: '能力边界提示',
  }[route] || route
}

function useExample(value) {
  question.value = value
}

function dueScore(due) {
  const score = Number(due?.snapshot?.data_completeness?.score)
  return Number.isFinite(score) ? `${score.toFixed(1)}%` : '—'
}

function highRiskCount(due) {
  return (due?.risks || []).filter((item) => item.level === 'HIGH').length
}

function publicRequestError(error, fallback) {
  if (error instanceof AiApiError) {
    return `${error.message}${error.code ? `（${error.code}）` : ''}${error.retryable ? ' 可稍后重试。' : ''}`
  }
  return error instanceof Error ? error.message : fallback
}

async function submit() {
  const value = question.value.trim()
  if (!value || loading.value) return
  requestError.value = ''
  messages.value.push({ type: 'question', text: value })
  question.value = ''
  loading.value = true
  await scrollConversationToLatest()
  try {
    const result = await askAi(value, sessionId.value)
    sessionId.value = result.session_id || sessionId.value
    conversation.value = result.conversation || conversation.value
    messages.value.push({ type: 'answer', result })
  } catch (error) {
    requestError.value = publicRequestError(error, 'AI 服务暂时不可用。')
  } finally {
    loading.value = false
    await scrollConversationToLatest()
  }
}

async function scrollConversationToLatest() {
  await nextTick()
  const viewport = conversationViewport.value
  if (viewport) viewport.scrollTo({ top: viewport.scrollHeight, behavior: 'smooth' })
}
</script>

<template>
  <div class="ai-page">
    <header class="ai-topbar">
      <button type="button" class="ai-back" @click="$emit('back')">← 返回电力研究</button>
      <div><strong>AI 智能问答</strong><span>电力与算力数据库事实可追溯</span></div>
      <em>EnergyComputeAI · V0.3.1</em>
    </header>

    <main class="ai-shell">
      <section class="ai-chat-panel">
      <section ref="conversationViewport" class="ai-conversation" aria-live="polite">
        <div v-if="contextItems.length" class="ai-context" aria-label="当前分析上下文">
          <span>当前上下文</span><b v-for="item in contextItems" :key="item.key">{{ item.label }}</b>
          <button v-if="conversation?.assumptions?.length" type="button" @click="clearAssumptions">清除融资假设 ×</button>
          <button type="button" @click="resetContext">重置上下文 ×</button>
          <small>仅继承已确认实体、明确时间与指标</small>
        </div>
        <div v-if="!messages.length" class="ai-welcome">
          <p>面向电力、算力与现行公开政策的可审计问答</p>
          <h1>先取证，再作答。</h1>
          <span>数字只来自已执行的只读 SQL；系统会将原始结果转换为业务语义，并保留数据口径与证据边界。</span>
          <div class="ai-examples">
            <button v-for="example in examples" :key="example" type="button" @click="useExample(example)">{{ example }}</button>
          </div>
        </div>

        <template v-for="(message, index) in messages" :key="index">
          <article v-if="message.type === 'question'" class="ai-question"><span>你的问题</span><p>{{ message.text }}</p></article>

          <article v-else class="ai-answer">
            <header>
              <div><span>AI 回答</span><b>{{ routeLabel(message.result.route) }}</b><small v-if="message.result.error_code" class="ai-outcome-code">{{ message.result.error_code }}</small></div>
              <small>{{ message.result.timing?.total_ms ?? '—' }} ms · {{ message.result.request_id }}</small>
            </header>
            <section class="ai-answer-conclusion"><h2>结论</h2><p>{{ message.result.interpretation?.primary_conclusion || message.result.answer }}</p></section>

            <section v-if="message.result.data?.due_diligence" class="ai-evidence-block ai-dd-summary">
              <h2>项目初步尽调</h2>
              <div><span>资料完整度 <b>{{ dueScore(message.result.data.due_diligence) }}</b></span><span>高优先级风险 <b>{{ highRiskCount(message.result.data.due_diligence) }}</b></span><span>待补材料 <b>{{ message.result.data.due_diligence.evidence_gaps?.length || 0 }}</b></span></div>
              <p>结果编号：{{ message.result.data.due_diligence.result_id }} · 可基于本结果继续询问“最大风险是什么？”或“还缺哪些资料？”。</p>
              <button type="button" @click="$emit('open-project-analysis')">打开完整尽调看板 →</button>
            </section>

            <section v-if="message.result.structured_data?.facts?.length" class="ai-evidence-block">
              <h2>关键数据</h2>
              <ul class="ai-claim-list"><li v-for="fact in message.result.structured_data.facts" :key="`${fact.key}-${fact.label}`"><span>{{ fact.label }}</span>{{ fact.value }}</li></ul>
            </section>

            <section v-if="message.result.data?.calculation" class="ai-evidence-block">
              <h2>程序计算</h2>
              <ul class="ai-claim-list">
                <li><span>{{ message.result.data.calculation.calculation_type }}</span>{{ message.result.data.calculation.formula }} = <b>{{ message.result.data.calculation.display_value }}</b></li>
                <li><span>分子</span>{{ message.result.data.calculation.numerator?.value }} {{ message.result.data.calculation.numerator?.unit }} · {{ message.result.data.calculation.numerator?.statistical_scope }}</li>
                <li><span>分母</span>{{ message.result.data.calculation.denominator?.value }} {{ message.result.data.calculation.denominator?.unit }} · {{ message.result.data.calculation.denominator?.statistical_scope }}</li>
              </ul>
            </section>

            <section v-if="message.result.structured_data?.candidates?.length" class="ai-evidence-block">
              <h2>候选参照</h2>
              <ul class="ai-claim-list"><li v-for="candidate in message.result.structured_data.candidates" :key="candidate.name"><span>{{ candidate.role }}</span><b>{{ candidate.name }}</b><br>{{ candidate.reason }}</li></ul>
            </section>

            <aside v-if="message.result.structured_data?.boundaries?.length" class="ai-warnings"><b>证据边界</b><p v-for="boundary in message.result.structured_data.boundaries" :key="boundary.message">{{ boundary.message }}</p></aside>

            <details v-if="message.result.data?.sql" class="ai-evidence-block ai-raw-data">
              <summary>查看原始数据（只读）</summary>
              <div class="ai-table-wrap"><table><thead><tr><th v-for="column in message.result.data.sql.columns" :key="column">{{ column }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in message.result.data.sql.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div>
            </details>

            <section v-if="message.result.data?.comparison" class="ai-evidence-block">
              <h2>匹配分析</h2>
              <ul class="ai-claim-list"><li><span>{{ message.result.data.comparison.status }}</span>{{ message.result.data.comparison.reason }}</li></ul>
            </section>

            <section v-if="message.result.sources?.length" class="ai-evidence-block">
              <h2>数据来源</h2>
              <ol class="ai-source-list"><li v-for="(source, sourceIndex) in message.result.sources" :key="`${source.document_name}-${sourceIndex}`"><div><b>{{ source.document_name }}</b><span>{{ sourcePages(source) }} · {{ sourceDetails(source) }}</span></div><q v-if="source.quote">{{ source.quote }}</q><a v-if="source.url" :href="source.url" target="_blank" rel="noreferrer">查看官方链接</a></li></ol>
            </section>

            <section v-if="message.result.claims?.length" class="ai-evidence-block">
              <h2>进一步分析</h2>
              <ul class="ai-claim-list"><li v-for="(claim, claimIndex) in message.result.claims" :key="claimIndex"><span>{{ claim.claim_type }}</span>{{ claim.text }}</li></ul>
            </section>

            <aside v-if="message.result.warnings?.length" class="ai-warnings"><b>风险提示</b><p v-for="warning in message.result.warnings" :key="warning">{{ warning }}</p></aside>
          </article>
        </template>

        <div v-if="loading" class="ai-thinking"><i></i><span>正在识别问题类型并调用受控工具…</span></div>
        <p v-if="requestError" class="ai-request-error">{{ requestError }}</p>
      </section>
      <form class="ai-composer" @submit.prevent="submit">
        <label for="ai-question">请输入项目事实或政策问题</label>
        <div><textarea id="ai-question" v-model="question" rows="3" maxlength="2000" placeholder="例如：哪些算力中心 PUE 低于 1.3？" @keydown.meta.enter.prevent="submit" @keydown.ctrl.enter.prevent="submit"></textarea><button type="submit" :disabled="!canSubmit">{{ loading ? '处理中…' : '发送 →' }}</button></div>
        <small>⌘ / Ctrl + Enter 发送 · 系统会保存审计记录与来源依据。</small>
      </form>
      </section>

      <aside class="ai-sidebar">
        <section><span>工作方式</span><h2>程序负责正确，AI负责易读</h2><ol><li>解析设施、企业与商品别名</li><li>生成并校验只读 SQL</li><li>程序化解释数据口径、状态与缺失值</li></ol></section>
        <section><span>使用边界</span><p>系统可做数据库事实、现行公开政策解释及有限的指标比对；绿色贷款资格、授信建议与融资比例仍须人工复核。</p></section>
        <section class="ai-due-diligence-link"><span>项目工具</span><h2>进入项目初步尽调</h2><p>汇集项目事实、政策规则与待补材料，形成可追溯的尽调快照。</p><button type="button" @click="$emit('open-project-analysis')">打开项目尽调 →</button></section>
      </aside>
    </main>
  </div>
</template>
