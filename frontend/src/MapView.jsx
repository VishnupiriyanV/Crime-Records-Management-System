import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// where the map opens when there is nothing to show yet
const START = [13.0827, 80.2707];
const COLORS = { High: '#b0123f', Medium: '#c9822b', Low: '#3b7f6e' };
const TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const CREDIT = '&copy; OpenStreetMap contributors';

function useLeaflet(options) {
  const box = useRef(null);
  const map = useRef(null);
  useEffect(() => {
    map.current = L.map(box.current, { zoomControl: true, ...options }).setView(START, 12);
    L.tileLayer(TILES, { maxZoom: 19, attribution: CREDIT }).addTo(map.current);
    return () => { map.current.stop(); map.current.remove(); map.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return { box, map };
}

// click the map to drop a pin; the parent keeps the coordinates
export function PinPicker({ value, onChange }) {
  const { box, map } = useLeaflet({});
  const marker = useRef(null);

  useEffect(() => {
    const handle = (e) => onChange({ lat: e.latlng.lat, lng: e.latlng.lng });
    map.current.on('click', handle);
    return () => map.current?.off('click', handle);
  }, [map, onChange]);

  useEffect(() => {
    if (!value) { marker.current?.remove(); marker.current = null; return; }
    const at = [value.lat, value.lng];
    if (marker.current) marker.current.setLatLng(at);
    else marker.current = L.circleMarker(at, { radius: 9, color: COLORS.High, fillOpacity: 0.7 }).addTo(map.current);
    // no animation: one still running when the page changes would touch a map that is already gone
    map.current.setView(at, Math.max(map.current.getZoom(), 14), { animate: false });
  }, [value, map]);

  return <div ref={box} className="map map--pick" role="application" aria-label="Map: click to pin the place" />;
}

// one fixed pin, for a complaint's own page
export function MiniMap({ lat, lng }) {
  const { box, map } = useLeaflet({ scrollWheelZoom: false });
  useEffect(() => {
    L.circleMarker([lat, lng], { radius: 9, color: COLORS.High, fillOpacity: 0.7 }).addTo(map.current);
    map.current.setView([lat, lng], 15, { animate: false });
  }, [lat, lng, map]);
  return <div ref={box} className="map map--small" role="img" aria-label="Map showing where it happened" />;
}

// every complaint as a dot coloured by severity, the busiest areas as larger rings, stations as squares
export function HotspotMap({ points, hotspots, stations }) {
  const { box, map } = useLeaflet({});
  const layer = useRef(null);

  useEffect(() => {
    layer.current?.remove();
    const group = L.featureGroup().addTo(map.current);
    layer.current = group;
    const biggest = Math.max(1, ...hotspots.map((h) => h.total));
    hotspots.forEach((h) => {
      L.circle([h.latitude, h.longitude], {
        radius: 350 + 450 * (h.total / biggest), color: COLORS.High, weight: 1, fillOpacity: 0.12,
      }).bindTooltip(`${h.total} complaints, mostly ${h.top_category.toLowerCase()}`).addTo(group);
    });
    points.forEach((p) => {
      L.circleMarker([p.latitude, p.longitude], { radius: 4, color: COLORS[p.severity] || COLORS.Medium, weight: 1, fillOpacity: 0.8 })
        .bindTooltip(`${p.fir_no}: ${p.title}`).addTo(group);
    });
    stations.filter((s) => s.latitude != null).forEach((s) => {
      L.marker([s.latitude, s.longitude], {
        icon: L.divIcon({ className: 'station-pin', html: '<span></span>', iconSize: [14, 14] }), title: s.name,
      }).bindTooltip(s.name).addTo(group);
    });
    if (group.getLayers().length) map.current.fitBounds(group.getBounds().pad(0.1), { maxZoom: 15, animate: false });
  }, [points, hotspots, stations, map]);

  return <div ref={box} className="map map--big" role="application" aria-label="Map of complaints" />;
}

export const severityColor = (s) => COLORS[s] || COLORS.Medium;
