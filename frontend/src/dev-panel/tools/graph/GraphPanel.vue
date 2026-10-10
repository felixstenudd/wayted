<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	boundsPolygon,
	EMPTY,
	tokenColor,
	useMapClick,
	useMapFilter,
	useMapPaint,
	useMapSource,
	useMapView,
} from '@/features/map'
import { Button } from '@/shared/ui/button'

import ProblemMessage from '../../components/ProblemMessage.vue'
import ToolSection from '../../components/ToolSection.vue'
import { useGraph } from './api'
import EdgeDetails from './EdgeDetails.vue'
import { edgeColor, scoreNames, scoreRange, toMapEdges } from './edges'

const NO_EDGE = -1

const { t } = useI18n()
const { bounds: view } = useMapView()
const { loaded, error, isFetching, load } = useGraph()
const graph = computed(() => loaded.value?.graph)

function loadView() {
	if (view.value) load(view.value)
}

const edgeCount = computed(() => graph.value?.edges.features.length ?? 0)
const vertexCount = computed(() => graph.value?.vertices.features.length ?? 0)

const names = computed(() => (graph.value ? scoreNames(graph.value) : []))
const colorBy = ref<string | null>(null)
watch(names, (next) => {
	if (colorBy.value !== null && !next.includes(colorBy.value)) colorBy.value = null
})
const range = computed(() =>
	graph.value && colorBy.value !== null ? scoreRange(graph.value, colorBy.value) : null,
)

const selectedId = ref<number | null>(null)
const edgesById = computed(
	() => new Map(graph.value?.edges.features.map((edge) => [edge.properties.id, edge.properties])),
)
const selected = computed(() =>
	selectedId.value === null ? null : (edgesById.value.get(selectedId.value) ?? null),
)

const colors = {
	plain: tokenColor('--map-edge'),
	low: tokenColor('--map-score-low'),
	high: tokenColor('--map-score-high'),
}
useMapSource('graph-area', () => (loaded.value ? boundsPolygon(loaded.value.bounds) : EMPTY), [
	{
		id: 'graph-area-outline',
		type: 'line',
		paint: {
			'line-color': tokenColor('--map-outline'),
			'line-width': 1,
			'line-dasharray': [4, 3],
		},
	},
])
useMapSource('graph-edges', () => (graph.value ? toMapEdges(graph.value) : EMPTY), [
	{
		id: 'graph-edge',
		type: 'line',
		layout: { 'line-cap': 'round' },
		paint: { 'line-color': colors.plain, 'line-width': 2 },
	},
	{
		id: 'graph-edge-selected',
		type: 'line',
		layout: { 'line-cap': 'round' },
		filter: ['==', ['get', 'id'], NO_EDGE],
		paint: { 'line-color': tokenColor('--map-selected'), 'line-width': 6 },
	},
])
useMapSource('graph-vertices', () => graph.value?.vertices ?? EMPTY, [
	{
		id: 'graph-vertex',
		type: 'circle',
		paint: { 'circle-radius': 2.5, 'circle-color': tokenColor('--map-vertex') },
	},
])
useMapPaint('graph-edge', 'line-color', () => edgeColor(colorBy.value, range.value, colors))
useMapFilter('graph-edge-selected', () => ['==', ['get', 'id'], selectedId.value ?? NO_EDGE])
useMapClick(['graph-edge'], (feature) => {
	const id = feature?.properties.id
	selectedId.value = typeof id === 'number' ? id : null
})
</script>

<template>
	<ToolSection :title="t('graph.title')">
		<Button size="sm" class="self-start" :disabled="!view || isFetching" @click="loadView">
			{{ isFetching ? t('graph.loading') : t('graph.load') }}
		</Button>
		<ProblemMessage v-if="error" :error="error" />
		<p v-if="!graph && !error && !isFetching" class="text-small text-graphite">
			{{ t('graph.notLoaded') }}
		</p>
		<p v-if="graph && edgeCount === 0" class="text-small text-graphite">
			{{ t('graph.empty') }}
		</p>

		<template v-if="graph && edgeCount > 0">
			<p>{{ t('graph.counts', { edges: edgeCount, vertices: vertexCount }) }}</p>

			<div class="flex flex-col gap-1">
				<label for="graph-color-by" class="text-small text-graphite">
					{{ t('graph.colorBy') }}
				</label>
				<select
					id="graph-color-by"
					v-model="colorBy"
					class="h-8 rounded-sm border border-line-strong bg-paper px-2"
					:disabled="names.length === 0"
				>
					<option :value="null">
						{{ names.length === 0 ? t('graph.noScores') : t('graph.oneColor') }}
					</option>
					<option v-for="name in names" :key="name" :value="name">{{ name }}</option>
				</select>
				<p v-if="range" class="flex items-center gap-2 text-small">
					<span class="size-3 rounded-sm bg-(--map-score-low)" aria-hidden="true" />
					{{ t('graph.lowest', { value: range.min }) }}
					<span class="size-3 rounded-sm bg-(--map-score-high)" aria-hidden="true" />
					{{ t('graph.highest', { value: range.max }) }}
				</p>
			</div>

			<EdgeDetails v-if="selected" :edge="selected" />
			<p v-else class="text-small text-graphite">{{ t('graph.selectEdge') }}</p>
		</template>
	</ToolSection>
</template>
