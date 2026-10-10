<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	boundsPolygon,
	circlePolygon,
	EMPTY,
	tokenColor,
	useCircleDraw,
	useMapSource,
} from '@/features/map'
import { Button } from '@/shared/ui/button'

import ProblemMessage from '../../components/ProblemMessage.vue'
import ToolSection from '../../components/ToolSection.vue'
import { formatKm } from '../../format'
import { useRequestArea } from './api'

// The dev API's limit on radius_m.
const MAX_RADIUS_M = 40_000

const { t } = useI18n()
const isDrawing = ref(false)
const refetch = ref(false)
const { circle } = useCircleDraw(isDrawing, MAX_RADIUS_M)
const { mutate, data: result, error, isPending, reset } = useRequestArea()

const isAtLimit = computed(() => circle.value?.radiusM === MAX_RADIUS_M)

function toggleDrawing() {
	isDrawing.value = !isDrawing.value
	if (isDrawing.value) reset()
}

function request() {
	if (!circle.value) return
	isDrawing.value = false
	mutate({
		lat: circle.value.center.lat,
		lon: circle.value.center.lon,
		radius_m: circle.value.radiusM,
		refetch: refetch.value,
	})
}

const outline = tokenColor('--map-outline')
useMapSource('request-circle', () => (circle.value ? circlePolygon(circle.value) : EMPTY), [
	{
		id: 'request-circle-fill',
		type: 'fill',
		paint: { 'fill-color': outline, 'fill-opacity': 0.08 },
	},
	{
		id: 'request-circle-outline',
		type: 'line',
		paint: { 'line-color': outline, 'line-width': 2 },
	},
])
useMapSource('request-bounds', () => (result.value ? boundsPolygon(result.value.bounds) : EMPTY), [
	{
		id: 'request-bounds-outline',
		type: 'line',
		paint: { 'line-color': outline, 'line-width': 1, 'line-dasharray': [4, 3] },
	},
])
</script>

<template>
	<ToolSection :title="t('request.title')">
		<Button
			size="sm"
			variant="secondary"
			class="self-start"
			:aria-pressed="isDrawing"
			@click="toggleDrawing"
		>
			{{ isDrawing ? t('request.stopDrawing') : t('request.draw') }}
		</Button>
		<p v-if="isDrawing" class="text-small text-graphite">{{ t('request.howToDraw') }}</p>
		<p v-else-if="!circle" class="text-small text-graphite">{{ t('request.noCircle') }}</p>

		<template v-if="circle">
			<p>{{ t('request.radius', { km: formatKm(circle.radiusM) }) }}</p>
			<p v-if="isAtLimit" class="text-small text-graphite">
				{{ t('request.atLimit', { km: formatKm(MAX_RADIUS_M) }) }}
			</p>
			<label class="flex items-center gap-2">
				<input v-model="refetch" type="checkbox" class="size-4 accent-ink" />
				{{ t('request.refetch') }}
			</label>
			<Button size="sm" class="self-start" :disabled="isPending" @click="request">
				{{ isPending ? t('request.requesting') : t('request.submit') }}
			</Button>
		</template>

		<ProblemMessage v-if="error" :error="error" />
		<p v-if="result" role="status">
			{{
				result.queued > 0
					? t('request.queued', { count: result.queued })
					: t('request.nothingQueued')
			}}
		</p>
	</ToolSection>
</template>
