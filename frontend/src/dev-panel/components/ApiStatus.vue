<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { useHealth } from '../dev-api/health'
import ProblemMessage from './ProblemMessage.vue'

const { t } = useI18n()
const { isPending, error } = useHealth()
</script>

<template>
	<p v-if="isPending" class="text-small text-graphite">{{ t('api.checking') }}</p>
	<ProblemMessage v-else-if="error" :error="error" />
	<p v-else class="text-small text-graphite">{{ t('api.connected') }}</p>
</template>
