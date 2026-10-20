<script setup lang="ts">
import { TriangleAlert } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { humanizeKey } from '../attributes'
import { formatKm } from '../distance'
import type { Route } from '../types'

const props = defineProps<{
	route: Route
	targetM: number
}>()

const i18n = useI18n()
const { t } = i18n

const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)

// Shares that round to 0 % say nothing.
const shares = computed(() => {
	const percent = new Intl.NumberFormat(i18n.locale.value, { style: 'percent' })
	return Object.entries(props.route.properties.scores)
		.filter(([, share]) => share >= 0.005)
		.sort(([, a], [, b]) => b - a)
		.map(([key, share]) =>
			t('planner.route.share', { name: name(key), percent: percent.format(share) }),
		)
})
</script>

<template>
	<div role="status" class="flex flex-col gap-1 text-small">
		<p>
			<span class="font-semibold">
				{{ t('planner.route.length', { km: formatKm(route.properties.length_m / 1000) }) }}
			</span>
			<template v-for="share in shares" :key="share"> · {{ share }}</template>
		</p>
		<p
			v-for="warning in route.properties.warnings"
			:key="warning"
			class="flex gap-1.5 text-graphite"
		>
			<TriangleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t(`planner.route.warnings.${warning}`, { km: formatKm(targetM / 1000) }) }}
		</p>
	</div>
</template>
