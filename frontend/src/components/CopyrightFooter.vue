<template>
  <footer class="copyright-footer" :class="{ light }">
    <span>微机教室在线考试系统</span>
    <span class="dot">·</span>
    <span>版权所有 © {{ year }} 柴延明</span>
    <span class="dot">·</span>
    <span>保留所有权利</span>
  </footer>
</template>

<script setup>
defineProps({
  light: { type: Boolean, default: false },
})

const year = new Date().getFullYear()
</script>

<style scoped>
.copyright-footer {
  text-align: center;
  padding: 16px 0 8px;
  font-size: 12px;
  color: #9ca3af;
}

.copyright-footer.light {
  color: #a5b4fc;
  padding-top: 12px;
}

.dot { margin: 0 6px; }
</style>
