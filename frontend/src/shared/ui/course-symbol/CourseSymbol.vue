<script setup lang="ts">
import type { CourseSymbolKind } from '.'

// Orienteering course notation: an open triangle for the start, a numbered
// circle for each control (waypoint), and a double circle for the finish.
// Fill is paper so a course line drawn underneath stops at the symbol's edge.
defineProps<{
	kind: CourseSymbolKind
	controlNumber?: number | undefined
}>()
</script>

<template>
	<svg
		viewBox="0 0 28 28"
		fill="none"
		stroke="currentColor"
		stroke-width="2.5"
		stroke-linejoin="round"
		class="text-overprint"
		aria-hidden="true"
	>
		<path v-if="kind === 'start'" d="M14 3.5 25 23.5H3Z" fill="var(--paper)" />
		<template v-else-if="kind === 'control'">
			<circle cx="14" cy="14" r="11.5" fill="var(--paper)" />
			<text
				v-if="controlNumber !== undefined"
				x="14"
				y="14"
				dy="0.35em"
				text-anchor="middle"
				fill="currentColor"
				stroke="none"
				class="text-caption font-bold tabular-nums"
			>
				{{ controlNumber }}
			</text>
		</template>
		<template v-else>
			<circle cx="14" cy="14" r="11.5" fill="var(--paper)" />
			<circle cx="14" cy="14" r="6" />
		</template>
	</svg>
</template>
