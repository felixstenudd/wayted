<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
	<div class="grid h-dvh grid-cols-[auto_1fr]">
		<aside class="flex w-80 flex-col overflow-y-auto border-r border-line bg-paper">
			<header class="flex flex-col gap-1 px-4 py-4">
				<h1 class="text-heading">{{ t('panel.title') }}</h1>
			</header>
		</aside>
		<main />
	</div>
</template>
