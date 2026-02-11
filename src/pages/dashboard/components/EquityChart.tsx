import { useEffect, useRef } from 'react';

interface EquityChartProps {
  data: Array<{ time: string; value: number }>;
}

export default function EquityChart({ data }: EquityChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!canvasRef.current || data.length === 0) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = 40;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Get min and max values
    const values = data.map(d => d.value);
    const minValue = Math.min(...values);
    const maxValue = Math.max(...values);
    const range = maxValue - minValue || 1;

    // Draw grid
    ctx.strokeStyle = 'rgba(148, 163, 184, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = padding + (height - padding * 2) * (i / 5);
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }

    // Draw area gradient
    const gradient = ctx.createLinearGradient(0, padding, 0, height - padding);
    gradient.addColorStop(0, 'rgba(6, 182, 212, 0.3)');
    gradient.addColorStop(1, 'rgba(6, 182, 212, 0)');

    ctx.beginPath();
    data.forEach((point, index) => {
      const x = padding + (width - padding * 2) * (index / (data.length - 1));
      const y = height - padding - ((point.value - minValue) / range) * (height - padding * 2);
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.lineTo(width - padding, height - padding);
    ctx.lineTo(padding, height - padding);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    data.forEach((point, index) => {
      const x = padding + (width - padding * 2) * (index / (data.length - 1));
      const y = height - padding - ((point.value - minValue) / range) * (height - padding * 2);
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    // Draw Y-axis labels
    ctx.fillStyle = '#94a3b8';
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 5; i++) {
      const value = maxValue - (range * i / 5);
      const y = padding + (height - padding * 2) * (i / 5);
      ctx.fillText(`$${value.toFixed(0)}`, padding - 10, y + 4);
    }

  }, [data]);

  return (
    <div className="relative w-full h-80">
      <canvas
        ref={canvasRef}
        className="w-full h-full"
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  );
}