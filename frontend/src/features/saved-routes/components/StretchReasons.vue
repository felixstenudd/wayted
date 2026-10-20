<script setup lang="ts">
import { Check, ChevronLeft, CircleAlert, Info } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { AttributeSymbol, humanizeKey } from '@/features/route-planner'
import { Button } from '@/shared/ui/button'

import { useReviewReasons, useSaveSegmentReview, useSegmentReviews } from '../api'
import { useStretchPick } from '../composables/useStretchPick'
import { formatDistanceKm } from '../format'
import { reasonsBySide, toggleReason } from '../reasons'
import { useSavedRoutesStore } from '../store'
import { edgeRange, overlaps, reviewStretch } from '../stretch'
import type { SavedRoute } from '../types'

const props = defineProps<{ route: SavedRoute; headingId: string }>()
const emit = defineEmits<{ saved: [] }>()

const MAX_COMMENT = 500
const COUNT_FROM = 450
const COMMENT_ID = 'stretch-review-comment'
const COMMENT_HINT_ID = 'stretch-review-comment-hint'

const i18n = useI18n()
const { t, locale } = i18n
const store = useSavedRoutesStore()
const pick = useStretchPick(() => props.route.id)
const reasons = useReviewReasons()
const reviews = useSegmentReviews(() => props.route.id)
const save = useSaveSegmentReview(() => props.route.id)

const editing = computed(
	() => reviews.data.value?.find((r) => r.id === store.editingReviewId) ?? null,
)
const selected = ref<string[]>([...(editing.value?.reasons ?? [])])
const comment = ref(editing.value?.comment ?? '')
const problem = ref<'nothing' | 'failed' | null>(null)
watch(selected, () => {
	if (problem.value === 'nothing') problem.value = null
})

const sides = computed(() => reasonsBySide(reasons.data.value ?? []))
const label = (code: string) =>
	i18n.te(`savedRoutes.reasons.${code}`) ? t(`savedRoutes.reasons.${code}`) : humanizeKey(code)

const km = (junction: number) =>
	formatDistanceKm(pick.junctions.value[junction]?.distanceM ?? 0, locale.value)
const where = computed(() => {
	const stretch = pick.stretch.value
	if (!stretch) return ''
	return t('savedRoutes.stretch.where', {
		length: formatDistanceKm(pick.lengthM.value, locale.value),
		from: km(stretch.from),
		to: km(stretch.to),
	})
})
// Another review of the same edges is replaced topic by topic; saying so avoids a surprise.
const overlapsEarlier = computed(() => {
	const stretch = pick.stretch.value
	if (!stretch) return false
	return (reviews.data.value ?? []).some((review) => {
		const other = reviewStretch(review)
		return review.id !== store.editingReviewId && other !== null && overlaps(stretch, other)
	})
})

async function submit(): Promise<void> {
	const stretch = pick.stretch.value
	if (!stretch) return
	if (selected.value.length === 0) {
		problem.value = 'nothing'
		return
	}
	problem.value = null
	const body = { reasons: selected.value, comment: comment.value.trim() || null }
	try {
		await save.mutateAsync(
			store.editingReviewId === null
				? { ...body, reviewId: null, ...edgeRange(stretch) }
				: { ...body, reviewId: store.editingReviewId },
		)
		store.stopPickingStretch()
		emit('saved')
	} catch {
		problem.value = 'failed'
	}
}
</script>

<template>
	<form class="flex flex-col gap-5" @submit.prevent="submit">
		<div class="flex flex-col gap-1">
			<button
				v-if="store.editingReviewId === null"
				type="button"
				class="-ml-1 flex items-center gap-1 self-start rounded-sm text-small font-semibold text-graphite transition-[color] duration-150 ease-out hover:text-ink"
				@click="store.backToStretchPick()"
			>
				<ChevronLeft class="size-4" aria-hidden="true" />
				{{ t('savedRoutes.stretch.change') }}
			</button>
			<h1 :id="headingId" class="text-heading">
				{{ t('savedRoutes.stretch.reasonsTitle') }}
			</h1>
			<p class="text-small text-graphite">{{ where }}</p>
		</div>

		<p v-if="overlapsEarlier" class="flex gap-1.5 text-small text-graphite">
			<Info class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t('savedRoutes.stretch.overlap') }}
		</p>

		<div v-if="reasons.isPending.value" class="flex flex-col gap-3" aria-hidden="true">
			<span class="h-4 w-28 rounded-sm bg-sunken" />
			<span class="h-16 rounded-sm bg-sunken" />
		</div>
		<div v-else-if="reasons.isError.value" role="alert" class="flex flex-col items-start gap-2">
			<p class="flex gap-1.5 text-small text-contour">
				<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ t('savedRoutes.stretch.reasonsFailed') }}
			</p>
			<Button variant="secondary" size="sm" @click="reasons.refetch()">
				{{ t('savedRoutes.tryAgain') }}
			</Button>
		</div>
		<template v-else>
			<fieldset
				v-for="side in ['good', 'bad'] as const"
				:key="side"
				class="flex flex-col gap-2"
			>
				<legend class="mb-2 text-small font-semibold">
					{{ t(`savedRoutes.stretch.${side}`) }}
				</legend>
				<div class="flex flex-wrap gap-1.5">
					<button
						v-for="reason in sides[side]"
						:key="reason.code"
						type="button"
						:aria-pressed="selected.includes(reason.code)"
						class="flex items-center gap-1.5 rounded-sm border border-line-strong px-2 py-1 text-small transition-[color,background-color,border-color] duration-150 ease-out hover:border-graphite aria-pressed:border-ink aria-pressed:bg-ink aria-pressed:text-paper"
						@click="
							selected = toggleReason(selected, reason.code, reasons.data.value ?? [])
						"
					>
						<Check
							v-if="selected.includes(reason.code)"
							class="size-3.5 shrink-0"
							aria-hidden="true"
						/>
						<AttributeSymbol
							v-else-if="reason.attribute"
							:attribute-key="reason.attribute"
						/>
						{{ label(reason.code) }}
					</button>
				</div>
			</fieldset>
		</template>

		<div class="flex flex-col gap-1.5">
			<label :for="COMMENT_ID" class="text-small font-semibold">
				{{ t('savedRoutes.review.comment') }}
			</label>
			<textarea
				:id="COMMENT_ID"
				v-model="comment"
				:maxlength="MAX_COMMENT"
				:aria-describedby="COMMENT_HINT_ID"
				rows="2"
				class="w-full resize-y rounded-sm border border-line-strong bg-paper px-3 py-2 text-input text-ink transition-[border-color] duration-150 ease-out hover:border-graphite"
			/>
			<p :id="COMMENT_HINT_ID" class="flex justify-between gap-3 text-small text-graphite">
				<span>{{ t('savedRoutes.review.commentHint') }}</span>
				<span v-if="comment.length >= COUNT_FROM">
					{{
						t('savedRoutes.review.commentCount', {
							count: comment.length,
							max: MAX_COMMENT,
						})
					}}
				</span>
			</p>
		</div>

		<p v-if="problem" class="flex gap-1.5 text-small text-contour" role="alert">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			{{ t(`savedRoutes.stretch.${problem}`) }}
		</p>

		<div class="flex gap-2">
			<Button type="submit" class="flex-1" :aria-busy="save.isPending.value">
				<template v-if="save.isPending.value">{{
					t('savedRoutes.review.saving')
				}}</template>
				<template v-else>
					{{
						store.editingReviewId === null
							? t('savedRoutes.review.save')
							: t('savedRoutes.review.saveChanges')
					}}
				</template>
			</Button>
			<Button type="button" variant="ghost" @click="store.stopPickingStretch()">
				{{ t('savedRoutes.stretch.cancel') }}
			</Button>
		</div>
	</form>
</template>
