<script setup lang="ts">
import ConfigField from './ConfigField.vue'
import type { Panel } from './bridge'

defineProps<{ panel: Panel }>()
</script>

<template>
  <ConfigField
    :panel="panel"
    group="Run"
    field="LoginMode"
    kind="select"
    :choices="['Project', 'Mas']"
    :hint="panel.t('loginModeHint')"
  />
</template>
