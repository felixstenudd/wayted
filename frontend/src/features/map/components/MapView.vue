<script setup lang="ts">
import 'maplibre-gl/dist/maplibre-gl.css'

import { useTemplateRef, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMap, type MapViewOptions } from '../composables/useMap'
import { useMapContext } from '../context'

const props = defineProps<
	MapViewOptions & {
		/** Lifts the bottom controls above something covering the map, such as a sheet. */
		controlsBottomPx?: number
		/** How far something covers the map from the left, such as a floating panel. */
		coveredLeftPx?: number
	}
>()

const { t } = useI18n()
const container = useTemplateRef<HTMLElement>('container')
const { hasBaseMapFailed, coveredPx } = useMapContext()

useMap(container, props)
watchEffect(() => {
	coveredPx.value = { left: props.coveredLeftPx ?? 0, bottom: props.controlsBottomPx ?? 0 }
})
</script>

<template>
	<div
		class="relative size-full"
		:style="{ '--controls-bottom': `${props.controlsBottomPx ?? 0}px` }"
	>
		<!-- MapLibre makes its container position: relative, so it is sized, not positioned. -->
		<div ref="container" class="size-full" />
		<p
			v-if="hasBaseMapFailed"
			role="alert"
			class="absolute top-3 left-3 rounded-md bg-paper px-3 py-2 text-small text-contour shadow-float"
		>
			{{ t('map.baseMapFailed') }}
		</p>
	</div>
</template>

<style scoped>
/* Never above half the map, so tall covers hide the controls instead of pushing them to the top. */
:deep(.maplibregl-ctrl-bottom-left),
:deep(.maplibregl-ctrl-bottom-right) {
	bottom: min(var(--controls-bottom), 50%);
}

/*
 * MapLibre's buttons redrawn in our tokens. Their icons are images in a fixed
 * grey, so they become masks filled with ink and follow the theme. The scale bar
 * and credits keep MapLibre's look: they belong to the map, which stays light in
 * both themes.
 */
:deep(.maplibregl-map) {
	font-family: inherit;
}

:deep(.maplibregl-ctrl-group) {
	overflow: hidden;
	border-radius: 9999px;
	background: var(--paper);
	box-shadow: var(--elevation-float);
}

:deep(.maplibregl-ctrl-group button) {
	width: 2.5rem;
	height: 2.5rem;
	transition: background-color 150ms var(--ease-out, ease-out);
}

:deep(.maplibregl-ctrl-group button + button) {
	border-top: 1px solid var(--line);
}

:deep(.maplibregl-ctrl button:not(:disabled):hover) {
	background-color: var(--sunken);
}

/* The group clips anything outside it, so the focus ring is drawn inside. */
:deep(.maplibregl-ctrl button:focus:focus-visible) {
	box-shadow: none;
	outline-offset: -3px;
}

:deep(.maplibregl-ctrl button.maplibregl-ctrl-zoom-in .maplibregl-ctrl-icon),
:deep(.maplibregl-ctrl button.maplibregl-ctrl-zoom-out .maplibregl-ctrl-icon) {
	background-image: none;
	background-color: var(--ink);
	mask: center / 1.125rem no-repeat;
}

:deep(.maplibregl-ctrl button.maplibregl-ctrl-zoom-in .maplibregl-ctrl-icon) {
	mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='M12 5v14M5 12h14'/%3E%3C/svg%3E");
}

:deep(.maplibregl-ctrl button.maplibregl-ctrl-zoom-out .maplibregl-ctrl-icon) {
	mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='M5 12h14'/%3E%3C/svg%3E");
}

:deep(.maplibregl-ctrl-attrib.maplibregl-compact) {
	/* Small enough that the credits fit on one line on a phone while shown. */
	font-size: 0.625rem;
}
</style>
