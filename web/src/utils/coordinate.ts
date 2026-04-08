export function toRemoteCoords(
  canvasEl: HTMLCanvasElement,
  clientX: number,
  clientY: number,
  remoteW: number,
  remoteH: number,
): { x: number; y: number } {
  const rect = canvasEl.getBoundingClientRect();
  const scaleX = remoteW / rect.width;
  const scaleY = remoteH / rect.height;
  const x = Math.round((clientX - rect.left) * scaleX);
  const y = Math.round((clientY - rect.top) * scaleY);
  return {
    x: Math.max(0, Math.min(x, remoteW - 1)),
    y: Math.max(0, Math.min(y, remoteH - 1)),
  };
}
