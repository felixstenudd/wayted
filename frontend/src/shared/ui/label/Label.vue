<script setup lang="ts">
import type { HTMLAttributes } from 'vue'

import { cn } from '@/shared/utils/cn'

const props = defineProps<{
	class?: HTMLAttributes['class']
}>()
</script>

<template>
	<label
		data-slot="label"
		:class="
			cn(
				'text-small font-semibold text-ink select-none peer-disabled:cursor-not-allowed peer-disabled:opacity-50',
				props.class,
			)
		"
	>
		<slot />
	</label>
</template>
