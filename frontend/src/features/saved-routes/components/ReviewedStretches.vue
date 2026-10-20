<script setup lang="ts">
import { ThumbsDown, ThumbsUp } from '@lucide/vue'
import type { ExpressionSpecification } from 'maplibre-gl'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { MapMarker, tokenColor, useMapPaint, useMapSource, type MapData } from '@/features/map'

import { useReviewReasons, useSavedRoute, useSegmentReviews } from '../api'
import { lineEnds } from '../chevrons'
import { formatDistanceKm } from '../format'
import { reviewSides, reviewTone } from '../reasons'
import { useSavedRoutesStore } from '../store'
import { junctions, pointAlong, reviewStretch } from '../stretch'
import type { SegmentReview } from '../types'

const props = defineProps<{
	routeId: number
	/** Stepped back behind a stretch being picked; the pills would be in the way of taps. */
	dimmed: boolean
}>()

const NO_REVIEW = -1
// Matches the bracket's line-offset, so the ticks close it.
const OFFSET_PX = 11

const { t, locale } = useI18n()
const store = useSavedRoutesStore()
const saved = useSavedRoute(() => props.routeId)
const reviews = useSegmentReviews(() => props.routeId)
const reasons = useReviewReasons()

const all = computed(() => junctions(saved.data.value?.edges ?? []))
function where(review: SegmentReview): string {
	const stretch = reviewStretch(review)
	if (!stretch) return ''
	const km = (junction: number) =>
		formatDistanceKm(all.value[junction]?.distanceM ?? 0, locale.value)
	return t('savedRoutes.stretch.range', { from: km(stretch.from), to: km(stretch.to) })
}

const brackets = computed<MapData>(() => ({
	type: 'FeatureCollection',
	features: (reviews.data.value ?? []).map((review) => ({
		type: 'Feature',
		geometry: review.geometry,
		properties: { id: review.id },
	})),
}))

const ticks = computed(() =>
	(reviews.data.value ?? []).flatMap((review) =>
		lineEnds(review.geometry.coordinates).map((end, index) => ({
			key: `${review.id}-${index}`,
			reviewId: review.id,
			...end,
		})),
	),
)

const pills = computed(() =>
	(reviews.data.value ?? []).flatMap((review) => {
		const at = pointAlong(review.geometry.coordinates)
		if (!at) return []
		const tone = reviewTone(reviewSides(review.reasons, reasons.data.value ?? []))
		const label = t(`savedRoutes.stretch.pill.${tone}`, { where: where(review) })
		return [{ id: review.id, at, tone, label }]
	}),
)

// Your marks sit beside the course like pencil notes, closed by a tick at each end; the one the
// list points at is drawn heavier.
useMapSource('saved-route-reviews', brackets, [
	{
		id: 'saved-route-reviews',
		type: 'line',
		layout: { 'line-cap': 'butt', 'line-join': 'round' },
		paint: {
			'line-color': tokenColor('--graphite'),
			'line-width': 2,
			'line-offset': OFFSET_PX,
		},
	},
])
useMapPaint('saved-route-reviews', 'line-width', (): ExpressionSpecification => [
	'case',
	['==', ['get', 'id'], store.highlightedReviewId ?? NO_REVIEW],
	4,
	2,
])
useMapPaint('saved-route-reviews', 'line-opacity', () => (props.dimmed ? 0.35 : 1))
</script>

<template>
	<!-- Turned to the line's direction, each tick reaches from the bracket towards the course. -->
	<MapMarker v-for="tick in ticks" :key="tick.key" :lon-lat="tick.at">
		<svg
			viewBox="0 0 32 32"
			class="size-8"
			:class="{ 'opacity-35': dimmed }"
			:style="{ transform: `rotate(${tick.bearingDeg - 90}deg)` }"
		>
			<path
				:d="`M16 ${16 + OFFSET_PX + 1}V20`"
				class="stroke-graphite"
				:stroke-width="store.highlightedReviewId === tick.reviewId ? 4 : 2"
			/>
		</svg>
	</MapMarker>
	<template v-if="!dimmed">
		<MapMarker v-for="pill in pills" :key="pill.id" :lon-lat="pill.at" control>
			<button
				type="button"
				class="group grid size-11 place-items-center rounded-full"
				:aria-label="pill.label"
				@click="store.revealReview(pill.id)"
			>
				<span
					class="flex items-center gap-1 rounded-full border bg-paper px-1.5 py-1 shadow-float transition-[border-color] duration-150 ease-out group-hover:border-graphite"
					:class="store.highlightedReviewId === pill.id ? 'border-ink' : 'border-line'"
				>
					<ThumbsUp
						v-if="pill.tone !== 'bad'"
						class="size-3.5 text-vegetation"
						aria-hidden="true"
					/>
					<ThumbsDown
						v-if="pill.tone !== 'good'"
						class="size-3.5 text-contour"
						aria-hidden="true"
					/>
				</span>
			</button>
		</MapMarker>
	</template>
</template>
