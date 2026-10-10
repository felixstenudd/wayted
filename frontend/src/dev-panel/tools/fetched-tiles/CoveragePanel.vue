<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { EMPTY, tokenColor, useMapFilter, useMapSource } from '@/features/map'
import { Button } from '@/shared/ui/button'

import ProblemMessage from '../../components/ProblemMessage.vue'
import ToolSection from '../../components/ToolSection.vue'
import { useFetchedTiles } from './api'
import { layerCodes, tileFilter, toMapTiles } from './tiles'

const { t } = useI18n()
const { data: tiles, error, isPending, isFetching, refetch } = useFetchedTiles()

const codes = computed(() => (tiles.value ? layerCodes(tiles.value) : []))
const checked = ref<string[]>([])
const known = new Set<string>()
// A layer is checked when it is first seen; unchecking it is kept across reloads.
watch(
	codes,
	(next) => {
		for (const code of next) {
			if (!known.has(code)) checked.value.push(code)
			known.add(code)
		}
	},
	{ immediate: true },
)

const fetched = tokenColor('--map-fetched')
// Layers share their squares, so a darker square has more layers fetched.
useMapSource('coverage', () => (tiles.value ? toMapTiles(tiles.value) : EMPTY), [
	{ id: 'coverage-fill', type: 'fill', paint: { 'fill-color': fetched, 'fill-opacity': 0.15 } },
	{ id: 'coverage-valid', type: 'line', paint: { 'line-color': fetched, 'line-width': 1 } },
])
const shown = computed(() => tileFilter(checked.value))
useMapFilter('coverage-fill', shown)
useMapFilter('coverage-valid', shown)
</script>

<template>
	<ToolSection :title="t('coverage.title')">
		<p v-if="isPending" class="text-small text-graphite">{{ t('coverage.loading') }}</p>
		<ProblemMessage v-if="error" :error="error" />
		<p v-if="tiles && codes.length === 0" class="text-small text-graphite">
			{{ t('coverage.empty') }}
		</p>

		<fieldset v-if="codes.length > 0" class="flex flex-col gap-1">
			<legend class="mb-1 text-small text-graphite">{{ t('coverage.layers') }}</legend>
			<label v-for="code in codes" :key="code" class="flex items-center gap-2">
				<input v-model="checked" type="checkbox" :value="code" class="size-4 accent-ink" />
				{{ code }}
			</label>
		</fieldset>

		<Button
			size="sm"
			variant="secondary"
			class="self-start"
			:disabled="isFetching"
			@click="refetch()"
		>
			{{ t('coverage.reload') }}
		</Button>
	</ToolSection>
</template>
