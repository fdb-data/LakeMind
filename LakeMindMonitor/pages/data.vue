<template>
  <div>
    <h1>Data Monitor</h1>
    <NuxtLink to="/">← Back</NuxtLink>
    <h2>Tables</h2>
    <pre>{{ tables }}</pre>
  </div>
</template>

<script setup>
const { data: tables } = await useFetch('/api/data/tables')
</script>
