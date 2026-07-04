<template>
  <div class="dashboard">
    <h1>LakeMind Monitor</h1>
    <div class="health-grid">
      <div v-for="(status, name) in health" :key="name" class="health-card" :class="status">
        <h3>{{ name }}</h3>
        <span>{{ status }}</span>
      </div>
    </div>
    <div class="nav">
      <NuxtLink to="/asset">Asset Monitor</NuxtLink> |
      <NuxtLink to="/data">Data Monitor</NuxtLink> |
      <NuxtLink to="/admin">Admin Monitor</NuxtLink> |
      <NuxtLink to="/chat">Chat</NuxtLink>
    </div>
  </div>
</template>

<script setup>
const { data: health } = await useFetch('/api/health')
</script>

<style>
.health-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; margin: 20px 0; }
.health-card { padding: 16px; border-radius: 8px; border: 1px solid #ddd; text-align: center; }
.health-card.ok { background: #e6f7e6; }
.health-card.error { background: #fff0f0; }
.nav { margin: 20px 0; }
.nav a { margin: 0 8px; }
</style>
