<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { BipolarSlider } from '@/shared/ui/bipolar-slider'

import { WEIGHT_DETENTS, weightMessage } from '../attributes'
import { usePlannerStore } from '../store'
import type { RouteAttribute } from '../types'
import AttributeSymbol from './AttributeSymbol.vue'

const props = defineProps<{ attribute: RouteAttribute; name: string }>()

const i18n = useI18n()
const { t } = i18n
const planner = usePlannerStore()

const weight = computed({
	get: () => planner.weightOf(props.attribute.key),
	set: (next: number) => planner.setWeight(props.attribute.key, next),
})
const word = computed(() =>
	t(weightMessage(props.attribute.key, weight.value, (path) => i18n.te(path))),
)
</script>

<template>
	<div class="flex min-h-9 items-center gap-2">
		<AttributeSymbol :attribute-key="attribute.key" />
		<p class="w-28 shrink-0 truncate text-body" :class="{ 'font-semibold': weight !== 0 }">
			{{ name }}
		</p>
		<BipolarSlider
			v-model="weight"
			class="min-w-0 flex-1"
			:label="name"
			:value-text="word"
			:detents="WEIGHT_DETENTS"
		/>
	</div>
</template>
