<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { CourseSymbolKind } from '@/shared/ui/course-symbol'
import { CourseSymbol } from '@/shared/ui/course-symbol'

interface Step {
	id: string
	symbol: CourseSymbolKind
	controlNumber?: number
}

const { t } = useI18n()

// The steps are drawn as a course because they are a real sequence.
const steps: Step[] = [
	{ id: 'start', symbol: 'start' },
	{ id: 'distance', symbol: 'control', controlNumber: 1 },
	{ id: 'preferences', symbol: 'control', controlNumber: 2 },
	{ id: 'pick', symbol: 'finish' },
]

const lastStepIndex = steps.length - 1
</script>

<template>
	<section aria-labelledby="how-it-works-title" class="border-t border-line">
		<div
			class="mx-auto flex w-full max-w-6xl flex-col gap-10 px-4 py-16 sm:px-6 lg:px-8 lg:py-24"
		>
			<h2 id="how-it-works-title" class="text-heading">
				{{ t('landing.howItWorks.title') }}
			</h2>
			<ol class="grid md:grid-cols-4 md:gap-6">
				<li
					v-for="(step, index) in steps"
					:key="step.id"
					class="relative flex gap-4 pb-8 last:pb-0 md:flex-col md:pb-0"
				>
					<span
						v-if="index < lastStepIndex"
						aria-hidden="true"
						class="absolute top-8 bottom-1 left-3.25 w-0.5 bg-overprint md:top-3.25 md:-right-5 md:bottom-auto md:left-8 md:h-0.5 md:w-auto"
					/>
					<CourseSymbol
						:kind="step.symbol"
						:control-number="step.controlNumber"
						class="relative size-7 shrink-0"
					/>
					<div class="flex flex-col gap-1">
						<h3 class="text-title">{{ t(`landing.howItWorks.${step.id}.title`) }}</h3>
						<p class="max-w-xs text-graphite">
							{{ t(`landing.howItWorks.${step.id}.body`) }}
						</p>
					</div>
				</li>
			</ol>
		</div>
	</section>
</template>
