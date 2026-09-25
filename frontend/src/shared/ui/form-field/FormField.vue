<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { computed } from 'vue'

import { Label } from '../label'

const props = defineProps<{
	id: string
	label: string
	hint?: string | undefined
	error?: string | undefined
}>()

defineSlots<{
	default(props: { describedBy: string | undefined; invalid: boolean }): unknown
}>()

const hintId = computed(() => `${props.id}-hint`)
const errorId = computed(() => `${props.id}-error`)

// The error replaces the hint while it is shown; it already states the rule.
const describedBy = computed(() => {
	if (props.error) return errorId.value
	if (props.hint) return hintId.value
	return undefined
})
</script>

<template>
	<div class="flex flex-col gap-1.5">
		<Label :for="id">{{ label }}</Label>
		<slot v-bind="{ describedBy, invalid: Boolean(error) }" />
		<p v-if="error" :id="errorId" class="flex gap-1.5 text-small text-contour">
			<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
			<span>{{ error }}</span>
		</p>
		<p v-else-if="hint" :id="hintId" class="text-small text-graphite">{{ hint }}</p>
	</div>
</template>
