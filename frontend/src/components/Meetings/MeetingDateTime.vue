<template>
  <fieldset class="space-y-2"><legend class="block text-sm text-ink-gray-5">{{ label }}</legend><div class="grid grid-cols-2 gap-2"><DatePicker :model-value="date" :label="__('Date')" :aria-label="label + ' date'" @update:model-value="setDate" /><TimePicker :model-value="time" format="h:mm A" :label="__('Time')" :aria-label="label + ' time'" @update:model-value="setTime" /></div></fieldset>
</template>
<script setup>
import { computed } from 'vue'
import { DatePicker, TimePicker } from 'frappe-ui'
const props = defineProps({ modelValue:String, label:String })
const emit = defineEmits(['update:modelValue'])
const date = computed(() => props.modelValue?.slice(0,10) || '')
const time = computed(() => props.modelValue?.slice(11,16) || '')
function setDate(v) { emit('update:modelValue', v ? v + ' ' + (time.value || '09:00') + ':00' : '') }
function setTime(v) { if (date.value && v) emit('update:modelValue', date.value + ' ' + v.slice(0,5) + ':00') }
</script>
