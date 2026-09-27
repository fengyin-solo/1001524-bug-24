<template>
  <section class="page" data-module="power-detail">
    <header class="page-head">
      <div>
        <h2>供电单元详情</h2>
        <p class="page-desc">查看单个供电单元的当前状态、待补字段与全部处理记录。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <template v-if="entry">
      <div v-if="missing.length" class="error-text">
        以下字段未填写：{{ missing.join('、') }}，补齐后才能确认正常。
      </div>

      <table class="data-table">
        <tbody>
          <tr v-for="field in fields" :key="field">
            <th>{{ field }}</th>
            <td>{{ entry[field] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <h3>处理记录</h3>
      <table class="data-table">
        <thead>
          <tr><th>时间</th><th>动作</th><th>状态变化</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="(record, index) in history" :key="index">
            <td>{{ record.time }}</td>
            <td>{{ record.action }}</td>
            <td>{{ record.from ? `${record.from} → ${record.to}` : record.to }}</td>
            <td>{{ record.detail }}</td>
          </tr>
          <tr v-if="!history.length">
            <td colspan="4" class="empty-state">暂无处理记录</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchJson } from '@/api/client'

type Entry = Record<string, unknown>
type HistoryRecord = { time: string; action: string; from: string; to: string; detail: string }

const fields = ["供电编号", "所属站点", "供电方式", "蓄电池容量", "上次放电测试", "备电时长", "责任人员", "供电状态"]

const route = useRoute()
const router = useRouter()
const entry = ref<Entry | null>(null)
const errorMessage = ref('')

const missing = computed(() => (Array.isArray(entry.value?.missing_fields) ? (entry.value!.missing_fields as string[]) : []))
const history = computed(() => (Array.isArray(entry.value?.history) ? (entry.value!.history as HistoryRecord[]) : []))

function goBack() {
  void router.push('/power')
}

onMounted(async () => {
  try {
    entry.value = await fetchJson<Entry>(`/api/power/${route.params.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '供电单元详情读取失败'
  }
})
</script>
