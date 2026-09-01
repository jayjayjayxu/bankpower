<script setup>
import { computed, ref } from 'vue'
import { askAi } from '../services/aiApi'

defineEmits(['back'])

const question = ref('')
const messages = ref([])
const loading = ref(false)
const requestError = ref('')
const examples = [
  '深圳百旺信智算中心2025年的上架率和平均机柜价格是多少？',
  '深圳训力券对算力服务商是否构成直接收入？',
  '百旺信这种项目是否适合做绿色贷款，预计能做到多少贷款比例？',
]

const canSubmit = computed(() => Boolean(question.value.trim()) && !loading.value)

function sourcePages(source) {
  if (source.locator) return source.locator
  if (source.page_start == null) return '页码待补充'
  return source.page_start === source.page_end ? `第 ${source.page_start} 页` : `第 ${source.page_start}–${source.page_end} 页`
}

function routeLabel(route) {
  return {
    RAG: '政策 / 文件检索',
    SQL: '结构化数据查询',
    BOTH: '数据与政策综合',
    OUT_OF_SCOPE: '能力边界提示',
  }[route] || route
}

function useExample(value) {
  question.value = value
}

async function submit() {
  const value = question.value.trim()
  if (!value || loading.value) return
  requestError.value = ''
  messages.value.push({ type: 'question', text: value })
  question.value = ''
  loading.value = true
  try {
    messages.value.push({ type: 'answer', result: await askAi(value) })
  } catch (error) {
    requestError.value = error instanceof Error ? error.message : 'AI 服务暂时不可用。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="ai-page">
    <header class="ai-topbar">
      <button type="button" class="ai-back" @click="$emit('back')">← 返回电力研究</button>
      <div><strong>AI 智能问答</strong><span>事实、政策与分析依据可追溯</span></div>
      <em>EnergyComputeAI · V0.2</em>
    </header>

    <main class="ai-shell">
      <section class="ai-conversation" aria-live="polite">
        <div v-if="!messages.length" class="ai-welcome">
          <p>面向银行研究的可审计问答</p>
          <h1>先取证，再作答。</h1>
          <span>数字只来自已执行查询；政策结论绑定文件原文；证据不足时会明确提示。</span>
          <div class="ai-examples">
            <button v-for="example in examples" :key="example" type="button" @click="useExample(example)">{{ example }}</button>
          </div>
        </div>

        <template v-for="(message, index) in messages" :key="index">
          <article v-if="message.type === 'question'" class="ai-question"><span>你的问题</span><p>{{ message.text }}</p></article>

          <article v-else class="ai-answer">
            <header>
              <div><span>AI 回答</span><b>{{ routeLabel(message.result.route) }}</b></div>
              <small>{{ message.result.timing?.total_ms ?? '—' }} ms · {{ message.result.request_id }}</small>
            </header>
            <section class="ai-answer-conclusion"><h2>结论</h2><p>{{ message.result.answer }}</p></section>

            <section v-if="message.result.data?.sql" class="ai-evidence-block">
              <h2>数据依据</h2>
              <div class="ai-table-wrap"><table><thead><tr><th v-for="column in message.result.data.sql.columns" :key="column">{{ column }}</th></tr></thead><tbody><tr v-for="(row, rowIndex) in message.result.data.sql.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td></tr></tbody></table></div>
            </section>

            <section v-if="message.result.data?.finance" class="ai-evidence-block">
              <h2>融资测算边界</h2>
              <ul class="ai-claim-list">
                <li><span>STATUS</span>{{ message.result.data.finance.status }}</li>
                <li><span>FORMULA</span>{{ message.result.data.finance.formula }}</li>
                <li v-for="(evidence, evidenceIndex) in message.result.data.finance.missing_evidence || []" :key="evidenceIndex"><span>NEEDED</span>{{ evidence }}</li>
              </ul>
            </section>

            <section v-if="message.result.sources?.length" class="ai-evidence-block">
              <h2>政策 / 文件依据</h2>
              <ol class="ai-source-list"><li v-for="(source, sourceIndex) in message.result.sources" :key="`${source.document_name}-${sourceIndex}`"><div><b>{{ source.document_name }}</b><span>{{ sourcePages(source) }} · {{ source.authority || '文件来源' }}</span></div><q v-if="source.quote">{{ source.quote }}</q><a v-if="source.url" :href="source.url" target="_blank" rel="noreferrer">查看官方链接</a></li></ol>
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

      <aside class="ai-sidebar">
        <section><span>工作方式</span><h2>模型不猜数字</h2><ol><li>识别 SQL、RAG 或综合问题</li><li>调用只读数据与政策证据</li><li>在有依据的范围内组织回答</li></ol></section>
        <section><span>使用边界</span><p>回答仅作为研究与初步判断，不构成授信审批、绿色贷款资格认定或融资承诺。</p></section>
      </aside>

      <form class="ai-composer" @submit.prevent="submit">
        <label for="ai-question">请输入研究问题</label>
        <div><textarea id="ai-question" v-model="question" rows="3" maxlength="2000" placeholder="例如：百旺信项目是否适合绿色贷款，预计可贷比例是多少？" @keydown.meta.enter.prevent="submit" @keydown.ctrl.enter.prevent="submit"></textarea><button type="submit" :disabled="!canSubmit">{{ loading ? '处理中…' : '发送 →' }}</button></div>
        <small>⌘ / Ctrl + Enter 发送 · 系统会保存审计记录与来源依据。</small>
      </form>
    </main>
  </div>
</template>
