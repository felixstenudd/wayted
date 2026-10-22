<script setup lang="ts">
import { computed, type DeepReadonly } from 'vue'
import { useI18n } from 'vue-i18n'

import { humanizeKey } from '@/features/route'
import { Button } from '@/shared/ui/button'

import { formatKm } from '../distance'
import type { RouteRequest } from '../types'

const props = defineProps<{
	/** What the shown routes were planned with. */
	request: DeepReadonly<RouteRequest>
	action: string
	/** While the settings below it are being changed: it names what the routes were found for. */
	isFoundFor?: boolean
}>()
defineEmits<{ action: [] }>()

const i18n = useI18n()
const { t } = i18n

const summary = computed(() =>
	t('planner.settingsLine.summary', {
		activity: t(`planner.activity.${props.request.activity}`),
		shape: t(`planner.settingsLine.shapes.${props.request.shape}`),
		distance:
			props.request.target_distance_m === undefined ||
			props.request.target_distance_m === null
				? t('planner.settingsLine.anyLength')
				: t('planner.route.length', {
						km: formatKm(props.request.target_distance_m / 1000),
					}),
	}),
)

const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)

// "Parks and water preferred, busy roads avoided": names after the first are lowercased.
const preferences = computed(() => {
	const list = new Intl.ListFormat(i18n.locale.value, { type: 'conjunction' })
	const names = (wanted: (weight: number) => boolean) =>
		Object.entries(props.request.preferences)
			.filter(([, weight]) => wanted(weight))
			.map(([key]) => name(key).toLocaleLowerCase(i18n.locale.value))
	const parts = [
		...[names((weight) => weight > 0)]
			.filter((preferred) => preferred.length > 0)
			.map((preferred) =>
				t('planner.settingsLine.preferred', { names: list.format(preferred) }),
			),
		...[names((weight) => weight < 0)]
			.filter((avoided) => avoided.length > 0)
			.map((avoided) => t('planner.settingsLine.avoided', { names: list.format(avoided) })),
	]
	const sentence = parts.join(', ') || t('planner.settingsLine.noPreferences')
	return sentence.charAt(0).toLocaleUpperCase(i18n.locale.value) + sentence.slice(1)
})
</script>

<template>
	<div class="flex items-center gap-3 rounded-md bg-sunken py-2.5 pr-1.5 pl-3">
		<div class="flex min-w-0 flex-1 flex-col">
			<span v-if="isFoundFor" class="text-small text-graphite">
				{{ t('planner.settingsLine.foundFor') }}
			</span>
			<span class="text-body font-semibold">{{ summary }}</span>
			<span class="text-small text-graphite">{{ preferences }}</span>
		</div>
		<Button variant="ghost" size="sm" class="hover:bg-line" @click="$emit('action')">
			{{ action }}
		</Button>
	</div>
</template>
