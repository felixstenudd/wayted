<script setup lang="ts">
import { Minus, Plus } from '@lucide/vue'
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'
import { FormField } from '@/shared/ui/form-field'
import { Input } from '@/shared/ui/input'
import { SegmentedControl } from '@/shared/ui/segmented-control'

import { formatKm, parseDistanceKm, STEP_KM, steppedKm } from '../distance'
import { usePlannerStore } from '../store'

const ID = 'target-distance'

const { t } = useI18n()
const planner = usePlannerStore()

// What is typed; the store only takes it on Enter or leaving the field.
const text = ref(formatKm(planner.targetDistanceKm))
const isInvalid = ref(false)
watch(
	() => planner.targetDistanceKm,
	(km) => {
		text.value = formatKm(km)
	},
)

// From point to point: the most pleasant way however long, or one of about the distance.
const lengthKind = computed({
	get: () => (planner.hasTargetDistance ? 'target' : 'any'),
	set: (kind: 'any' | 'target') => {
		planner.hasTargetDistance = kind === 'target'
	},
})
const lengthKinds = computed(() => [
	{ value: 'any' as const, label: t('planner.distance.any') },
	{ value: 'target' as const, label: t('planner.distance.target') },
])

const stepKm = computed(() => STEP_KM[planner.activity])
const range = computed(() => planner.distanceRange)

const hint = computed(() =>
	t(`planner.distance.hint.${planner.activity}`, {
		min: formatKm(range.value.minKm),
		max: formatKm(range.value.maxKm),
	}),
)

function commit(): void {
	const km = parseDistanceKm(text.value)
	isInvalid.value = km === null
	if (km === null) return
	planner.setTargetDistanceKm(km)
	// The store may have kept it in range; show what it kept even when that did not change.
	text.value = formatKm(planner.targetDistanceKm)
}

function step(direction: 1 | -1): void {
	isInvalid.value = false
	planner.setTargetDistanceKm(steppedKm(planner.targetDistanceKm, stepKm.value, direction))
}
</script>

<template>
	<div v-if="planner.shape === 'point_to_point'" class="flex flex-col gap-1.5">
		<SegmentedControl
			v-model="lengthKind"
			:label="t('planner.distance.kind')"
			:options="lengthKinds"
		/>
		<p v-if="!planner.usesTargetDistance" class="text-small text-graphite">
			{{ t('planner.distance.anyHint') }}
		</p>
	</div>
	<FormField
		v-if="planner.usesTargetDistance"
		:id="ID"
		v-slot="{ describedBy, invalid }"
		:label="t('planner.distance.label')"
		:hint="hint"
		:error="isInvalid ? t('planner.distance.invalid') : undefined"
	>
		<div class="flex gap-2">
			<Button
				variant="secondary"
				size="icon"
				:aria-label="t('planner.distance.shorter', { step: formatKm(stepKm) })"
				:disabled="planner.targetDistanceKm <= range.minKm"
				@click="step(-1)"
			>
				<Minus />
			</Button>
			<div class="relative flex-1">
				<Input
					:id="ID"
					v-model="text"
					inputmode="decimal"
					autocomplete="off"
					class="pr-10 text-center tabular-nums"
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
			<Button
				variant="secondary"
				size="icon"
				:aria-label="t('planner.distance.longer', { step: formatKm(stepKm) })"
				:disabled="planner.targetDistanceKm >= range.maxKm"
				@click="step(1)"
			>
				<Plus />
			</Button>
		</div>
	</FormField>
</template>
