<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { problemOf } from '../dev-api/problem'

const props = defineProps<{
	error: unknown
}>()

const { t } = useI18n()

const message = computed(() => {
	const problem = problemOf(props.error)
	if (problem.kind === 'refused' && problem.detail) return problem.detail
	if (problem.kind === 'unavailable') return t('api.unavailable')
	return t('api.rejected', { detail: problem.detail })
})
</script>

<template>
	<p role="alert" class="text-small text-contour">{{ message }}</p>
</template>
