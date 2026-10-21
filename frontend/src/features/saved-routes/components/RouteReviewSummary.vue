<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { humanizeKey, plannedFirst, useRouteAttributes } from '@/features/route'
import { Button } from '@/shared/ui/button'

import { ANSWERS } from '../review'
import type { SavedRoute } from '../types'

const props = defineProps<{ route: SavedRoute }>()
const emit = defineEmits<{ edit: [] }>()

const HEADING_ID = 'route-review-heading'

const i18n = useI18n()
const { t } = i18n
const attributes = useRouteAttributes()

const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)

const answers = computed(() => {
	const given = props.route.review?.answers ?? {}
	const order = (attributes.data.value ?? []).map((a) => a.key)
	return plannedFirst(Object.keys(given), props.route.preferences, order).map((key) => {
		const answer = ANSWERS.find((a) => a.value === given[key])
		return {
			key,
			name: name(key),
			answer: answer ? t(`savedRoutes.review.said.${answer.key}`) : '',
		}
	})
})
</script>

<template>
	<section v-if="route.review" :aria-labelledby="HEADING_ID" class="flex flex-col gap-2">
		<div class="flex items-baseline justify-between gap-3">
			<h2 :id="HEADING_ID" class="text-title">{{ t('savedRoutes.review.yours') }}</h2>
			<Button variant="link" class="text-small" @click="emit('edit')">
				{{ t('savedRoutes.review.edit') }}
			</Button>
		</div>
		<dl class="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-small">
			<template v-for="row in answers" :key="row.key">
				<dt class="text-graphite">{{ row.name }}</dt>
				<dd>{{ row.answer }}</dd>
			</template>
		</dl>
		<p v-if="route.review.comment" class="text-small wrap-break-word whitespace-pre-line">
			{{ route.review.comment }}
		</p>
	</section>
</template>
