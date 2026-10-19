<script setup lang="ts">
import { Marker } from 'maplibre-gl'
import { onBeforeUnmount, useTemplateRef, watch } from 'vue'

import { useMapContext } from '../context'
import type { LonLat } from '../geometry'

const props = defineProps<{
	lonLat: LonLat
	/** What the marker stands for, read out by screen readers. */
	label: string
	draggable?: boolean
}>()
const emit = defineEmits<{ move: [to: LonLat] }>()

const element = useTemplateRef<HTMLElement>('element')
const { map, isReady } = useMapContext()
// Not reactive: MapLibre objects stay out of Vue's reactivity.
let marker: Marker | null = null

// MapLibre moves the element into the map, and Vue keeps rendering the slot into it.
watch(
	[isReady, element],
	([ready, el]) => {
		if (!ready || !el || !map.value || marker) return
		marker = new Marker({ element: el, draggable: props.draggable, anchor: 'center' })
			.setLngLat([props.lonLat.lon, props.lonLat.lat])
			.addTo(map.value)
		marker.on('dragend', () => {
			const at = marker?.getLngLat()
			if (at) emit('move', { lon: at.lng, lat: at.lat })
		})
	},
	{ immediate: true },
)

watch(
	() => props.lonLat,
	({ lon, lat }) => marker?.setLngLat([lon, lat]),
)

// Before Vue removes the element, so MapLibre lets go of it first.
onBeforeUnmount(() => {
	marker?.remove()
	marker = null
})
</script>

<template>
	<div ref="element" role="img" :aria-label="props.label">
		<slot />
	</div>
</template>
