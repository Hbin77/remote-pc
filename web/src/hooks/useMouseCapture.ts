import { useEffect, useRef } from 'react';
import { toRemoteCoords } from '../utils/coordinate';
import { buildMouseMsg, type MouseMsg } from '../utils/protocol';

export function useMouseCapture(
  canvasRef: React.RefObject<HTMLCanvasElement | HTMLVideoElement | null>,
  remoteResolution: [number, number],
  sendFn: (msg: MouseMsg) => void,
  isActive: boolean,
): void {
  const lastMoveTime = useRef(0);
  const MOVE_THROTTLE_MS = 1000 / 60;  // ~16ms for regular move
  const DRAG_THROTTLE_MS = 1000 / 30;  // ~33ms for drag (less network spam)

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !isActive) return;

    const [remoteW, remoteH] = remoteResolution;

    function getCoords(e: MouseEvent): { x: number; y: number } {
      return toRemoteCoords(canvas!, e.clientX, e.clientY, remoteW, remoteH);
    }

    function onMouseMove(e: MouseEvent) {
      const now = performance.now();
      const isDrag = e.buttons > 0;
      const throttle = isDrag ? DRAG_THROTTLE_MS : MOVE_THROTTLE_MS;
      if (now - lastMoveTime.current < throttle) return;
      lastMoveTime.current = now;
      const { x, y } = getCoords(e);
      sendFn(buildMouseMsg(isDrag ? 'drag' : 'move', x, y));
    }

    function onMouseDown(e: MouseEvent) {
      const { x, y } = getCoords(e);
      const button = e.button === 2 ? 'right' : e.button === 1 ? 'middle' : 'left';
      sendFn(buildMouseMsg('button_down', x, y, button));
    }

    function onMouseUp(e: MouseEvent) {
      const { x, y } = getCoords(e);
      const button = e.button === 2 ? 'right' : e.button === 1 ? 'middle' : 'left';
      sendFn(buildMouseMsg('button_up', x, y, button));
    }

    function onDblClick(e: MouseEvent) {
      const { x, y } = getCoords(e);
      sendFn(buildMouseMsg('double_click', x, y, 'left'));
    }

    function onContextMenu(e: MouseEvent) {
      e.preventDefault();
      const { x, y } = getCoords(e);
      sendFn(buildMouseMsg('click', x, y, 'right'));
    }

    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const { x, y } = toRemoteCoords(canvas!, e.clientX, e.clientY, remoteW, remoteH);
      const delta = Math.sign(e.deltaY) * -3;
      sendFn(buildMouseMsg('scroll', x, y, undefined, delta));
    }

    const el = canvas as HTMLElement;
    el.addEventListener('mousemove', onMouseMove as EventListener);
    el.addEventListener('mousedown', onMouseDown as EventListener);
    el.addEventListener('mouseup', onMouseUp as EventListener);
    el.addEventListener('dblclick', onDblClick as EventListener);
    el.addEventListener('contextmenu', onContextMenu as EventListener);
    el.addEventListener('wheel', onWheel as EventListener, { passive: false });

    return () => {
      el.removeEventListener('mousemove', onMouseMove as EventListener);
      el.removeEventListener('mousedown', onMouseDown as EventListener);
      el.removeEventListener('mouseup', onMouseUp as EventListener);
      el.removeEventListener('dblclick', onDblClick as EventListener);
      el.removeEventListener('contextmenu', onContextMenu as EventListener);
      el.removeEventListener('wheel', onWheel as EventListener);
    };
  }, [canvasRef, remoteResolution, sendFn, isActive]);
}
