<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { ScoreProfile } from '@/features/route'

import { useShownRoute } from '../composables/useShownRoute'
import { usePlannerStore } from '../store'
import RouteHead from './RouteHead.vue'
import RouteOptions from './RouteOptions.vue'
import SettingsLine from './SettingsLine.vue'

defineProps<{
	/** In the sheet the options and length sit in its header, which a phone always shows. */
	layout: 'panel' | 'sheet'
}>()

const { t } = useI18n()
const planner = usePlannerStore()
const { shown } = useShownRoute()

const request = computed(() => planner.search?.request ?? null)
</script>

<template>
	<div v-if="shown && request" class="flex flex-col gap-5">
		<SettingsLine
			:request="request"
			:action="t('planner.settingsLine.change')"
			@action="planner.changeSettings(true)"
		/>
		<template v-if="layout === 'panel'">
			<RouteOptions />
			<RouteHead />
		</template>
		<ScoreProfile :scores="shown.properties.scores" :preferences="request.preferences" />
	</div>
</template>
