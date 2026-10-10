<script setup lang="ts">
import 'maplibre-gl/dist/maplibre-gl.css'

import { useTemplateRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMap, type MapViewOptions } from '../composables/useMap'
import { useMapContext } from '../context'

const props = defineProps<MapViewOptions>()

const { t } = useI18n()
const container = useTemplateRef<HTMLElement>('container')
const { hasBaseMapFailed } = useMapContext()

useMap(container, props)
</script>

<template>
	<div class="relative size-full">
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
