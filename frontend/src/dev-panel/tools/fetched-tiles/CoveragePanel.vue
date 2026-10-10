<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { EMPTY, tokenColor, useMapClick, useMapFilter, useMapSource } from '@/features/map'
import { Button } from '@/shared/ui/button'

import ProblemMessage from '../../components/ProblemMessage.vue'
import ToolSection from '../../components/ToolSection.vue'
import { formatTime } from '../../format'
import { useFetchedTiles } from './api'
import {
	advance,
	countExpired,
	layerCodes,
	tileFilter,
	tilesAt,
	timeRange,
	toMapTiles,
} from './tiles'

const PLAY_STEPS = 100
const PLAY_STEP_MS = 80

const { t } = useI18n()
const { data: tiles, error, isPending, isFetching, dataUpdatedAt, refetch } = useFetchedTiles()

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

const nowMs = computed(() => dataUpdatedAt.value)
const range = computed(() => (tiles.value ? timeRange(tiles.value, nowMs.value) : null))
// null follows the end of the range
const selectedMs = ref<number | null>(null)
const untilMs = computed(() => selectedMs.value ?? range.value?.endMs ?? 0)

function selectTime(event: Event) {
	const value = Number((event.target as HTMLInputElement).value)
	selectedMs.value = range.value && value < range.value.endMs ? value : null
}

const playTimer = ref<ReturnType<typeof setInterval> | null>(null)
function stopPlaying() {
	if (playTimer.value) clearInterval(playTimer.value)
	playTimer.value = null
}
function togglePlaying() {
	if (playTimer.value) return stopPlaying()
	if (!range.value) return
	selectedMs.value ??= range.value.startMs
	playTimer.value = setInterval(() => {
		selectedMs.value = range.value ? advance(untilMs.value, range.value, PLAY_STEPS) : null
		if (selectedMs.value === null) stopPlaying()
	}, PLAY_STEP_MS)
}
onBeforeUnmount(stopPlaying)

const expiredCount = computed(() => (tiles.value ? countExpired(tiles.value, nowMs.value) : 0))

const selectedKey = ref<string | null>(null)
const selected = computed(() =>
	tiles.value && selectedKey.value ? tilesAt(tiles.value, selectedKey.value) : [],
)

const fetched = tokenColor('--map-fetched')
// Layers share their squares, so a darker square has more layers fetched.
useMapSource('coverage', () => (tiles.value ? toMapTiles(tiles.value) : EMPTY), [
	{ id: 'coverage-fill', type: 'fill', paint: { 'fill-color': fetched, 'fill-opacity': 0.15 } },
	{ id: 'coverage-valid', type: 'line', paint: { 'line-color': fetched, 'line-width': 1 } },
	{
		id: 'coverage-expired',
		type: 'line',
		paint: {
			'line-color': tokenColor('--map-expired'),
			'line-width': 2,
			'line-dasharray': [2, 2],
		},
	},
])
const shown = (expiry: Parameters<typeof tileFilter>[3]) => () =>
	tileFilter(checked.value, selectedMs.value, nowMs.value, expiry)
useMapFilter('coverage-fill', shown('any'))
useMapFilter('coverage-valid', shown('valid'))
useMapFilter('coverage-expired', shown('expired'))
useMapClick(['coverage-fill'], (feature) => {
	const key = feature?.properties.key
	selectedKey.value = typeof key === 'string' ? key : null
})
</script>

<template>
	<ToolSection :title="t('coverage.title')">
		<p v-if="isPending" class="text-small text-graphite">{{ t('coverage.loading') }}</p>
		<ProblemMessage v-if="error" :error="error" />
		<p v-if="tiles && !range" class="text-small text-graphite">{{ t('coverage.empty') }}</p>

		<template v-if="tiles && range">
			<fieldset class="flex flex-col gap-1">
				<legend class="mb-1 text-small text-graphite">{{ t('coverage.layers') }}</legend>
				<label v-for="code in codes" :key="code" class="flex items-center gap-2">
					<input
						v-model="checked"
						type="checkbox"
						:value="code"
						class="size-4 accent-ink"
					/>
					{{ code }}
				</label>
			</fieldset>

			<div class="flex flex-col gap-1">
				<label for="coverage-time" class="text-small text-graphite">
					{{ t('coverage.until') }}
				</label>
				<input
					id="coverage-time"
					type="range"
					class="accent-ink"
					:min="range.startMs"
					:max="range.endMs"
					:value="untilMs"
					@input="selectTime"
				/>
				<p>{{ selectedMs === null ? t('coverage.now') : formatTime(untilMs) }}</p>
			</div>

			<p v-if="expiredCount > 0" class="text-small text-graphite">
				{{ t('coverage.expired', { count: expiredCount }) }}
			</p>

			<dl v-if="selectedKey && selected.length > 0" class="flex flex-col gap-2 text-small">
				<dt class="font-semibold">{{ t('coverage.tile', { key: selectedKey }) }}</dt>
				<dd v-for="tile in selected" :key="tile.layer">
					{{
						t('coverage.tileLayer', {
							layer: tile.layer,
							fetched: formatTime(tile.fetched_at),
							expires: formatTime(tile.expires_at),
						})
					}}
				</dd>
			</dl>
		</template>

		<div class="flex gap-2">
			<Button v-if="range" size="sm" variant="secondary" @click="togglePlaying">
				{{ playTimer ? t('coverage.pause') : t('coverage.play') }}
			</Button>
			<Button size="sm" variant="secondary" :disabled="isFetching" @click="refetch()">
				{{ t('coverage.reload') }}
			</Button>
		</div>
	</ToolSection>
</template>
