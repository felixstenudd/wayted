<script setup lang="ts">
import { computed } from 'vue'

import { silhouette } from '../silhouette'

const props = defineProps<{ coordinates: readonly (readonly number[])[] }>()

const BOX = { width: 44, height: 32, padding: 5 }
// The start triangle, drawn around (0, 0) and moved to where the route starts.
const START = 'M0 -4.2 3.7 2.4H-3.7Z'

const shape = computed(() => silhouette(props.coordinates, BOX))
</script>

<template>
	<!-- The route's own outline: people know a loop by its shape before its name. -->
	<svg :viewBox="`0 0 ${BOX.width} ${BOX.height}`" class="h-8 w-11 shrink-0" aria-hidden="true">
		<template v-if="shape">
			<path
				:d="shape.path"
				class="fill-none stroke-ink"
				stroke-width="1.6"
				stroke-linecap="round"
				stroke-linejoin="round"
			/>
			<path
				:d="START"
				:transform="`translate(${shape.start.x} ${shape.start.y})`"
				class="fill-overprint stroke-overprint-contrast"
				stroke-width="1"
				stroke-linejoin="round"
			/>
		</template>
	</svg>
</template>
