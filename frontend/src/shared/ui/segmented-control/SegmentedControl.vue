<script setup lang="ts" generic="Value extends string">
import { RadioGroupItem, RadioGroupRoot } from 'reka-ui'

import type { SegmentedOption } from '.'

// A radio group drawn as joined buttons: one choice from a few, all in view.
defineProps<{
	/** Names the choice for screen readers. */
	label: string
	options: readonly SegmentedOption<Value>[]
}>()
const model = defineModel<Value>({ required: true })
</script>

<template>
	<RadioGroupRoot
		:model-value="model"
		:aria-label="label"
		orientation="horizontal"
		class="flex h-10 rounded-md bg-sunken p-0.5"
		@update:model-value="model = $event as Value"
	>
		<RadioGroupItem
			v-for="option in options"
			:key="option.value"
			:value="option.value"
			class="flex flex-1 items-center justify-center gap-1.5 rounded-sm border border-transparent text-small whitespace-nowrap text-graphite transition-[color,background-color,border-color] duration-150 ease-out hover:text-ink data-[state=checked]:border-line-strong data-[state=checked]:bg-paper data-[state=checked]:font-semibold data-[state=checked]:text-ink [&_svg]:size-4 [&_svg]:shrink-0"
		>
			<component :is="option.icon" v-if="option.icon" aria-hidden="true" />
			{{ option.label }}
		</RadioGroupItem>
	</RadioGroupRoot>
</template>
