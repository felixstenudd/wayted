<script setup lang="ts">
import DistanceField from './DistanceField.vue'
import FindRoutes from './FindRoutes.vue'
</script>

<template>
	<!-- What a phone shows at the sheet's lowest stop: enough to go. -->
	<div class="flex flex-col gap-3">
		<DistanceField />
		<FindRoutes />
	</div>
</template>
