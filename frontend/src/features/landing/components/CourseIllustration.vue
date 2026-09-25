<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { CourseSymbolKind } from '@/shared/ui/course-symbol'
import { CourseSymbol } from '@/shared/ui/course-symbol'

interface Marker {
	id: string
	kind: CourseSymbolKind
	controlNumber?: number
	x: number
	y: number
}

interface RouteLabel {
	letter: string
	distanceKm: string
	selected: boolean
	x: number
	y: number
}

const { t } = useI18n()

const VIEW_WIDTH = 560
const VIEW_HEIGHT = 380
// Measured from selectedRoutePath: 680 units for the labelled 10.2 km.
const UNITS_PER_KM = 66.6

const roadPaths = [
	'M0 90H560',
	'M0 210H560',
	'M110 0V380',
	'M280 0V380',
	'M430 210V380',
	'M0 350 560 262',
]
const alternativeRoutePath = 'M110 210V90H280V210H430V300'
const selectedRoutePath = 'M110 210H280V150L330 158C360 112 420 88 480 118L505 158 430 210V300'

// Markers and labels are HTML on top of the drawing so they keep a readable
// size when the drawing scales down, like markers on a real map.
const markers: Marker[] = [
	{ id: 'start', kind: 'start', x: 110, y: 210 },
	{ id: 'control-1', kind: 'control', controlNumber: 1, x: 330, y: 158 },
	{ id: 'control-2', kind: 'control', controlNumber: 2, x: 505, y: 158 },
	{ id: 'finish', kind: 'finish', x: 430, y: 300 },
]
const routeLabels: RouteLabel[] = [
	{ letter: 'B', distanceKm: '9.8', selected: false, x: 190, y: 90 },
	{ letter: 'A', distanceKm: '10.2', selected: true, x: 200, y: 210 },
]

function placeAt(x: number, y: number): Record<string, string> {
	return { left: `${(x / VIEW_WIDTH) * 100}%`, top: `${(y / VIEW_HEIGHT) * 100}%` }
}

const scaleBarWidth = `${(UNITS_PER_KM / VIEW_WIDTH) * 100}%`
</script>

<template>
	<figure class="flex flex-col gap-3">
		<div class="relative overflow-hidden rounded-lg border border-line">
			<svg
				:viewBox="`0 0 ${VIEW_WIDTH} ${VIEW_HEIGHT}`"
				role="img"
				:aria-label="t('landing.illustration.label')"
				class="block h-auto w-full"
			>
				<rect :width="VIEW_WIDTH" :height="VIEW_HEIGHT" class="fill-sunken" />
				<path d="M300 40 470 30 530 125 440 178 330 158Z" class="map-park" />
				<ellipse cx="195" cy="262" rx="58" ry="28" class="map-water" />
				<g fill="none" stroke-linecap="round">
					<path
						v-for="road in roadPaths"
						:key="`edge-${road}`"
						:d="road"
						stroke-width="10"
						class="stroke-line"
					/>
					<path
						v-for="road in roadPaths"
						:key="road"
						:d="road"
						stroke-width="7"
						class="stroke-paper"
					/>
					<path
						d="M330 62C380 92 440 72 480 110"
						stroke-width="3"
						stroke-dasharray="1 6"
						class="stroke-line-strong"
					/>
				</g>
				<g fill="none" stroke-linecap="round" stroke-linejoin="round">
					<path
						:d="alternativeRoutePath"
						stroke-width="3.5"
						class="stroke-graphite opacity-75"
					/>
					<path
						:d="selectedRoutePath"
						stroke-width="9"
						class="stroke-overprint-contrast"
					/>
					<path :d="selectedRoutePath" stroke-width="5.5" class="stroke-overprint" />
				</g>
			</svg>
			<div aria-hidden="true" class="absolute inset-0">
				<CourseSymbol
					v-for="marker in markers"
					:key="marker.id"
					:kind="marker.kind"
					:control-number="marker.controlNumber"
					class="absolute size-6 -translate-x-1/2 -translate-y-1/2 sm:size-7"
					:style="placeAt(marker.x, marker.y)"
				/>
				<span
					v-for="label in routeLabels"
					:key="label.letter"
					class="absolute -translate-x-1/2 -translate-y-1/2 rounded-full border px-2 py-0.5 text-caption font-semibold whitespace-nowrap"
					:class="
						label.selected
							? 'border-overprint-contrast bg-overprint text-overprint-contrast'
							: 'border-line bg-paper text-graphite'
					"
					:style="placeAt(label.x, label.y)"
				>
					{{
						t('landing.illustration.candidate', {
							letter: label.letter,
							distanceKm: label.distanceKm,
						})
					}}
				</span>
			</div>
		</div>
		<figcaption class="flex items-end justify-between gap-6 text-small text-graphite">
			<span>{{ t('landing.illustration.caption') }}</span>
			<span
				role="img"
				:aria-label="t('landing.illustration.scaleLabel')"
				class="flex shrink-0 flex-col gap-1"
				:style="{ width: scaleBarWidth }"
			>
				<span class="text-caption">{{ t('landing.illustration.scale') }}</span>
				<span class="h-1.5 w-full border-x-2 border-b-2 border-graphite" />
			</span>
		</figcaption>
	</figure>
</template>

<style scoped>
/* Base map tints are derived from the palette so the drawing follows the theme. */
.map-park {
	fill: color-mix(in oklab, var(--vegetation) 18%, var(--paper));
}

.map-water {
	fill: color-mix(in oklab, var(--graphite) 16%, var(--paper));
}
</style>
