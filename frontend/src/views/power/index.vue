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
      <label class="filter-item">
        <span>供电编号</span>
        <input v-model="keyword" placeholder="按供电编号检索" />
      </label>
      <label class="filter-item">
        <span>供电状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="actionBusy"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <RouterLink class="link" :to="`/power/${row.id}`">详情</RouterLink>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无供电保障数据，可先登记供电单元</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条供电保障记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/power'
const columns = ["供电编号", "所属站点", "供电方式", "蓄电池容量", "上次放电测试", "备电时长", "责任人员", "供电状态"]
const actions = ["安排巡检", "确认正常", "标记断电"]
const statuses = ["待巡检", "巡检中", "供电正常", "备电不足", "已断电"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([{ label: "在册供电单元", value: 0 }, { label: "备电不足", value: 0 }, { label: "已断电站点", value: 0 }])
const errorMessage = ref('')
const noticeMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const actionBusy = ref(false)

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '供电单元登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  if (actionBusy.value) return
  actionBusy.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message ?? '供电保障动作未生效，请稍后重试')
    }
    noticeMessage.value = result.message ?? `供电单元已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '供电保障操作失败'
  } finally {
    actionBusy.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const [listResponse, statsResponse] = await Promise.all([
      request(`${ENDPOINT}?${query}`),
      request(`${ENDPOINT}/stats`),
    ])
    if (!listResponse.ok) {
      throw new Error('供电单元列表读取失败')
    }
    const payload = await listResponse.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    if (statsResponse.ok) {
      const summary = await statsResponse.json()
      stats.value = stats.value.map((item) => ({ ...item, value: summary[item.label] ?? 0 }))
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '供电保障列表读取失败'
  }
}

onMounted(reload)
</script>
