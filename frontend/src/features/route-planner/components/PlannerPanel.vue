<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import RoutePoints from './RoutePoints.vue'

const { t } = useI18n()
</script>

<template>
	<div class="flex flex-col gap-5">
		<h1 class="text-heading">{{ t('planner.title') }}</h1>
		<RoutePoints />
	</div>
</template>
