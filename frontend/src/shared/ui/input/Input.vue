<script setup lang="ts" generic="Value extends string | number">
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = defineProps<{
	class?: HTMLAttributes['class']
}>()

const model = defineModel<Value>({ required: true })
</script>

<template>
	<input
		v-model="model"
		data-slot="input"
		:class="
			cn(
				'h-10 w-full min-w-0 rounded-sm border border-line-strong bg-paper px-3 text-input text-ink transition-colors duration-150 ease-out placeholder:text-graphite hover:border-graphite disabled:cursor-not-allowed disabled:bg-sunken disabled:text-graphite aria-invalid:border-contour',
				props.class,
			)
		"
	/>
</template>
