import React, { useEffect, useState } from 'react';

/** Magic UI-inspired animated number ticker. */
export function NumberTicker({ value = 0, durationMs = 450 }) {
  const [display, setDisplay] = useState(Number(value) || 0);

  useEffect(() => {
    const target = Number(value) || 0;
    const startVal = display;
    if (startVal === target) return;
    const start = performance.now();
    let raf = 0;

    const tick = (now) => {
      const p = Math.min(1, (now - start) / durationMs);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(startVal + (target - startVal) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return <span>{display}</span>;
}
