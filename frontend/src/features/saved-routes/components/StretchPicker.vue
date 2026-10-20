<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useMediaQuery } from '@/shared/composables/useMediaQuery'
import { Button } from '@/shared/ui/button'

import { useStretchPick } from '../composables/useStretchPick'
import { formatDistanceKm } from '../format'
import { useSavedRoutesStore } from '../store'
import type { SavedRoute } from '../types'

const props = defineProps<{ route: SavedRoute; headingId: string }>()

const FROM_ID = 'stretch-from'
const TO_ID = 'stretch-to'

const { t, locale } = useI18n()
const store = useSavedRoutesStore()
const pick = useStretchPick(() => props.route.id)
// Fingers tap, pointers click: the instruction says which.
const isTouch = useMediaQuery('(pointer: coarse)')

const km = (junction: number) =>
	formatDistanceKm(pick.junctions.value[junction]?.distanceM ?? 0, locale.value)
const last = computed(() => pick.junctions.value.length - 1)
const instruction = computed(() => {
	const how = isTouch.value ? 'tap' : 'click'
	if (pick.step.value === 'start') return t(`savedRoutes.stretch.${how}.start`)
	if (pick.step.value === 'end') return t(`savedRoutes.stretch.${how}.end`)
	return t('savedRoutes.stretch.adjust')
})
/** A slider moved: the end follows, and the slider shows where the end could go. */
function slide(which: 'from' | 'to', event: Event): void {
	const input = event.target as HTMLInputElement
	if (which === 'from') pick.setFrom(Number(input.value))
	else pick.setTo(Number(input.value))
	// An end cannot pass the other, so the slider may need to come back.
	input.value = String(pick.stretch.value?.[which] ?? input.value)
}

const length = computed(() =>
	t('savedRoutes.stretch.length', { km: formatDistanceKm(pick.lengthM.value, locale.value) }),
)
</script>

<template>
	<div class="flex flex-col gap-5">
		<div class="flex flex-col gap-1">
			<h1 :id="headingId" class="text-heading">{{ t('savedRoutes.stretch.title') }}</h1>
			<p class="text-small text-graphite" aria-live="polite">{{ instruction }}</p>
		</div>

		<div v-if="pick.stretch.value" class="flex flex-col gap-3">
			<p class="font-semibold" aria-live="polite">{{ length }}</p>
			<div class="grid grid-cols-[5rem_1fr_3.5rem] items-center gap-x-3 gap-y-2 text-small">
				<label :for="FROM_ID">{{ t('savedRoutes.stretch.from') }}</label>
				<input
					:id="FROM_ID"
					type="range"
					min="0"
					:max="last"
					step="1"
					:value="pick.stretch.value.from"
					:aria-valuetext="
						t('savedRoutes.stretch.atKm', { km: km(pick.stretch.value.from) })
					"
					class="accent-ink"
					@input="slide('from', $event)"
				/>
				<span class="text-right">{{
					t('savedRoutes.row.distanceKm', { km: km(pick.stretch.value.from) })
				}}</span>
				<label :for="TO_ID">{{ t('savedRoutes.stretch.to') }}</label>
				<input
					:id="TO_ID"
					type="range"
					min="0"
					:max="last"
					step="1"
					:value="pick.stretch.value.to"
					:aria-valuetext="
						t('savedRoutes.stretch.atKm', { km: km(pick.stretch.value.to) })
					"
					class="accent-ink"
					@input="slide('to', $event)"
				/>
				<span class="text-right">{{
					t('savedRoutes.row.distanceKm', { km: km(pick.stretch.value.to) })
				}}</span>
			</div>
		</div>

		<div class="flex gap-2">
			<Button
				class="flex-1"
				:disabled="!pick.stretch.value"
				@click="store.toStretchReasons()"
			>
				{{ t('savedRoutes.stretch.next') }}
			</Button>
			<Button variant="ghost" @click="store.stopPickingStretch()">
				{{ t('savedRoutes.stretch.cancel') }}
			</Button>
		</div>
	</div>
</template>
