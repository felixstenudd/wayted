<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMapClick, useMapView } from '@/features/map'
import { Button } from '@/shared/ui/button'

import ProblemMessage from '../../components/ProblemMessage.vue'
import ToolSection from '../../components/ToolSection.vue'
import { useGraph } from './api'
import AreaDetails from './AreaDetails.vue'
import AreaLegend from './AreaLegend.vue'
import { areaKey } from './areas'
import EdgeDetails from './EdgeDetails.vue'
import { colorScale, isFixedScale, scoredCount, scoreNames, scoreToken } from './edges'
import { AREA_FILL_LAYER, useAreaLayers } from './useAreaLayers'
import { EDGE_LAYER, useEdgeLayers } from './useEdgeLayers'
import { LINE_LAYER, useLineLayers } from './useLineLayers'

const { t } = useI18n()
const { bounds: view } = useMapView()
const { loaded, error, isFetching, load } = useGraph()
const graph = computed(() => loaded.value?.graph)
const areas = computed(() => loaded.value?.areas)
const lines = computed(() => loaded.value?.lines)

function loadView() {
	if (view.value) load(view.value)
}

const edgeCount = computed(() => graph.value?.edges.features.length ?? 0)
const vertexCount = computed(() => graph.value?.vertices.features.length ?? 0)
const areaCount = computed(() => areas.value?.features.length ?? 0)
const lineCount = computed(() => lines.value?.features.length ?? 0)

const names = computed(() => (graph.value ? scoreNames(graph.value) : []))
const colorBy = ref<string | null>(null)
watch(names, (next) => {
	if (colorBy.value !== null && !next.includes(colorBy.value)) colorBy.value = null
})
const range = computed(() =>
	graph.value && colorBy.value !== null ? colorScale(graph.value, colorBy.value) : null,
)
const fixedScale = computed(() => colorBy.value !== null && isFixedScale(colorBy.value))
const scored = computed(() =>
	names.value.map((name) => ({ name, count: graph.value ? scoredCount(graph.value, name) : 0 })),
)

const selectedId = ref<number | null>(null)
const edgesById = computed(
	() => new Map(graph.value?.edges.features.map((edge) => [edge.properties.id, edge.properties])),
)
const selected = computed(() =>
	selectedId.value === null ? null : (edgesById.value.get(selectedId.value) ?? null),
)
const selectedAreaKey = ref<string | null>(null)
// Lines share the areas' properties and keys, so one map finds either.
const areasByKey = computed(
	() =>
		new Map(
			[...(areas.value?.features ?? []), ...(lines.value?.features ?? [])].map((feature) => [
				areaKey(feature.properties),
				feature.properties,
			]),
		),
)
const selectedArea = computed(() =>
	selectedAreaKey.value === null ? null : (areasByKey.value.get(selectedAreaKey.value) ?? null),
)

const hiddenLayers = ref<string[]>([])
// A hidden area can no longer be seen, so it is no longer selected either.
watch(hiddenLayers, (hidden) => {
	if (selectedArea.value && hidden.includes(selectedArea.value.layer))
		selectedAreaKey.value = null
})

// Areas first, then lines, so edges are drawn above both.
const { layersInView: areaLayersInView } = useAreaLayers(areas, hiddenLayers, selectedAreaKey)
const { layersInView: lineLayersInView } = useLineLayers(lines, hiddenLayers, selectedAreaKey)
const layersInView = computed(() =>
	[...new Set([...areaLayersInView.value, ...lineLayersInView.value])].sort(),
)
useEdgeLayers(() => loaded.value?.bounds, graph, colorBy, range, selectedId)
// Edges are drawn above areas, so a click on an edge inside an area selects the edge.
useMapClick([EDGE_LAYER, LINE_LAYER, AREA_FILL_LAYER], (feature) => {
	const id = feature?.layerId === EDGE_LAYER ? feature.properties.id : null
	const key =
		feature?.layerId === AREA_FILL_LAYER || feature?.layerId === LINE_LAYER
			? feature.properties.key
			: null
	selectedId.value = typeof id === 'number' ? id : null
	selectedAreaKey.value = typeof key === 'string' ? key : null
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
			<p>
				{{
					t('graph.counts', {
						edges: edgeCount,
						vertices: vertexCount,
						areas: areaCount,
						lines: lineCount,
					})
				}}
			</p>
			<p v-for="score in scored" :key="score.name" class="text-small">
				{{ t('graph.scored', { name: score.name, count: score.count, edges: edgeCount }) }}
			</p>
			<AreaLegend
				v-if="layersInView.length > 0"
				v-model:hidden="hiddenLayers"
				:layers="layersInView"
				:line-layers="lineLayersInView"
			/>

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
				<template v-if="range">
					<p class="flex items-center gap-2 text-small">
						<span class="size-3 rounded-sm bg-(--map-score-low)" aria-hidden="true" />
						{{ range.min }}
						<span
							class="size-3 rounded-sm"
							:style="{ backgroundColor: `var(${scoreToken(colorBy ?? '')})` }"
							aria-hidden="true"
						/>
						{{ range.max }}
					</p>
					<p class="text-small text-graphite">
						{{ fixedScale ? t('graph.fixedScale') : t('graph.viewScale') }}
					</p>
				</template>
			</div>

			<EdgeDetails v-if="selected" :edge="selected" />
			<AreaDetails v-else-if="selectedArea" :area="selectedArea" />
			<p v-else class="text-small text-graphite">{{ t('graph.selectEdge') }}</p>
		</template>
	</ToolSection>
</template>
