<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { fillOpacity, isDotted, layerToken } from './areas'

const props = defineProps<{
	layers: string[]
	// drawn as lines, not as areas
	lineLayers: string[]
}>()
const hidden = defineModel<string[]>('hidden', { required: true })

const i18n = useI18n()
const { t } = i18n

// The swatch repeats how the map draws the layer: a pale fill inside its edge, or the line.
const entries = computed(() =>
	props.layers.map((layer) => ({
		layer,
		name: i18n.te(`graph.legend.${layer}`) ? t(`graph.legend.${layer}`) : layer,
		isLine: props.lineLayers.includes(layer),
		edge: props.lineLayers.includes(layer)
			? t('graph.legend.line')
			: isDotted(layer)
				? t('graph.legend.dotted')
				: t('graph.legend.solid'),
		lineStyle: { backgroundColor: `var(${layerToken(layer)})` },
		style: {
			backgroundColor: `color-mix(in oklch, var(${layerToken(layer)}) ${fillOpacity(layer) * 100}%, transparent)`,
			borderColor: `var(${layerToken(layer)})`,
			borderStyle: isDotted(layer) ? 'dotted' : 'solid',
		},
	})),
)

function toggle(layer: string, event: Event) {
	if (!(event.target instanceof HTMLInputElement)) return
	hidden.value = event.target.checked
		? hidden.value.filter((other) => other !== layer)
		: [...hidden.value, layer]
}
</script>

<template>
	<fieldset class="flex flex-col gap-1">
		<legend class="mb-1 text-small text-graphite">{{ t('graph.legend.title') }}</legend>
		<label
			v-for="entry in entries"
			:key="entry.layer"
			class="flex items-center gap-2 text-small"
		>
			<input
				type="checkbox"
				:value="entry.layer"
				:checked="!hidden.includes(entry.layer)"
				class="size-4 accent-ink"
				@change="toggle(entry.layer, $event)"
			/>
			<span v-if="entry.isLine" class="flex size-4 items-center" aria-hidden="true">
				<span class="h-0.5 w-full" :style="entry.lineStyle" />
			</span>
			<span
				v-else
				class="rounded-xs size-4 border-2"
				:style="entry.style"
				aria-hidden="true"
			/>
			<span>{{ entry.name }}</span>
			<span class="text-graphite">{{ entry.edge }}</span>
		</label>
	</fieldset>
</template>
