<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'

defineProps<{
	message: string
}>()
</script>

<template>
	<p role="alert" class="flex gap-2 text-small text-contour">
		<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
		<span>{{ message }}</span>
	</p>
</template>
