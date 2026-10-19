<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import DistanceField from './DistanceField.vue'
import PreferenceSection from './PreferenceSection.vue'
import RouteKindFields from './RouteKindFields.vue'
import RoutePoints from './RoutePoints.vue'

const { t } = useI18n()
</script>

<template>
	<div class="flex flex-col gap-5">
		<h1 class="text-heading">{{ t('planner.title') }}</h1>
		<RouteKindFields />
		<RoutePoints />
		<DistanceField />
		<PreferenceSection />
	</div>
</template>
