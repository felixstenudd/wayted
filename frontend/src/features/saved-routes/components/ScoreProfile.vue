<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import {
	AttributeSymbol,
	humanizeKey,
	useRouteAttributes,
	weightMessage,
} from '@/features/route-planner'

import { needsCoverageNote, profileRows, scoreWord } from '../profile'
import type { SavedRoute } from '../types'

const props = defineProps<{ route: SavedRoute }>()

const HEADING_ID = 'route-profile-heading'

const i18n = useI18n()
const { t } = i18n
const attributes = useRouteAttributes()

const percent = (share: number) => Math.round(share * 100)
const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)

const rows = computed(() =>
	profileRows(
		props.route.scores,
		props.route.preferences,
		(attributes.data.value ?? []).map((a) => a.key),
	).map((row) => ({
		...row,
		name: name(row.key),
		word: t(`savedRoutes.profile.words.${scoreWord(row.mean)}`),
		wanted:
			row.weight === 0
				? null
				: t('savedRoutes.profile.wanted', {
						weight: t(weightMessage(row.key, row.weight, (path) => i18n.te(path))),
					}),
		known: needsCoverageNote(row.coverage)
			? t('savedRoutes.profile.known', { percent: percent(row.coverage) })
			: null,
		spoken: t('savedRoutes.profile.spoken', {
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
		<h2 :id="HEADING_ID" class="text-title">{{ t('savedRoutes.profile.title') }}</h2>
		<p v-if="rows.length === 0" class="text-small text-graphite">
			{{ t('savedRoutes.profile.empty') }}
		</p>
		<ul v-else class="flex flex-col gap-2.5">
			<li v-for="row in rows" :key="row.key" class="flex items-center gap-2">
				<AttributeSymbol :attribute-key="row.key" />
				<div class="flex w-32 shrink-0 flex-col">
					<span class="text-body" :class="{ 'font-semibold': row.wanted }">{{
						row.name
					}}</span>
					<span v-if="row.wanted" class="text-caption text-graphite">{{
						row.wanted
					}}</span>
					<span v-if="row.known" class="text-caption text-graphite">{{ row.known }}</span>
				</div>
				<div
					class="relative h-2 flex-1 overflow-hidden rounded-full bg-line"
					aria-hidden="true"
				>
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
				<span class="w-16 shrink-0 text-right text-small font-semibold">
					{{ row.word }}
					<span class="sr-only">{{ row.spoken }}</span>
				</span>
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
