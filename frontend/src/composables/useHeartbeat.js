import { onMounted, onUnmounted } from 'vue'
import { presenceApi } from '@/api'

const HEARTBEAT_INTERVAL_MS = 15000

export function useHeartbeat() {
  let timer = null

  async function sendHeartbeat() {
    try {
      await presenceApi.heartbeat()
    } catch {
      // 网络波动时忽略，下次重试
    }
  }

  onMounted(() => {
    sendHeartbeat()
    timer = setInterval(sendHeartbeat, HEARTBEAT_INTERVAL_MS)
  })

  onUnmounted(() => {
    if (timer) {
      clearInterval(timer)
      timer = null
    }
  })
}
