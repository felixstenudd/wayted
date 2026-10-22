<script setup lang="ts">
import { Trash2 } from '@lucide/vue'
import { RadioGroupItem, RadioGroupRoot } from 'reka-ui'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'
import { FormField } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'

import { formatKm, parseDistanceKm } from '../distance'
import { usePlannerStore } from '../store'
import type { ThroughPoint, ThroughPointPlacement } from '../types'

const props = defineProps<{
	point: ThroughPoint
	/** The id of the heading that names the point, which its container shows. */
	titleId: string
	/** For the distance field's id, unique on the page. */
	idPrefix: string
}>()
const emit = defineEmits<{ removed: [] }>()

type At = ThroughPointPlacement['at']

const { t } = useI18n()
const planner = usePlannerStore()

const choices = computed(() =>
	(['any', 'asap', 'after'] as const).map((at) => ({
		at,
		label: t(`planner.points.through.placement.${at}`),
		hint: t(`planner.points.through.placement.${at}Hint`),
	})),
)

// Halfway is a likely place to want a point; without a target, the first kilometre.
const firstAfterKm = computed(() =>
	planner.usesTargetDistance ? Math.max(Math.round(planner.targetDistanceKm) / 2, 0.5) : 1,
)

const at = computed({
	get: () => props.point.placement.at,
	set: (next: At) => {
		planner.setThroughPointPlacement(
			props.point.id,
			next === 'after' ? { at: 'after', afterKm: firstAfterKm.value } : { at: next },
		)
	},
})

const afterKm = computed(() =>
	props.point.placement.at === 'after' ? props.point.placement.afterKm : null,
)
const text = ref(afterKm.value === null ? '' : formatKm(afterKm.value))
const isInvalid = ref(false)
watch(afterKm, (km) => {
	text.value = km === null ? '' : formatKm(km)
})

function commit(): void {
	const km = parseDistanceKm(text.value)
	isInvalid.value = km === null
	if (km !== null) planner.setThroughPointPlacement(props.point.id, { at: 'after', afterKm: km })
}

function remove(): void {
	planner.removeThroughPoint(props.point.id)
	emit('removed')
}
</script>

<template>
	<div class="flex flex-col gap-3">
		<RadioGroupRoot v-model="at" :aria-labelledby="titleId" class="flex flex-col gap-1.5">
			<RadioGroupItem
				v-for="choice in choices"
				:key="choice.at"
				:value="choice.at"
				class="flex flex-col items-start rounded-md border border-line px-3 py-2 text-left transition-[border-color,background-color] duration-150 ease-out hover:border-line-strong data-[state=checked]:border-ink data-[state=checked]:inset-ring data-[state=checked]:inset-ring-ink"
			>
				<span class="text-body font-semibold">{{ choice.label }}</span>
				<span class="text-small text-graphite">{{ choice.hint }}</span>
			</RadioGroupItem>
		</RadioGroupRoot>
		<FormField
			v-if="point.placement.at === 'after'"
			:id="`${idPrefix}-after`"
			v-slot="{ describedBy, invalid }"
			:label="t('planner.points.through.afterLabel')"
			:error="isInvalid ? t('planner.distance.invalid') : undefined"
		>
			<div class="relative">
				<Input
					:id="`${idPrefix}-after`"
					v-model="text"
					inputmode="decimal"
					autocomplete="off"
					class="pr-10"
					:aria-describedby="describedBy"
					:aria-invalid="invalid || undefined"
					@blur="commit"
					@keydown.enter="commit"
				/>
				<span
					class="pointer-events-none absolute inset-y-0 right-3 flex items-center text-body text-graphite"
					aria-hidden="true"
				>
					{{ t('planner.distance.unit') }}
				</span>
			</div>
		</FormField>
		<Button variant="ghost" size="sm" class="-ml-3 self-start" @click="remove">
			<Trash2 />
			{{ t('planner.points.through.remove') }}
		</Button>
	</div>
</template>
