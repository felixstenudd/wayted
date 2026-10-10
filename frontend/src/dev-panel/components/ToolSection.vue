<script setup lang="ts">
defineProps<{
	title: string
}>()
</script>

<template>
	<section class="flex flex-col gap-3 border-t border-line px-4 py-4">
		<h2 class="text-title">{{ title }}</h2>
		<slot />
	</section>
</template>
