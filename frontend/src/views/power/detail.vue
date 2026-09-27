<template>
  <section class="page" data-module="power-detail">
    <header class="page-head">
      <div>
        <h2>供电单元详情</h2>
        <p class="page-desc">与列表页读取同一份数据，含完整处理记录。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回列表</button>
      </div>
    </header>

    <template v-if="entry">
      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in fields" :key="field">
            <th>{{ field }}</th>
            <td>{{ entry[field] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <h3 class="section-title">处理记录</h3>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in historyColumns" :key="column">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(record, index) in history" :key="index">
            <td v-for="column in historyColumns" :key="column">{{ record[column] ?? '—' }}</td>
          </tr>
          <tr v-if="!history.length">
            <td :colspan="historyColumns.length" class="empty-state">暂无处理记录</td>
          </tr>
        </tbody>
      </table>
    </template>

    <footer class="page-foot">
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchJson } from '@/api/client'

type Entry = Record<string, string | number | null> & { history?: Record<string, string>[] }

const route = useRoute()
const router = useRouter()

const fields = ["供电编号", "所属站点", "供电方式", "蓄电池容量", "上次放电测试", "备电时长", "责任人员", "供电状态"]
const historyColumns = ["时间", "动作", "状态变化", "说明"]

const entry = ref<Entry | null>(null)
const errorMessage = ref('')

const history = computed(() => entry.value?.history ?? [])

function goBack() {
  router.push('/power')
}

onMounted(async () => {
  try {
    entry.value = await fetchJson<Entry>(`/api/power/${route.params.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '供电单元详情读取失败'
  }
})
</script>
