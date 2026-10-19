<script setup lang="ts">
import { CourseSymbol, type CourseSymbolKind } from '@/shared/ui/course-symbol'

defineProps<{
	kind: CourseSymbolKind
	label: string
	/** What the point's state is, and what to do next. */
	hint: string
}>()
</script>

<template>
	<div class="flex items-center gap-3">
		<CourseSymbol :kind="kind" class="size-6 shrink-0" />
		<div class="min-w-0 flex-1">
			<p class="text-body font-semibold">{{ label }}</p>
			<p class="text-small text-graphite">{{ hint }}</p>
		</div>
		<div class="flex shrink-0 items-center">
			<slot name="actions" />
		</div>
	</div>
</template>
