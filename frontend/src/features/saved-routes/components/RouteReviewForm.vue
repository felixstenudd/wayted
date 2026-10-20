<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { AttributeSymbol, humanizeKey, useRouteAttributes } from '@/features/route-planner'
import { Button } from '@/shared/ui/button'

import { useSaveRouteReview } from '../api'
import { plannedFirst } from '../profile'
import { answeredOnly, type Answer, type PreferenceChange } from '../review'
import type { SavedRoute } from '../types'
import AnswerChoice from './AnswerChoice.vue'

const props = defineProps<{ route: SavedRoute; headingId: string }>()
const emit = defineEmits<{ saved: [changes: PreferenceChange[]]; cancel: [] }>()

const MAX_COMMENT = 500
// The count shows only near the limit, where it helps.
const COUNT_FROM = 450
const COMMENT_ID = 'route-review-comment'
const COMMENT_HINT_ID = 'route-review-comment-hint'

const i18n = useI18n()
const { t } = i18n
const attributes = useRouteAttributes()
const save = useSaveRouteReview(() => props.route.id)

const isEditing = computed(() => props.route.review !== null)
const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)

// Only what the router can steer; what the route was planned for comes first.
const rows = computed(() => {
	const scored = (attributes.data.value ?? []).filter((a) => a.scored).map((a) => a.key)
	return plannedFirst(scored, props.route.preferences, scored).map((key) => ({
		key,
		name: name(key),
	}))
})

const answers = ref<Record<string, Answer | null>>({ ...props.route.review?.answers })
const comment = ref(props.route.review?.comment ?? '')
const problem = ref<'unanswered' | 'failed' | null>(null)
watch(
	answers,
	() => {
		if (problem.value === 'unanswered') problem.value = null
	},
	{ deep: true },
)

async function submit(): Promise<void> {
	const answered = answeredOnly(answers.value)
	if (Object.keys(answered).length === 0) {
		problem.value = 'unanswered'
		return
	}
	problem.value = null
	try {
		const saved = await save.mutateAsync({
			answers: answered,
			comment: comment.value.trim() || null,
		})
		emit('saved', saved.preference_changes)
	} catch {
		problem.value = 'failed'
	}
}
</script>

<template>
	<form class="flex flex-col gap-5" @submit.prevent="submit">
		<div class="flex flex-col gap-1">
			<h1 :id="headingId" class="text-heading">
				{{ isEditing ? t('savedRoutes.review.editTitle') : t('savedRoutes.review.title') }}
			</h1>
			<p class="text-small text-graphite">
				{{ t('savedRoutes.review.lead', { name: route.name }) }}
			</p>
		</div>

		<div v-if="attributes.isPending.value" class="flex flex-col gap-4" aria-hidden="true">
			<span v-for="row in 3" :key="row" class="h-14 rounded-md bg-sunken" />
		</div>
		<ul v-else class="flex flex-col gap-4">
			<li v-for="row in rows" :key="row.key" class="flex flex-col gap-1.5">
				<span class="flex items-center gap-2 text-body font-semibold">
					<AttributeSymbol :attribute-key="row.key" />
					{{ row.name }}
				</span>
				<AnswerChoice
					:model-value="answers[row.key] ?? null"
					:label="row.name"
					@update:model-value="answers[row.key] = $event"
				/>
			</li>
		</ul>

		<div class="flex flex-col gap-1.5">
			<label :for="COMMENT_ID" class="text-small font-semibold">
				{{ t('savedRoutes.review.comment') }}
			</label>
			<textarea
				:id="COMMENT_ID"
				v-model="comment"
				:maxlength="MAX_COMMENT"
				:aria-describedby="COMMENT_HINT_ID"
				rows="3"
				class="w-full resize-y rounded-sm border border-line-strong bg-paper px-3 py-2 text-input text-ink transition-[border-color] duration-150 ease-out placeholder:text-graphite hover:border-graphite"
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
			{{ t(`savedRoutes.review.${problem}`) }}
		</p>

		<div class="flex gap-2">
			<Button type="submit" class="flex-1" :aria-busy="save.isPending.value">
				<template v-if="save.isPending.value">{{
					t('savedRoutes.review.saving')
				}}</template>
				<template v-else>
					{{
						isEditing
							? t('savedRoutes.review.saveChanges')
							: t('savedRoutes.review.save')
					}}
				</template>
			</Button>
			<Button type="button" variant="ghost" @click="emit('cancel')">
				{{ t('savedRoutes.review.cancel') }}
			</Button>
		</div>
	</form>
</template>
