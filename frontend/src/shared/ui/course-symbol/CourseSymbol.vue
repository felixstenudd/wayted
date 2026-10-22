<script setup lang="ts">
import type { CourseSymbolKind } from '.'

// Orienteering course notation: a triangle for the start, a numbered circle
// for each control (waypoint), and a double circle for the finish. Filled with
// overprint and edged in overprint-contrast so they read on light and dark
// grounds alike, and a course line drawn underneath stops at the edge.
defineProps<{
	kind: CourseSymbolKind
	controlNumber?: number | undefined
	/** A control the course no longer visits: drawn hollow, the map showing through, as left out. */
	missed?: boolean
}>()
</script>

<template>
	<svg
		viewBox="0 0 28 28"
		stroke="currentColor"
		stroke-width="2.5"
		stroke-linejoin="round"
		:class="missed ? 'fill-none' : 'fill-overprint'"
		class="text-overprint-contrast"
		aria-hidden="true"
	>
		<path v-if="kind === 'start'" d="M14 3.5 25 23.5H3Z" />
		<template v-else-if="kind === 'control'">
			<circle cx="14" cy="14" r="11.5" />
			<text
				v-if="controlNumber !== undefined"
				x="14"
				y="14"
				dy="0.35em"
				text-anchor="middle"
				fill="currentColor"
				stroke="none"
				class="text-caption font-bold"
			>
				{{ controlNumber }}
			</text>
		</template>
		<template v-else>
			<circle cx="14" cy="14" r="11.5" />
			<circle cx="14" cy="14" r="6" />
		</template>
	</svg>
</template>
