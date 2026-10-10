<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { EMPTY, tokenColor, useMapSource, useMapView } from '@/features/map'
import { Button } from '@/shared/ui/button'

import ProblemMessage from '../../components/ProblemMessage.vue'
import ToolSection from '../../components/ToolSection.vue'
import { useQueuedTiles } from './api'
import { countByStatus, failedTiles, toMapTiles } from './queue'

const { t } = useI18n()
const { data: queued, error, isPending } = useQueuedTiles()
const { showBounds } = useMapView()

const counts = computed(() => (queued.value ? countByStatus(queued.value) : null))
const failed = computed(() => (queued.value ? failedTiles(queued.value) : []))
const isEmpty = computed(() => queued.value?.features.length === 0)

// The three statuses differ in line pattern and width, not only in colour.
useMapSource('queue', () => (queued.value ? toMapTiles(queued.value) : EMPTY), [
	{
		id: 'queue-pending',
		type: 'line',
		filter: ['==', ['get', 'status'], 'pending'],
		paint: {
			'line-color': tokenColor('--map-waiting'),
			'line-width': 2,
			'line-dasharray': [1, 2],
		},
	},
	{
		id: 'queue-running',
		type: 'line',
		filter: ['==', ['get', 'status'], 'running'],
		paint: { 'line-color': tokenColor('--map-running'), 'line-width': 2 },
	},
	{
		id: 'queue-failed',
		type: 'line',
		filter: ['==', ['get', 'status'], 'failed'],
		paint: { 'line-color': tokenColor('--map-failed'), 'line-width': 4 },
	},
])
</script>

<template>
	<ToolSection :title="t('queue.title')">
		<p v-if="isPending" class="text-small text-graphite">{{ t('queue.loading') }}</p>
		<ProblemMessage v-if="error" :error="error" />
		<p v-if="isEmpty" class="text-small text-graphite">{{ t('queue.empty') }}</p>

		<dl v-if="counts && !isEmpty" class="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1">
			<dt>{{ t('queue.pending') }}</dt>
			<dd class="text-right tabular-nums">{{ counts.pending }}</dd>
			<dt>{{ t('queue.running') }}</dt>
			<dd class="text-right tabular-nums">{{ counts.running }}</dd>
			<dt>{{ t('queue.failed') }}</dt>
			<dd class="text-right tabular-nums">{{ counts.failed }}</dd>
		</dl>

		<ul v-if="failed.length > 0" class="flex flex-col gap-3">
			<li v-for="tile in failed" :key="tile.id" class="flex flex-col gap-1 text-small">
				<p class="font-semibold">
					{{
						t('queue.failedTile', {
							layer: tile.layer,
							key: tile.key,
							count: tile.attempts,
						})
					}}
				</p>
				<p class="wrap-anywhere text-graphite">
					{{ tile.lastMessage ?? tile.lastStatus ?? t('queue.noReason') }}
				</p>
				<Button
					size="sm"
					variant="secondary"
					class="self-start"
					@click="showBounds(tile.bounds)"
				>
					{{ t('queue.show') }}
				</Button>
			</li>
		</ul>
	</ToolSection>
</template>
