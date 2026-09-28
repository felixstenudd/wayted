<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
	<main class="flex min-h-dvh flex-col items-center justify-center gap-2 p-6">
		<h1 class="text-heading">{{ t('planner.title') }}</h1>
		<p class="text-graphite">{{ t('planner.placeholder') }}</p>
	</main>
</template>
