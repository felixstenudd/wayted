<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import { Wordmark } from '@/shared/ui/wordmark'

defineProps<{
	title: string
	lead?: string | undefined
}>()

defineSlots<{
	default(): unknown
	footer(): unknown
}>()

const { t } = useI18n()
</script>

<template>
	<div class="flex min-h-dvh flex-col">
		<header class="mx-auto flex h-16 w-full max-w-6xl items-center px-4 sm:px-6 lg:px-8">
			<RouterLink :to="{ name: 'landing' }" class="rounded-sm">
				<Wordmark>{{ t('app.name') }}</Wordmark>
			</RouterLink>
		</header>
		<main class="flex flex-1 justify-center px-4 pt-8 pb-16 sm:pt-20">
			<div class="flex w-full max-w-sm flex-col gap-8">
				<div class="flex flex-col gap-2">
					<h1 class="text-heading">{{ title }}</h1>
					<p v-if="lead" class="text-graphite">{{ lead }}</p>
				</div>
				<slot />
				<p class="text-graphite">
					<slot name="footer" />
				</p>
			</div>
		</main>
	</div>
</template>
