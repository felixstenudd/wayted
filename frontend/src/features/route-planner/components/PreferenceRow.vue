<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { BipolarSlider } from '@/shared/ui/bipolar-slider'

import { WEIGHT_DETENTS, weightWord } from '../attributes'
import { usePlannerStore } from '../store'
import type { RouteAttribute } from '../types'
import AttributeSymbol from './AttributeSymbol.vue'

const props = defineProps<{ attribute: RouteAttribute; name: string }>()

const { t } = useI18n()
const planner = usePlannerStore()

const weight = computed({
	get: () => planner.weightOf(props.attribute.key),
	set: (next: number) => planner.setWeight(props.attribute.key, next),
})
const word = computed(() =>
	props.attribute.scored
		? t(`planner.preferences.weights.${weightWord(weight.value)}`)
		: t('planner.preferences.notScored'),
)
const isSet = computed(() => weight.value !== 0)
</script>

<template>
	<div class="flex items-center gap-2">
		<AttributeSymbol :attribute-key="attribute.key" />
		<div class="w-28 shrink-0">
			<p
				class="truncate text-body"
				:class="[isSet && 'font-semibold', !attribute.scored && 'text-graphite']"
			>
				{{ name }}
			</p>
			<p class="truncate text-small text-graphite" aria-hidden="true">{{ word }}</p>
		</div>
		<BipolarSlider
			v-model="weight"
			class="min-w-0 flex-1"
			:label="name"
			:value-text="word"
			:disabled="!attribute.scored"
			:detents="WEIGHT_DETENTS"
		/>
	</div>
</template>
