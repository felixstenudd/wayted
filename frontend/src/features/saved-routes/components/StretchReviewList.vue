<script setup lang="ts">
import { CircleAlert, Ellipsis, PenLine, Trash2 } from '@lucide/vue'
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { humanizeKey } from '@/features/route-planner'
import { Button } from '@/shared/ui/button'
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

import { useDeleteSegmentReview, useReviewReasons, useSegmentReviews } from '../api'
import { formatDistanceKm } from '../format'
import { useSavedRoutesStore } from '../store'
import { junctions, reviewStretch } from '../stretch'
import type { SavedRoute, SegmentReview } from '../types'

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
const remove = useDeleteSegmentReview(() => props.route.id)
const reasons = useReviewReasons()
const hasDeleteFailed = ref(false)

const all = computed(() => junctions(props.route.edges))
// Good things first, then bad, each in the order the reasons list them.
const goodFirst = (codes: readonly string[]) => {
	const order = (reasons.data.value ?? []).map((r) => r.code)
	const sentiment = (code: string) =>
		reasons.data.value?.find((r) => r.code === code)?.sentiment ?? 0
	return [...codes].sort(
		(a, b) => sentiment(b) - sentiment(a) || order.indexOf(a) - order.indexOf(b),
	)
}
const label = (code: string) =>
	i18n.te(`savedRoutes.reasons.${code}`) ? t(`savedRoutes.reasons.${code}`) : humanizeKey(code)

const rows = computed(() =>
	(reviews.data.value ?? []).flatMap((review) => {
		const stretch = reviewStretch(review)
		if (!stretch) return []
		const km = (junction: number) =>
			formatDistanceKm(all.value[junction]?.distanceM ?? 0, locale.value)
		return [
			{
				review,
				stretch,
				where: t('savedRoutes.stretch.range', {
					from: km(stretch.from),
					to: km(stretch.to),
				}),
				said: new Intl.ListFormat(locale.value, { type: 'conjunction' }).format(
					goodFirst(review.reasons).map(label),
				),
			},
		]
	}),
)

function edit(review: SegmentReview, from: number, to: number): void {
	store.editStretchReview(review.id, from, to)
}

async function deleteReview(id: number): Promise<void> {
	hasDeleteFailed.value = false
	try {
		await remove.mutateAsync(id)
	} catch {
		hasDeleteFailed.value = true
	}
}

onBeforeUnmount(() => {
	store.highlightedReviewId = null
})
</script>

<template>
	<section :aria-labelledby="HEADING_ID" class="flex flex-col gap-2">
		<div class="flex items-baseline justify-between gap-3">
			<h2 :id="HEADING_ID" class="text-title">{{ t('savedRoutes.stretch.yours') }}</h2>
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
			<li
				v-for="row in rows"
				:key="row.review.id"
				class="-mx-2 flex items-center gap-2 rounded-md px-2 py-2 transition-[background-color] duration-150 ease-out"
				:class="{ 'bg-sunken': store.highlightedReviewId === row.review.id }"
				@pointerenter="store.highlightedReviewId = row.review.id"
				@pointerleave="store.highlightedReviewId = null"
			>
				<div class="min-w-0 flex-1">
					<p class="text-small font-semibold">{{ row.where }}</p>
					<p class="text-small text-graphite">{{ row.said }}</p>
				</div>
				<DropdownMenu>
					<DropdownMenuTrigger as-child>
						<Button
							variant="ghost"
							size="icon"
							class="-my-1.5"
							:aria-label="t('savedRoutes.stretch.more', { where: row.where })"
						>
							<Ellipsis />
						</Button>
					</DropdownMenuTrigger>
					<DropdownMenuContent align="end" class="w-44">
						<DropdownMenuItem
							@select="edit(row.review, row.stretch.from, row.stretch.to)"
						>
							<PenLine />
							{{ t('savedRoutes.stretch.edit') }}
						</DropdownMenuItem>
						<DropdownMenuItem @select="deleteReview(row.review.id)">
							<Trash2 />
							{{ t('savedRoutes.stretch.delete') }}
						</DropdownMenuItem>
					</DropdownMenuContent>
				</DropdownMenu>
			</li>
		</ul>
		<p v-if="hasDeleteFailed" class="flex gap-1.5 text-small text-contour" role="alert">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t('savedRoutes.stretch.deleteFailed') }}
		</p>
	</section>
</template>
