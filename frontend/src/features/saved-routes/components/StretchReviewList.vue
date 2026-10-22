<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { computed, nextTick, onBeforeUnmount, useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { humanizeKey } from '@/features/route'
import { Button } from '@/shared/ui/button'

import { useReviewReasons, useSegmentReviews } from '../api'
import { formatDistanceKm, joinLabels } from '../format'
import { reviewSides } from '../reasons'
import { useSavedRoutesStore } from '../store'
import { junctions, reviewStretch } from '../stretch'
import type { SavedRoute } from '../types'
import StretchReviewRow from './StretchReviewRow.vue'

const props = defineProps<{
	route: SavedRoute
	/** Says "Stretch review saved" after a save, until the next change. */
	justSaved: boolean
}>()

const HEADING_ID = 'stretch-reviews-heading'

const i18n = useI18n()
const { t, locale } = i18n
const store = useSavedRoutesStore()
const reviews = useSegmentReviews(() => props.route.id)
const reasons = useReviewReasons()
const heading = useTemplateRef<HTMLElement>('heading')

const all = computed(() => junctions(props.route.edges))
const label = (code: string) =>
	i18n.te(`savedRoutes.reasons.${code}`) ? t(`savedRoutes.reasons.${code}`) : humanizeKey(code)
const sentence = (codes: readonly string[]) => joinLabels(codes.map(label), locale.value)

const rows = computed(() =>
	(reviews.data.value ?? []).flatMap((review) => {
		const stretch = reviewStretch(review)
		if (!stretch) return []
		const km = (junction: number) =>
			formatDistanceKm(all.value[junction]?.distanceM ?? 0, locale.value)
		const { good, bad } = reviewSides(review.reasons, reasons.data.value ?? [])
		return [
			{
				review,
				stretch,
				where: t('savedRoutes.stretch.range', {
					from: km(stretch.from),
					to: km(stretch.to),
				}),
				good: good.length > 0 ? sentence(good) : '',
				bad: bad.length > 0 ? sentence(bad) : '',
			},
		]
	}),
)

// The deleted row took focus with it; the list's heading is the nearest place to carry on from.
async function deleted(): Promise<void> {
	await nextTick()
	heading.value?.focus()
}

onBeforeUnmount(() => {
	store.highlightedReviewId = null
})
</script>

<template>
	<section :aria-labelledby="HEADING_ID" class="flex flex-col gap-2">
		<div class="flex flex-col gap-1">
			<h2 :id="HEADING_ID" ref="heading" tabindex="-1" class="text-title outline-none">
				{{ t('savedRoutes.stretch.yours') }}
			</h2>
			<p v-if="justSaved" role="status" class="text-small text-graphite">
				{{ t('savedRoutes.stretch.saved') }}
			</p>
		</div>

		<div v-if="reviews.isPending.value" class="flex flex-col gap-2" aria-hidden="true">
			<span v-for="row in 2" :key="row" class="h-10 rounded-sm bg-sunken" />
		</div>
		<div v-else-if="reviews.isError.value" role="alert" class="flex flex-col items-start gap-2">
			<p class="flex gap-1.5 text-small text-contour">
				<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ t('savedRoutes.stretch.loadFailed') }}
			</p>
			<Button variant="secondary" size="sm" @click="reviews.refetch()">
				{{ t('savedRoutes.tryAgain') }}
			</Button>
		</div>
		<p v-else-if="rows.length === 0" class="text-small text-graphite">
			{{ t('savedRoutes.stretch.empty') }}
		</p>
		<ul v-else class="flex flex-col divide-y divide-line">
			<StretchReviewRow
				v-for="row in rows"
				:key="row.review.id"
				:route-id="route.id"
				:review="row.review"
				:stretch="row.stretch"
				:where="row.where"
				:good="row.good"
				:bad="row.bad"
				@deleted="deleted"
			/>
		</ul>
	</section>
</template>
