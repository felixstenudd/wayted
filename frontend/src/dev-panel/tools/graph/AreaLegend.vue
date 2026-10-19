<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { fillOpacity, isDotted, layerToken } from './areas'

const props = defineProps<{
	layers: string[]
}>()

const i18n = useI18n()
const { t } = i18n

// The swatch repeats how the map draws the layer: a pale fill inside its edge.
const entries = computed(() =>
	props.layers.map((layer) => ({
		layer,
		name: i18n.te(`graph.legend.${layer}`) ? t(`graph.legend.${layer}`) : layer,
		edge: isDotted(layer) ? t('graph.legend.dotted') : t('graph.legend.solid'),
		style: {
			backgroundColor: `color-mix(in oklch, var(${layerToken(layer)}) ${fillOpacity(layer) * 100}%, transparent)`,
			borderColor: `var(${layerToken(layer)})`,
			borderStyle: isDotted(layer) ? 'dotted' : 'solid',
		},
	})),
)
</script>

<template>
	<div class="flex flex-col gap-1">
		<h3 class="text-small text-graphite">{{ t('graph.legend.title') }}</h3>
		<ul class="flex flex-col gap-1 text-small">
			<li v-for="entry in entries" :key="entry.layer" class="flex items-center gap-2">
				<span class="rounded-xs size-4 border-2" :style="entry.style" aria-hidden="true" />
				<span>{{ entry.name }}</span>
				<span class="text-graphite">{{ entry.edge }}</span>
			</li>
		</ul>
	</div>
</template>
