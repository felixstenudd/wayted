<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useRouteAttributes } from '../api'
import { humanizeKey, weightMessage } from '../attributes'
import { needsCoverageNote, profileRows, scoreMessage } from '../profile'
import type { AttributeScore } from '../types'
import AttributeSymbol from './AttributeSymbol.vue'

const props = defineProps<{
	scores: Record<string, AttributeScore>
	/** The weights the route was planned with, which are shown first. */
	preferences: Record<string, number>
}>()

const HEADING_ID = 'route-profile-heading'

const i18n = useI18n()
const { t } = i18n
const attributes = useRouteAttributes()

const percent = (share: number) => Math.round(share * 100)
// A row may be named for what its words describe: "Surface", read with "Mostly smooth".
const name = (key: string) =>
	i18n.te(`route.profile.rowNames.${key}`)
		? t(`route.profile.rowNames.${key}`)
		: i18n.te(`planner.preferences.attributes.${key}`)
			? t(`planner.preferences.attributes.${key}`)
			: humanizeKey(key)

const rows = computed(() =>
	profileRows(
		props.scores,
		props.preferences,
		(attributes.data.value ?? []).map((a) => a.key),
	).map((row) => ({
		...row,
		name: name(row.key),
		word: t(scoreMessage(row.key, row.mean, (path) => i18n.te(path))),
		wanted:
			row.weight === 0
				? null
				: t('route.profile.wanted', {
						weight: t(weightMessage(row.key, row.weight, (path) => i18n.te(path))),
					}),
		known: needsCoverageNote(row.coverage)
			? t('route.profile.known', { percent: percent(row.coverage) })
			: null,
		spoken: t('route.profile.spoken', {
			percent: percent(row.mean),
			known: percent(row.coverage),
		}),
		// The meter is the whole route: the known part is filled by its score, the rest hatched.
		fillPercent: percent(row.mean * row.coverage),
		unknownPercent: 100 - percent(row.coverage),
	})),
)
</script>

<template>
	<section :aria-labelledby="HEADING_ID" class="flex flex-col gap-3">
		<h2 :id="HEADING_ID" class="text-title">{{ t('route.profile.title') }}</h2>
		<p v-if="rows.length === 0" class="text-small text-graphite">
			{{ t('route.profile.empty') }}
		</p>
		<ul v-else class="flex flex-col gap-3.5">
			<!-- The word says what the route is like; the bar below shows it, unknown part hatched. -->
			<li v-for="row in rows" :key="row.key" class="flex flex-col gap-1.5">
				<div class="flex items-center gap-2">
					<AttributeSymbol :attribute-key="row.key" />
					<span class="min-w-0 flex-1 text-body" :class="{ 'font-semibold': row.wanted }">
						{{ row.name }}
					</span>
					<span class="text-small font-semibold">
						{{ row.word }}
						<span class="sr-only">{{ row.spoken }}</span>
					</span>
				</div>
				<div class="relative ml-6" aria-hidden="true">
					<div class="relative h-2 overflow-hidden rounded-full bg-line">
						<span
							class="absolute inset-y-0 left-0 rounded-full bg-ink"
							:style="{ width: `${row.fillPercent}%` }"
						/>
						<span
							v-if="row.unknownPercent > 0"
							class="unknown absolute inset-y-0 right-0"
							:style="{ width: `${row.unknownPercent}%` }"
						/>
					</div>
					<!-- Where the scored part ends: the word describes what is left of this tick. -->
					<span
						v-if="row.unknownPercent > 0"
						class="absolute -inset-y-1 w-0.5 -translate-x-1/2 bg-graphite"
						:style="{ left: `${100 - row.unknownPercent}%` }"
					/>
				</div>
				<p
					v-if="row.wanted || row.known"
					class="ml-6 flex flex-col text-caption text-graphite"
				>
					<span v-if="row.wanted">{{ row.wanted }}</span>
					<span v-if="row.known">{{ row.known }}</span>
				</p>
			</li>
		</ul>
	</section>
</template>

<style scoped>
/* Unknown is hatched, not coloured, so it reads in greyscale too. */
.unknown {
	background-image: repeating-linear-gradient(
		135deg,
		var(--line-strong) 0 1px,
		var(--paper) 1px 4px
	);
}
</style>
