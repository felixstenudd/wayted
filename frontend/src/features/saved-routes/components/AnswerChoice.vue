<script setup lang="ts">
import { RadioGroupItem, RadioGroupRoot } from 'reka-ui'
import { useI18n } from 'vue-i18n'

import { ANSWERS, type Answer } from '../review'

// Like SegmentedControl, but it starts with nothing chosen: a row is only answered on purpose.
defineProps<{ label: string }>()
const answer = defineModel<Answer | null>({ required: true })

const { t } = useI18n()
</script>

<template>
	<RadioGroupRoot
		:model-value="answer"
		:aria-label="label"
		orientation="horizontal"
		class="flex h-9 rounded-md bg-sunken p-0.5"
		@update:model-value="answer = $event as Answer"
	>
		<RadioGroupItem
			v-for="option in ANSWERS"
			:key="option.value"
			:value="option.value"
			class="flex flex-1 items-center justify-center rounded-sm border border-transparent text-small whitespace-nowrap text-graphite transition-[color,background-color,border-color] duration-150 ease-out hover:text-ink data-[state=checked]:border-line-strong data-[state=checked]:bg-paper data-[state=checked]:font-semibold data-[state=checked]:text-ink"
		>
			{{ t(`savedRoutes.review.answers.${option.key}`) }}
		</RadioGroupItem>
	</RadioGroupRoot>
</template>
