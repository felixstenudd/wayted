import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { EMPTY, tokenColor, useMapFilter, useMapPaint, useMapSource } from '@/features/map'

import type { Lines } from '../../dev-api/types'
import { areaLayers, byLayer, layerFilter, layerToken, toMapAreas } from './areas'

export const LINE_LAYER = 'graph-line'

const NO_LINE = ''

/** Draws the lines in their layer's colour, leaving out hidden layers. */
export function useLineLayers(
	lines: MaybeRefOrGetter<Lines | undefined>,
	hidden: MaybeRefOrGetter<string[]>,
	selectedKey: MaybeRefOrGetter<string | null>,
) {
	const layersInView = computed(() => {
		const loaded = toValue(lines)
		return loaded ? areaLayers(loaded) : []
	})

	useMapSource(
		'graph-lines',
		() => {
			const loaded = toValue(lines)
			return loaded ? toMapAreas(loaded) : EMPTY
		},
		[
			{
				id: LINE_LAYER,
				type: 'line',
				layout: { 'line-cap': 'round', 'line-join': 'round' },
				paint: { 'line-width': 2 },
			},
			{
				id: 'graph-line-selected',
				type: 'line',
				filter: ['==', ['get', 'key'], NO_LINE],
				paint: { 'line-color': tokenColor('--map-selected'), 'line-width': 4 },
			},
		],
	)
	useMapPaint(LINE_LAYER, 'line-color', () =>
		byLayer(
			layersInView.value,
			(layer) => tokenColor(layerToken(layer)),
			tokenColor('--map-area'),
		),
	)
	useMapFilter(LINE_LAYER, () =>
		layerFilter(layersInView.value.filter((layer) => !toValue(hidden).includes(layer))),
	)
	useMapFilter('graph-line-selected', () => [
		'==',
		['get', 'key'],
		toValue(selectedKey) ?? NO_LINE,
	])

	return { layersInView }
}
