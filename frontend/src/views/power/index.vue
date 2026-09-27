<template>
  <section class="page" data-module="power">
    <header class="page-head">
      <div>
        <h2>供电保障管理</h2>
        <p class="page-desc">维护供电单元，围绕供电编号、所属站点、供电方式、蓄电池容量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记供电单元</button>
        <button class="btn" type="button" @click="exportRows">导出供电保障清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>待补字段</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">
            <a v-if="column === '供电编号'" class="link" href="javascript:void 0" @click="openDetail(row)">
              {{ row[column] ?? '—' }}
            </a>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td>
            <span v-if="missingOf(row).length" class="error-text">缺：{{ missingOf(row).join('、') }}</span>
            <span v-else>—</span>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无供电保障数据，可先登记供电单元</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条供电保障记录</span>
      <span v-if="infoMessage" class="info-text">{{ infoMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, unknown> & { id?: number }

const ENDPOINT = '/api/power'
const columns = ["供电编号", "所属站点", "供电方式", "蓄电池容量", "上次放电测试", "备电时长", "责任人员", "供电状态"]
const actions = ["安排巡检", "确认正常", "标记断电"]

const router = useRouter()
const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref<{ label: string; value: number }[]>([])
const errorMessage = ref('')
const infoMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function missingOf(row: Row): string[] {
  return Array.isArray(row.missing_fields) ? (row.missing_fields as string[]) : []
}

function openDetail(row: Row) {
  void router.push(`/power/${row.id}`)
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '供电单元登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  infoMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '供电保障动作未生效，请稍后重试')
    }
    infoMessage.value = payload.message || ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '供电保障操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const [payload, statPayload] = await Promise.all([
      fetchJson<{ items?: Row[]; total?: number }>(`${ENDPOINT}?${query}`),
      fetchJson<{ items?: { label: string; value: number }[] }>(`${ENDPOINT}/stats`),
    ])
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value = statPayload.items ?? []
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '供电保障列表读取失败'
  }
}

onMounted(reload)
</script>
