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
  '哪些算力中心PUE低于1.3？',
  'B200-C4-1对应哪个数据中心？',
]

const canSubmit = computed(() => Boolean(question.value.trim()) && !loading.value)

function sourcePages(source) {
  if (source.locator) return source.locator
  if (source.page_start == null) return '页码待补充'
  return source.page_start === source.page_end ? `第 ${source.page_start} 页` : `第 ${source.page_start}–${source.page_end} 页`
}

function routeLabel(route) {
  return {
    SQL: '电力 / 算力结构化查询',
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
      <div><strong>AI 智能问答</strong><span>电力与算力数据库事实可追溯</span></div>
      <em>EnergyComputeAI · V0.2 SQL</em>
    </header>

    <main class="ai-shell">
      <section class="ai-conversation" aria-live="polite">
        <div v-if="!messages.length" class="ai-welcome">
          <p>面向电力与算力事实的可审计查询</p>
          <h1>先取证，再作答。</h1>
          <span>数字只来自已执行的只读 SQL；字段、单位和实体口径均可追溯；数据库无法回答时会明确拒答。</span>
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

            <section v-if="message.result.sources?.length" class="ai-evidence-block">
              <h2>数据来源</h2>
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
        <section><span>工作方式</span><h2>模型不猜数字</h2><ol><li>解析设施、企业与商品别名</li><li>生成并校验只读 SQL</li><li>原样展示数据库字段与结果</li></ol></section>
        <section><span>使用边界</span><p>当前 V0.2 仅提供数据库事实查询；政策解释、绿色资格、融资风险及授信建议均会拒答，等待后续工具层接入。</p></section>
      </aside>

      <form class="ai-composer" @submit.prevent="submit">
        <label for="ai-question">请输入数据库查询问题</label>
        <div><textarea id="ai-question" v-model="question" rows="3" maxlength="2000" placeholder="例如：哪些算力中心 PUE 低于 1.3？" @keydown.meta.enter.prevent="submit" @keydown.ctrl.enter.prevent="submit"></textarea><button type="submit" :disabled="!canSubmit">{{ loading ? '处理中…' : '发送 →' }}</button></div>
        <small>⌘ / Ctrl + Enter 发送 · 系统会保存审计记录与来源依据。</small>
      </form>
    </main>
  </div>
</template>
