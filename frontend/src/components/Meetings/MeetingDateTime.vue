<template>
  <div class="space-y-2"><label class="block text-sm text-ink-gray-5">{{ label }}</label><div class="grid grid-cols-2 gap-2"><DatePicker :model-value="date" :aria-label="label + ' date'" @update:model-value="setDate" /><TimePicker :model-value="time" format="h:mm A" :aria-label="label + ' time'" @update:model-value="setTime" /></div></div>
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
