"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import type { Layer, PathOptions } from "leaflet";
import { Flame, MapPinned } from "lucide-react";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";

type BurnedAreaProperties = {
  area_ha?: number | string;
  class_name?: string;
};

type BurnedAreaCollection = FeatureCollection<
  Geometry,
  BurnedAreaProperties
>;

const GEOJSON_URL = "/maps/karabuk_burned_area_2025.geojson";
const MAP_CENTER: [number, number] = [41.2, 32.6];
const MAP_ZOOM = 9;

const BURNED_AREA_STYLE: PathOptions = {
  color: "#dc2626",
  fillColor: "#dc2626",
  fillOpacity: 0.45,
  weight: 1,
};

export function BurnedAreaMap() {
  const [data, setData] = useState<BurnedAreaCollection | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let ignore = false;

    async function loadBurnedAreas() {
      try {
        setLoading(true);
        setError(null);

        const response = await fetch(GEOJSON_URL);
        if (!response.ok) {
          throw new Error(`GeoJSON request failed with ${response.status}`);
        }

        const geojson = (await response.json()) as BurnedAreaCollection;
        if (!ignore) setData(geojson);
      } catch (err) {
        if (!ignore) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load burned-area GeoJSON.",
          );
        }
      } finally {
        if (!ignore) setLoading(false);
      }
    }

    loadBurnedAreas();

    return () => {
      ignore = true;
    };
  }, []);

  const featureCount = data?.features.length ?? 0;
  const totalArea = useMemo(() => {
    if (!data) return null;

    return data.features.reduce((sum, feature) => {
      const area = Number(feature.properties?.area_ha ?? 0);
      return Number.isFinite(area) ? sum + area : sum;
    }, 0);
  }, [data]);

  return (
    <section className="ent-card overflow-hidden" aria-labelledby="burned-area-map-title">
      <div className="flex flex-col gap-4 border-b px-5 py-5 md:flex-row md:items-start md:justify-between">
        <div className="max-w-3xl">
          <p className="ent-eyebrow">Static GeoJSON Export</p>
          <h2
            id="burned-area-map-title"
            className="mt-1 flex items-center gap-2 font-display text-xl font-semibold leading-tight tracking-tight"
          >
            <MapPinned className="h-5 w-5" style={{ color: "var(--destructive)" }} />
            Karabük Burned Area Map - 2025
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
            This map shows detected burned areas after the 2025 wildfire period
            using Sentinel-2 imagery and machine learning.
          </p>
        </div>

        {data && totalArea !== null && (
          <div className="grid min-w-[180px] grid-cols-2 gap-2 md:grid-cols-1">
            <MapMetric label="Polygons" value={featureCount.toLocaleString("en-US")} />
            <MapMetric
              label="Detected Area"
              value={`${totalArea.toLocaleString("en-US", {
                maximumFractionDigits: 1,
              })} ha`}
            />
          </div>
        )}
      </div>

      <div className="p-3 md:p-5">
        {loading && (
          <MapState
            icon={<Flame className="h-5 w-5" />}
            title="Loading burned-area map"
            body="Fetching /maps/karabuk_burned_area_2025.geojson from the public folder."
          />
        )}

        {!loading && error && (
          <MapState
            icon={<Flame className="h-5 w-5" />}
            title="Map data could not be loaded"
            body={error}
            danger
          />
        )}

        {!loading && data && (
          <div
            className="burned-area-map relative z-0 isolate overflow-hidden rounded-lg border"
            style={{ borderColor: "var(--border)" }}
          >
            <MapContainer
              center={MAP_CENTER}
              zoom={MAP_ZOOM}
              scrollWheelZoom
              className="h-[500px] w-full md:h-[600px]"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />
              <GeoJSON
                key={featureCount}
                data={data}
                pathOptions={BURNED_AREA_STYLE}
                onEachFeature={bindBurnedAreaPopup}
              />
            </MapContainer>
          </div>
        )}
      </div>
    </section>
  );
}

function MapMetric({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="rounded-md border px-3 py-2"
      style={{ background: "var(--muted)", borderColor: "var(--border)" }}
    >
      <p className="ent-eyebrow">{label}</p>
      <p className="mt-1 font-display text-lg font-semibold leading-none">
        {value}
      </p>
    </div>
  );
}

function MapState({
  icon,
  title,
  body,
  danger = false,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  danger?: boolean;
}) {
  return (
    <div
      className="flex min-h-[320px] items-center justify-center rounded-lg border px-5 text-center"
      style={{
        background: "var(--muted)",
        borderColor: danger ? "var(--destructive)" : "var(--border)",
      }}
    >
      <div className="max-w-md">
        <div
          className="mx-auto flex h-10 w-10 items-center justify-center rounded-md"
          style={{
            background: danger
              ? "rgba(220, 38, 38, 0.12)"
              : "rgba(255, 95, 3, 0.12)",
            color: danger ? "var(--destructive)" : "var(--secondary)",
          }}
          aria-hidden
        >
          {icon}
        </div>
        <h3 className="mt-3 font-display text-base font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      </div>
    </div>
  );
}

function bindBurnedAreaPopup(
  feature: Feature<Geometry, BurnedAreaProperties>,
  layer: Layer,
) {
  const rawArea = Number(feature.properties?.area_ha);
  const area = Number.isFinite(rawArea)
    ? rawArea.toLocaleString("en-US", {
      maximumFractionDigits: 2,
      minimumFractionDigits: 2,
    })
    : "Unknown";

  layer.bindPopup(`
    <div style="font-family: Ubuntu, system-ui, sans-serif; min-width: 140px;">
      <strong>Burned Area</strong>
      <div>Area: ${area} ha</div>
    </div>
  `);
}
