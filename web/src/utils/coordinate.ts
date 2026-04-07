export function toRemoteCoords(
  element: HTMLCanvasElement | HTMLVideoElement,
  clientX: number,
  clientY: number,
  remoteW: number,
  remoteH: number,
): { x: number; y: number } {
  const rect = element.getBoundingClientRect();
  const scaleX = remoteW / rect.width;
  const scaleY = remoteH / rect.height;
  const x = Math.round((clientX - rect.left) * scaleX);
  const y = Math.round((clientY - rect.top) * scaleY);
  return {
    x: Math.max(0, Math.min(x, remoteW - 1)),
    y: Math.max(0, Math.min(y, remoteH - 1)),
  };
}
