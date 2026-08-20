import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// Relative base: the app has no client-side routing, so "./" makes the same
// build work at GitHub Pages (/GeoSteward/), locally, and anywhere else.
export default defineConfig({
  base: "./",
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      workbox: {
        // Deep-case artifacts are versioned and hashed; cache-first is safe.
        globPatterns: ["**/*.{js,css,html,svg,png}"],
        runtimeCaching: [
          {
            urlPattern: /\/events\/.*\.(geojson|json|jsonl)$/,
            handler: "StaleWhileRevalidate",
            options: { cacheName: "artifacts" },
          },
          {
            urlPattern: /^https:\/\/tiles\.openfreemap\.org\/.*/,
            handler: "CacheFirst",
            options: {
              cacheName: "basemap",
              expiration: { maxEntries: 400, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      manifest: {
        name: "GeoSteward",
        short_name: "GeoSteward",
        description:
          "An accountable GeoAI risk analyst for location-based resilience understanding.",
        theme_color: "#12314f",
        background_color: "#0b1c30",
        display: "standalone",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
      },
    }),
  ],
});
