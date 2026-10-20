<script setup lang="ts">
import { CircleAlert, Ellipsis, PenLine, ThumbsDown, ThumbsUp, Trash2 } from '@lucide/vue'
import { nextTick, ref, useTemplateRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { Button } from '@/shared/ui/button'
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from '@/shared/ui/dropdown-menu'

import { useDeleteSegmentReview } from '../api'
import { useSavedRoutesStore } from '../store'
import type { Stretch } from '../stretch'
import type { SegmentReview } from '../types'

const props = defineProps<{
	routeId: number
	review: SegmentReview
	stretch: Stretch
	/** Where along the route, such as "1.2 to 2.0 km". */
	where: string
	/** What was good and what was bad, each as one sentence; empty when nothing was. */
	good: string
	bad: string
}>()
const emit = defineEmits<{ deleted: [] }>()

const { t } = useI18n()
const store = useSavedRoutesStore()
const remove = useDeleteSegmentReview(() => props.routeId)
const isConfirming = ref(false)
const hasFailed = ref(false)
const row = useTemplateRef<HTMLElement>('row')
const question = useTemplateRef<HTMLElement>('question')
const moreId = `stretch-review-more-${props.review.id}`
const prefersLessMotion = useMediaQuery('(prefers-reduced-motion: reduce)')

// Picked on the map: the row comes into view, so it is clear which review that was.
watch(
	() => store.revealedReviewId,
	async (id) => {
		if (id !== props.review.id) return
		store.revealedReviewId = null
		await nextTick()
		row.value?.scrollIntoView({
			block: 'nearest',
			behavior: prefersLessMotion.value ? 'auto' : 'smooth',
		})
	},
)

function highlight(isOn: boolean): void {
	if (isOn) store.highlightedReviewId = props.review.id
	else if (store.highlightedReviewId === props.review.id) store.highlightedReviewId = null
}

// Focus leaving for somewhere inside the row, such as its menu, still points at this review.
function blur(event: FocusEvent): void {
	if (!row.value?.contains(event.relatedTarget as Node | null)) highlight(false)
}

async function askToDelete(): Promise<void> {
	hasFailed.value = false
	isConfirming.value = true
	await nextTick()
	question.value?.focus()
}

async function keep(): Promise<void> {
	isConfirming.value = false
	await nextTick()
	document.getElementById(moreId)?.focus()
}

async function confirm(): Promise<void> {
	if (remove.isPending.value) return
	hasFailed.value = false
	try {
		await remove.mutateAsync(props.review.id)
		emit('deleted')
	} catch {
		hasFailed.value = true
	}
}
</script>

<template>
	<li
		ref="row"
		class="-mx-2 flex items-start gap-2 rounded-md px-2 py-2 transition-[background-color] duration-150 ease-out"
		:class="{ 'bg-sunken': store.highlightedReviewId === review.id }"
		@pointerenter="highlight(true)"
		@pointerleave="highlight(false)"
		@focusin="highlight(true)"
		@focusout="blur"
	>
		<div v-if="!isConfirming" class="flex min-w-0 flex-1 flex-col gap-0.5">
			<p class="text-small font-semibold">{{ where }}</p>
			<p v-if="good" class="flex gap-1.5 text-small">
				<ThumbsUp class="mt-0.5 size-3.5 shrink-0 text-vegetation" aria-hidden="true" />
				<span>
					<span class="sr-only">{{ t('savedRoutes.stretch.good') }}: </span>{{ good }}
				</span>
			</p>
			<p v-if="bad" class="flex gap-1.5 text-small">
				<ThumbsDown class="mt-0.5 size-3.5 shrink-0 text-contour" aria-hidden="true" />
				<span>
					<span class="sr-only">{{ t('savedRoutes.stretch.bad') }}: </span>{{ bad }}
				</span>
			</p>
		</div>
		<DropdownMenu v-if="!isConfirming">
			<DropdownMenuTrigger as-child>
				<Button
					:id="moreId"
					variant="ghost"
					size="icon"
					class="-my-1.5"
					:aria-label="t('savedRoutes.stretch.more', { where })"
				>
					<Ellipsis />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end" class="w-44">
				<DropdownMenuItem
					@select="store.editStretchReview(review.id, stretch.from, stretch.to)"
				>
					<PenLine />
					{{ t('savedRoutes.stretch.edit') }}
				</DropdownMenuItem>
				<DropdownMenuItem @select="askToDelete">
					<Trash2 />
					{{ t('savedRoutes.stretch.delete') }}
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>

		<div v-else class="flex flex-1 flex-col gap-3">
			<p ref="question" tabindex="-1" class="text-small outline-none">
				{{ t('savedRoutes.stretch.deleteQuestion', { where }) }}
			</p>
			<p v-if="hasFailed" class="flex gap-1.5 text-small text-contour" role="alert">
				<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ t('savedRoutes.stretch.deleteFailed') }}
			</p>
			<div class="flex gap-2">
				<Button size="sm" :aria-busy="remove.isPending.value" @click="confirm">
					{{
						remove.isPending.value
							? t('savedRoutes.stretch.deleting')
							: t('savedRoutes.stretch.deleteConfirm')
					}}
				</Button>
				<Button variant="ghost" size="sm" @click="keep">
					{{ t('savedRoutes.stretch.keep') }}
				</Button>
			</div>
		</div>
	</li>
</template>
