<script setup lang="ts">
import { CourseSymbol } from '../course-symbol'
</script>

<template>
	<span class="inline-flex items-center gap-2 text-title font-extrabold tracking-tight text-ink">
		<CourseSymbol kind="start" class="size-5" />
		<slot />
	</span>
</template>
