<script setup lang="ts">
import ConfigField from './ConfigField.vue'
import type { Panel } from './bridge'

defineProps<{ panel: Panel }>()
</script>

<template>
  <ConfigField
    :panel="panel"
    group="Run"
    field="GameUpdateMode"
    kind="select"
    :choices="['Off', 'Check', 'AutoInstall']"
    :hint="panel.t('gameUpdateModeHint')"
  />
</template>
