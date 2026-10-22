<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { humanizeKey, weightWord } from '@/features/route'
import { Button } from '@/shared/ui/button'

import { changeKind, sliderPercent, type PreferenceChange } from '../review'

const props = defineProps<{ changes: PreferenceChange[] }>()

const i18n = useI18n()
const { t } = i18n

const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)

const lines = computed(() =>
	props.changes.map((change) => {
		const kind = changeKind(change)
		return {
			key: change.attribute,
			text: t(`savedRoutes.review.notice.${kind}`, {
				name: name(change.attribute),
				weight: t(`planner.preferences.weights.${weightWord(change.after)}`),
			}),
			before: sliderPercent(change.before),
			after: sliderPercent(change.after),
			hasMoved: kind !== 'atEnd',
		}
	}),
)
</script>

<template>
	<div role="status" class="flex flex-col gap-2 rounded-md bg-sunken p-3">
		<p class="font-semibold">{{ t('savedRoutes.review.notice.title') }}</p>
		<p v-if="lines.length === 0" class="text-small text-graphite">
			{{ t('savedRoutes.review.notice.unchanged') }}
		</p>
		<ul v-else class="flex flex-col gap-1.5">
			<li
				v-for="line in lines"
				:key="line.key"
				class="flex items-center justify-between gap-3"
			>
				<span class="text-small">{{ line.text }}</span>
				<!-- The slider in small: where the weight was, hollow, and where it is now. -->
				<span class="relative h-3 w-24 shrink-0" aria-hidden="true">
					<span
						class="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 rounded-full bg-line-strong"
					/>
					<span class="absolute top-0 left-1/2 h-3 w-px bg-graphite" />
					<span
						v-if="line.hasMoved"
						class="absolute top-1/2 size-2.5 -translate-1/2 rounded-full border-[1.5px] border-graphite bg-paper"
						:style="{ left: `${line.before}%` }"
					/>
					<span
						class="absolute top-1/2 size-2.5 -translate-1/2 rounded-full bg-ink"
						:style="{ left: `${line.after}%` }"
					/>
				</span>
			</li>
		</ul>
		<Button variant="link" as-child class="self-start text-small">
			<RouterLink :to="{ name: 'planner' }">{{
				t('savedRoutes.review.notice.openPlanner')
			}}</RouterLink>
		</Button>
	</div>
</template>
