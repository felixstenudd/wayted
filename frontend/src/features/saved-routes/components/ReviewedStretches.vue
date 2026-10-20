<script setup lang="ts">
import { ThumbsDown, ThumbsUp } from '@lucide/vue'
import type { ExpressionSpecification } from 'maplibre-gl'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { MapMarker, tokenColor, useMapPaint, useMapSource, type MapData } from '@/features/map'

import { useReviewReasons, useSegmentReviews } from '../api'
import { voteCounts } from '../reasons'
import { useSavedRoutesStore } from '../store'
import { pointAlong } from '../stretch'

const props = defineProps<{ routeId: number }>()

const NO_REVIEW = -1

const { t } = useI18n()
const store = useSavedRoutesStore()
const reviews = useSegmentReviews(() => props.routeId)
const reasons = useReviewReasons()

const brackets = computed<MapData>(() => ({
	type: 'FeatureCollection',
	features: (reviews.data.value ?? []).map((review) => ({
		type: 'Feature',
		geometry: review.geometry,
		properties: { id: review.id },
	})),
}))

const pills = computed(() =>
	(reviews.data.value ?? []).flatMap((review) => {
		const at = pointAlong(review.geometry.coordinates)
		if (!at) return []
		const { up, down } = voteCounts(review.reasons, reasons.data.value ?? [])
		return [
			{ id: review.id, at, up, down, label: t('savedRoutes.stretch.votes', { up, down }) },
		]
	}),
)

// Your marks sit beside the course like pencil notes; the one the list points at is drawn heavier.
useMapSource('saved-route-reviews', brackets, [
	{
		id: 'saved-route-reviews',
		type: 'line',
		layout: { 'line-cap': 'butt', 'line-join': 'round' },
		paint: {
			'line-color': tokenColor('--overprint-contrast'),
			'line-width': 2,
			'line-offset': 11,
		},
	},
])
useMapPaint('saved-route-reviews', 'line-width', (): ExpressionSpecification => [
	'case',
	['==', ['get', 'id'], store.highlightedReviewId ?? NO_REVIEW],
	4,
	2,
])
</script>

<template>
	<MapMarker v-for="pill in pills" :key="pill.id" :lon-lat="pill.at" :label="pill.label">
		<span
			class="flex items-center gap-1 rounded-full border border-line bg-paper px-1.5 py-0.5 text-caption font-semibold text-ink shadow-float"
			:class="{ 'border-ink': store.highlightedReviewId === pill.id }"
		>
			<template v-if="pill.up > 0">
				<ThumbsUp class="size-3 text-vegetation" aria-hidden="true" />
				{{ pill.up }}
			</template>
			<template v-if="pill.down > 0">
				<ThumbsDown class="size-3 text-contour" aria-hidden="true" />
				{{ pill.down }}
			</template>
		</span>
	</MapMarker>
</template>
