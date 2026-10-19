import { computed, toValue, type MaybeRefOrGetter } from 'vue'

import { EMPTY, tokenColor, useMapFilter, useMapPaint, useMapSource } from '@/features/map'

import type { Areas } from '../../dev-api/types'
import {
	areaLayers,
	byLayer,
	fillOpacity,
	isDotted,
	layerFilter,
	layerToken,
	toMapAreas,
} from './areas'

export const AREA_FILL_LAYER = 'graph-area-fill'

const NO_AREA = ''

/** Draws the areas in their layer's colour and edge, leaving out hidden layers. */
export function useAreaLayers(
	areas: MaybeRefOrGetter<Areas | undefined>,
	hidden: MaybeRefOrGetter<string[]>,
	selectedKey: MaybeRefOrGetter<string | null>,
) {
	const layersInView = computed(() => {
		const loaded = toValue(areas)
		return loaded ? areaLayers(loaded) : []
	})
	const shown = computed(() =>
		layersInView.value.filter((layer) => !toValue(hidden).includes(layer)),
	)
	const color = () =>
		byLayer(
			layersInView.value,
			(layer) => tokenColor(layerToken(layer)),
			tokenColor('--map-area'),
		)

	useMapSource(
		'graph-areas',
		() => {
			const loaded = toValue(areas)
			return loaded ? toMapAreas(loaded) : EMPTY
		},
		[
			{ id: AREA_FILL_LAYER, type: 'fill' },
			{ id: 'graph-area-line', type: 'line', paint: { 'line-width': 1.5 } },
			{
				id: 'graph-area-dotted',
				type: 'line',
				layout: { 'line-cap': 'round' },
				paint: { 'line-width': 2, 'line-dasharray': [0, 2] },
			},
			{
				id: 'graph-area-selected',
				type: 'line',
				filter: ['==', ['get', 'key'], NO_AREA],
				paint: { 'line-color': tokenColor('--map-selected'), 'line-width': 3 },
			},
		],
	)
	useMapPaint(AREA_FILL_LAYER, 'fill-color', color)
	useMapPaint(AREA_FILL_LAYER, 'fill-opacity', () =>
		byLayer(layersInView.value, fillOpacity, fillOpacity('')),
	)
	useMapPaint('graph-area-line', 'line-color', color)
	useMapPaint('graph-area-dotted', 'line-color', color)
	useMapFilter(AREA_FILL_LAYER, () => layerFilter(shown.value))
	useMapFilter('graph-area-line', () =>
		layerFilter(shown.value.filter((layer) => !isDotted(layer))),
	)
	useMapFilter('graph-area-dotted', () => layerFilter(shown.value.filter(isDotted)))
	useMapFilter('graph-area-selected', () => [
		'==',
		['get', 'key'],
		toValue(selectedKey) ?? NO_AREA,
	])

	return { layersInView }
}
