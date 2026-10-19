<script setup lang="ts">
import { CircleAlert } from '@lucide/vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { Button } from '@/shared/ui/button'

import { useRouteAttributes } from '../api'
import { groupAttributes, humanizeKey } from '../attributes'
import { usePlannerStore } from '../store'
import PreferenceRow from './PreferenceRow.vue'

const HEADING_ID = 'preferences-heading'
const PLACEHOLDER_ROWS = 4

const i18n = useI18n()
const { t } = i18n
const planner = usePlannerStore()
const attributes = useRouteAttributes()

const groups = computed(() => groupAttributes(attributes.data.value ?? []))

const name = (key: string) =>
	i18n.te(`planner.preferences.attributes.${key}`)
		? t(`planner.preferences.attributes.${key}`)
		: humanizeKey(key)
const groupName = (group: string) =>
	i18n.te(`planner.preferences.groups.${group}`)
		? t(`planner.preferences.groups.${group}`)
		: humanizeKey(group)
</script>

<template>
	<section
		v-if="attributes.isPending.value || attributes.isError.value || groups.length > 0"
		:aria-labelledby="HEADING_ID"
		:aria-busy="attributes.isPending.value"
		class="flex flex-col gap-3"
	>
		<div class="flex items-baseline justify-between gap-2">
			<h2 :id="HEADING_ID" class="text-title">{{ t('planner.preferences.title') }}</h2>
			<p
				v-if="planner.setWeightCount > 0"
				class="flex items-baseline gap-3 text-small text-graphite"
			>
				{{ t('planner.preferences.setCount', planner.setWeightCount) }}
				<Button variant="link" class="text-small" @click="planner.resetWeights()">
					{{ t('planner.preferences.reset') }}
				</Button>
			</p>
		</div>

		<div v-if="attributes.isPending.value" class="flex flex-col gap-4">
			<span class="sr-only">{{ t('planner.preferences.loading') }}</span>
			<div
				v-for="row in PLACEHOLDER_ROWS"
				:key="row"
				class="flex items-center gap-2"
				aria-hidden="true"
			>
				<span class="size-4 rounded-sm bg-sunken" />
				<span class="h-4 w-28 rounded-sm bg-sunken" />
				<span class="mx-2.5 h-1 flex-1 rounded-full bg-sunken" />
			</div>
		</div>

		<div
			v-else-if="attributes.isError.value"
			role="alert"
			class="flex flex-col items-start gap-2"
		>
			<p class="flex gap-1.5 text-small text-contour">
				<CircleAlert class="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
				{{ t('planner.preferences.loadFailed') }}
			</p>
			<Button variant="secondary" size="sm" @click="attributes.refetch()">
				{{ t('planner.preferences.tryAgain') }}
			</Button>
		</div>

		<template v-else>
			<!-- One scale for every track below; the tracks line up under it. -->
			<div class="flex gap-2 text-caption text-graphite" aria-hidden="true">
				<span class="w-4 shrink-0" />
				<span class="w-28 shrink-0" />
				<span class="flex flex-1 justify-between px-1">
					<span>{{ t('planner.preferences.weights.avoid') }}</span>
					<span>{{ t('planner.preferences.weights.dontMind') }}</span>
					<span>{{ t('planner.preferences.weights.prefer') }}</span>
				</span>
			</div>
			<div
				v-for="{ group, attributes: members } in groups"
				:key="group"
				class="flex flex-col gap-1"
			>
				<h3 class="text-small font-semibold text-graphite">{{ groupName(group) }}</h3>
				<PreferenceRow
					v-for="attribute in members"
					:key="attribute.key"
					:attribute="attribute"
					:name="name(attribute.key)"
				/>
			</div>
		</template>
	</section>
</template>
