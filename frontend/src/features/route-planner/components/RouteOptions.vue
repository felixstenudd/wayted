<script setup lang="ts">
import { RadioGroupItem, RadioGroupRoot } from 'reka-ui'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { scoreMessage } from '@/features/route'

import { useShownRoute } from '../composables/useShownRoute'
import { formatKm } from '../distance'
import { optionLetter, routeFit, standOut } from '../options'
import { usePlannerStore } from '../store'

const i18n = useI18n()
const { t } = i18n
const hasMessage = (path: string) => i18n.te(path)
const planner = usePlannerStore()
const { routes } = useShownRoute()
// An edited option is described as it is now.
const described = computed(() =>
	routes.value.map((route, index) =>
		planner.edit?.option === index && planner.editedRoute ? planner.editedRoute : route,
	),
)

const selected = computed({
	get: () => String(planner.selectedOption),
	set: (index: string) => planner.selectOption(Number(index)),
})

// Each option is told apart by what it is like where it differs, when it does; else by its fit.
const apart = computed(() => {
	const scores = described.value.map((route) => route.properties.scores)
	const keys = [...new Set(scores.flatMap((each) => Object.keys(each)))].filter((key) =>
		hasMessage(`route.profile.attributeWords.${key}.none`),
	)
	return standOut(scores, planner.search?.request.preferences ?? {}, keys)
})

const options = computed(() =>
	described.value.map((route, index) => {
		const fit = routeFit(route.properties.length_m, planner.search?.request.target_distance_m)
		const apartKey = apart.value[index]
		return {
			value: String(index),
			letter: optionLetter(index),
			isEdited: planner.edit?.option === index,
			km: t('planner.route.length', { km: formatKm(route.properties.length_m / 1000) }),
			fit:
				fit === null
					? null
					: fit.kind === 'close'
						? t('planner.options.close', {
								km: formatKm(
									(planner.search?.request.target_distance_m ?? 0) / 1000,
								),
							})
						: t(`planner.options.${fit.kind}`, { km: formatKm(fit.km) }),
			apart: apartKey
				? t(
						scoreMessage(
							apartKey,
							route.properties.scores[apartKey]?.mean ?? 0,
							hasMessage,
						),
					)
				: null,
		}
	}),
)
</script>

<template>
	<!-- One route is not a choice, so there is nothing to show. -->
	<RadioGroupRoot
		v-if="options.length > 1 && !planner.isChosen"
		v-model="selected"
		:aria-label="t('planner.options.group')"
		orientation="horizontal"
		class="grid auto-cols-fr grid-flow-col gap-2"
	>
		<RadioGroupItem
			v-for="option in options"
			:key="option.value"
			:value="option.value"
			:aria-label="
				t('planner.options.spoken', {
					letter: option.letter,
					km: option.km,
					fit: [option.fit, option.apart].filter(Boolean).join('. '),
				})
			"
			class="group flex min-w-0 flex-col items-start gap-0.5 rounded-md border border-line px-2.5 py-2 text-left transition-[border-color] duration-150 ease-out hover:border-line-strong data-[state=checked]:border-ink data-[state=checked]:inset-ring data-[state=checked]:inset-ring-ink"
		>
			<span
				class="grid size-5.5 place-items-center rounded-full border border-line-strong text-caption font-bold text-graphite group-data-[state=checked]:border-overprint-contrast group-data-[state=checked]:bg-overprint group-data-[state=checked]:text-overprint-contrast"
				aria-hidden="true"
			>
				{{ option.letter }}
			</span>
			<span class="text-body font-semibold text-ink">{{ option.km }}</span>
			<span v-if="option.isEdited" class="text-caption font-semibold text-ink">
				{{ t('planner.options.edited') }}
			</span>
			<span v-else-if="option.apart ?? option.fit" class="text-caption text-graphite">
				{{ option.apart ?? option.fit }}
			</span>
		</RadioGroupItem>
	</RadioGroupRoot>
</template>
