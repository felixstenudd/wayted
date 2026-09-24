<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
	<main class="flex min-h-dvh flex-col items-center justify-center gap-2 p-6">
		<h1 class="text-2xl font-semibold">{{ t('planner.title') }}</h1>
		<p class="text-neutral-600">{{ t('planner.placeholder') }}</p>
	</main>
</template>
