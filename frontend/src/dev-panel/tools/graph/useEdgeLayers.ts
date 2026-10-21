import { toValue, type MaybeRefOrGetter } from 'vue'

import {
	boundsPolygon,
	EMPTY,
	tokenColor,
	useMapFilter,
	useMapPaint,
	useMapSource,
	type Bounds,
} from '@/features/map'

import type { Graph } from '../../dev-api/types'
import { edgeColor, feedbackColor, scoreToken, toMapEdges, type ScoreRange } from './edges'

export const EDGE_LAYER = 'graph-edge'

const NO_EDGE = -1

/** Draws the loaded box, its edges coloured by one score or one activity's votes, and their vertices. */
export function useEdgeLayers(
	bounds: MaybeRefOrGetter<Bounds | undefined>,
	graph: MaybeRefOrGetter<Graph | undefined>,
	colorBy: MaybeRefOrGetter<string | null>,
	range: MaybeRefOrGetter<ScoreRange | null>,
	feedbackBy: MaybeRefOrGetter<string | null>,
	selectedId: MaybeRefOrGetter<number | null>,
) {
	const colors = {
		plain: tokenColor('--map-edge'),
		low: tokenColor('--map-score-low'),
		high: tokenColor('--map-score-high'),
	}

	useMapSource(
		'graph-area',
		() => {
			const box = toValue(bounds)
			return box ? boundsPolygon(box) : EMPTY
		},
		[
			{
				id: 'graph-area-outline',
				type: 'line',
				paint: {
					'line-color': tokenColor('--map-outline'),
					'line-width': 1,
					'line-dasharray': [4, 3],
				},
			},
		],
	)
	useMapSource(
		'graph-edges',
		() => {
			const loaded = toValue(graph)
			return loaded ? toMapEdges(loaded) : EMPTY
		},
		[
			{
				id: EDGE_LAYER,
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
		],
	)
	useMapSource('graph-vertices', () => toValue(graph)?.vertices ?? EMPTY, [
		{
			id: 'graph-vertex',
			type: 'circle',
			paint: { 'circle-radius': 2.5, 'circle-color': tokenColor('--map-vertex') },
		},
	])

	const feedbackColors = {
		plain: colors.plain,
		bad: tokenColor('--map-feedback-bad'),
		mixed: colors.low,
		good: tokenColor('--map-feedback-good'),
	}

	useMapPaint(EDGE_LAYER, 'line-color', () => {
		const activity = toValue(feedbackBy)
		if (activity !== null) return feedbackColor(activity, feedbackColors)
		const name = toValue(colorBy)
		const high = name === null ? colors.high : tokenColor(scoreToken(name))
		return edgeColor(name, toValue(range), { ...colors, high })
	})
	useMapFilter('graph-edge-selected', () => ['==', ['get', 'id'], toValue(selectedId) ?? NO_EDGE])
}
