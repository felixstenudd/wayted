<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { CourseSymbol } from '@/shared/ui/course-symbol'

const { t } = useI18n()

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
</script>

<template>
	<figure class="flex flex-col gap-3">
		<div class="overflow-hidden rounded-lg border border-line">
			<svg
				viewBox="0 0 560 380"
				role="img"
				:aria-label="t('landing.illustration.label')"
				class="block h-auto w-full"
			>
				<rect width="560" height="380" class="fill-sunken" />
				<path d="M300 40 470 30 530 125 440 178 330 158Z" class="map-park" />
				<path
					d="M40 270C110 238 200 252 240 292 262 322 205 368 120 364 55 360 20 310 40 270Z"
					class="map-water"
				/>
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
					<path :d="selectedRoutePath" stroke-width="10" class="stroke-paper" />
					<path :d="selectedRoutePath" stroke-width="5" class="stroke-overprint" />
				</g>
				<CourseSymbol kind="start" x="96" y="196" width="28" height="28" />
				<CourseSymbol
					kind="control"
					:control-number="1"
					x="316"
					y="144"
					width="28"
					height="28"
				/>
				<CourseSymbol
					kind="control"
					:control-number="2"
					x="491"
					y="144"
					width="28"
					height="28"
				/>
				<CourseSymbol kind="finish" x="416" y="286" width="28" height="28" />
				<g class="text-caption font-semibold" text-anchor="middle">
					<rect
						x="158"
						y="79"
						width="64"
						height="22"
						rx="11"
						class="fill-paper stroke-line"
					/>
					<text x="190" y="90" dy="0.35em" class="fill-graphite">
						{{
							t('landing.illustration.candidate', { letter: 'B', distanceKm: '9.8' })
						}}
					</text>
					<rect x="164" y="199" width="72" height="22" rx="11" class="fill-overprint" />
					<text x="200" y="210" dy="0.35em" class="fill-paper">
						{{
							t('landing.illustration.candidate', { letter: 'A', distanceKm: '10.2' })
						}}
					</text>
				</g>
			</svg>
		</div>
		<figcaption class="text-small text-graphite">
			{{ t('landing.illustration.caption') }}
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
